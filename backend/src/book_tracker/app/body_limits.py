"""Request bodies are capped before they are read, not after (Sprint 128, F7).

FastAPI reads a JSON body whole into memory and Starlette spools a multipart body
whole to disk before a route's own size check ever runs, so a route's cap bounded
what it *kept*, never what it *received*: a 400 MiB login body cost 1.2 GB of RSS
before the password was looked at. This pure-ASGI middleware decides each request's
ceiling from its path alone (`scope["path"]`, never a header-derived URL) and

- refuses with 413 before reading a byte when `Content-Length` declares more;
- counts the bytes actually received, so a chunked body with no `Content-Length`
  is cut off at the same ceiling, and answers 413 in place of whatever the route
  made of the truncated body;
- for the routes that write uploads to disk, refuses with 507 before reading when
  the declared body would leave less than the configured free-space minimum on the
  data volume or the temporary directory the upload is spooled to.

The ceilings are the routes' own documented caps plus room for multipart framing;
the routes still enforce their exact caps on what they parse.
"""

from __future__ import annotations

import json
import re
import tempfile
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from starlette.requests import Request

from book_tracker.api.imports import MAX_IMPORT_BYTES, MAX_IMPORT_FILES
from book_tracker.domain.registry import IMPORTERS
from book_tracker.domain.sniffing import SNIFF_BYTES
from book_tracker.infrastructure.covers import MAX_COVER_BYTES
from book_tracker.infrastructure.diskspace import InsufficientDiskSpace, ensure_free_space

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

MiB = 1024 * 1024
KiB = 1024

#: Every request that names no larger ceiling below: JSON bodies, logins, form posts.
DEFAULT_MAX_BODY_BYTES = 1 * MiB
#: Multipart framing around a single file: boundaries, part headers, a few fields.
MULTIPART_OVERHEAD_BYTES = 64 * KiB
#: Per file in a bundle: its part's boundary and headers, filename included.
PER_PART_OVERHEAD_BYTES = 1 * KiB
#: An import bundle's form fields (Calibre's plan manifest lists every offered file).
IMPORT_FIELDS_OVERHEAD_BYTES = 1 * MiB
#: `/api/import/detect` reads one sniff window from at most 50 files; the client
#: sends only that window of each.
DETECT_MAX_FILES = 50
#: An import commit names a choice per ambiguous row; generous for 10,000 rows.
IMPORT_COMMIT_MAX_BYTES = 8 * MiB


@dataclass(frozen=True)
class BodyLimit:
    max_bytes: int
    #: The body is written to disk, so free space is checked against its declared size.
    writes_to_disk: bool = False


def _attachment_limit(app: Any) -> BodyLimit:
    cap = int(getattr(getattr(app, "state", None), "attachment_max_bytes", 25 * MiB))
    return BodyLimit(cap + MULTIPART_OVERHEAD_BYTES, writes_to_disk=True)


def _importer_limit(name: str) -> BodyLimit:
    """The widest upload any of this importer's declared inputs accepts, framed."""
    importer = IMPORTERS.get(name)
    if importer is None:
        return BodyLimit(DEFAULT_MAX_BODY_BYTES)
    spec = importer.input
    widest = 0
    for candidate in (spec, *spec.alternates):
        if candidate.kind == "path":
            continue
        files = candidate.max_files or (1 if candidate.kind == "upload" else MAX_IMPORT_FILES)
        widest = max(
            widest,
            (candidate.max_bytes or MAX_IMPORT_BYTES)
            + IMPORT_FIELDS_OVERHEAD_BYTES
            + files * PER_PART_OVERHEAD_BYTES,
        )
    if widest == 0:
        return BodyLimit(DEFAULT_MAX_BODY_BYTES)
    return BodyLimit(widest, writes_to_disk=True)


#: The table. First match wins; a path matching none gets `DEFAULT_MAX_BODY_BYTES`.
ROUTE_LIMITS: tuple[tuple[re.Pattern[str], Callable[[Any, re.Match[str]], BodyLimit]], ...] = (
    (
        re.compile(r"/api/items/[^/]+/cover"),
        lambda _app, _match: BodyLimit(MAX_COVER_BYTES + MULTIPART_OVERHEAD_BYTES, True),
    ),
    (
        re.compile(r"/api/items/[^/]+/attachments"),
        lambda app, _match: _attachment_limit(app),
    ),
    (
        re.compile(r"/api/import/detect"),
        lambda _app, _match: BodyLimit(
            DETECT_MAX_FILES * (SNIFF_BYTES + PER_PART_OVERHEAD_BYTES) + MULTIPART_OVERHEAD_BYTES
        ),
    ),
    (
        re.compile(r"/api/import/[^/]+/batches/[^/]+/files"),
        lambda app, _match: _attachment_limit(app),
    ),
    (
        re.compile(r"/api/import/(?P<importer>[^/]+)/(?:preview|plan)"),
        lambda _app, match: _importer_limit(match.group("importer")),
    ),
    (
        re.compile(r"/api/import/[^/]+/commit"),
        lambda _app, _match: BodyLimit(IMPORT_COMMIT_MAX_BYTES),
    ),
)


def body_limit(app: Any, path: str) -> BodyLimit:
    for pattern, limit in ROUTE_LIMITS:
        match = pattern.fullmatch(path)
        if match:
            return limit(app, match)
    return BodyLimit(DEFAULT_MAX_BODY_BYTES)


class _BodyTooLarge(Exception):
    """Raised into the application from `receive` once the ceiling is crossed."""


def _declared_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", ()):
        if name == b"content-length":
            try:
                length = int(value)
            except ValueError:
                return None
            return length if length >= 0 else None
    return None


async def _too_large(send: Send, limit: int) -> None:
    megabytes = max(1, limit // MiB)
    body = json.dumps(
        {
            "error": {
                "code": "payload_too_large",
                "message": f"Request body exceeds {limit} bytes",
                "details": {"max_bytes": limit},
                "user_message": f"That is larger than the {megabytes} MiB this accepts.",
            }
        }
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"connection", b"close"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _check_free_space(app: Any, declared: int) -> None:
    """Refuse a declared upload that would eat into the free-space minimum."""
    data_dir = getattr(app.state, "data_dir", None)
    minimum = int(getattr(app.state, "min_free_bytes", 0))
    folders = {Path(tempfile.gettempdir())}
    if data_dir is not None:
        folders.add(Path(data_dir))
    for folder in folders:
        if folder.exists():
            ensure_free_space(folder, minimum + declared)


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        application = scope.get("app")
        limit = body_limit(application, scope["path"])
        declared = _declared_length(scope)
        if declared is not None and declared > limit.max_bytes:
            await _too_large(send, limit.max_bytes)
            return
        if limit.writes_to_disk and declared and application is not None:
            try:
                _check_free_space(application, declared)
            except InsufficientDiskSpace as error:
                handler = application.exception_handlers[InsufficientDiskSpace]
                response = await handler(Request(scope), error)
                await response(scope, receive, send)
                return

        received = 0
        exceeded = False
        started = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            if exceeded:
                raise _BodyTooLarge
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit.max_bytes:
                    exceeded = True
                    raise _BodyTooLarge
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal started
            # Once the ceiling is crossed, whatever the route made of a truncated
            # body (FastAPI answers 400 for one it could not parse) is replaced.
            if exceeded and not started:
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not exceeded:
                raise
        if exceeded and not started:
            await _too_large(send, limit.max_bytes)


def install_body_limits(app: Any) -> None:
    """Innermost of the middlewares, so a 413 still carries the request id and log."""
    app.add_middleware(BodyLimitMiddleware)
