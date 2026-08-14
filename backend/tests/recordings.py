"""Replay committed provider recordings instead of mocking the unit under test.

DEC-025: substituting a mock for the provider method under test is not proof of that
method. Boundary behaviour is proven by replaying a real response captured from the
live provider. See `tests/fixtures/providers/README.md` for provenance and the exact
commands used to capture each file.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import AsyncIterator, Callable, Mapping
from pathlib import Path
from typing import Any

import httpx

FIXTURES = Path(__file__).parent / "fixtures" / "providers"


def recording(name: str) -> Any:
    """Return a committed recorded provider response body."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def redirect_location(name: str) -> str:
    """Return the Location header from a committed recorded redirect response."""
    for line in (FIXTURES / name).read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition(":")
        if key.strip().casefold() == "location":
            return value.strip()
    raise AssertionError(f"{name} has no Location header")


Route = tuple[int, Any] | tuple[int, Any, Mapping[str, str]]


def replay(
    routes: Mapping[str, Route],
    *,
    on_request: Callable[[httpx.Request], None] | None = None,
) -> httpx.MockTransport:
    """Serve recorded responses keyed by request path.

    Any path that was not recorded fails the test loudly rather than returning a
    convenient default, so a test can never pass on a response nobody captured.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if on_request is not None:
            on_request(request)
        route = routes.get(request.url.path)
        if route is None:
            raise AssertionError(f"no recording for {request.url.path}")
        status, body = route[0], route[1]
        headers = dict(route[2]) if len(route) > 2 else {}
        if body is None:
            return httpx.Response(status, headers=headers)
        if isinstance(body, bytes | str):
            return httpx.Response(status, content=body, headers=headers)
        return httpx.Response(status, json=body, headers=headers)

    return httpx.MockTransport(handler)


# --------------------------------------------------------------------------------------
# Route sets shared by the provider and enrichment suites
# --------------------------------------------------------------------------------------

RECORDED_ISBN = "9788437604572"

OPENLIBRARY_HIT: Mapping[str, Route] = {
    f"/isbn/{RECORDED_ISBN}.json": (
        302,
        None,
        {"location": redirect_location("isbn_9788437604572.headers")},
    ),
    "/books/OL19845805M.json": (200, recording("edition_OL19845805M.json")),
    "/authors/OL2631008A.json": (200, recording("author_OL2631008A.json")),
    "/works/OL14860424W.json": (200, recording("work_OL14860424W.json")),
}
OPENLIBRARY_MISS: Mapping[str, Route] = {
    f"/isbn/{RECORDED_ISBN}.json": (404, {"error": "notfound"})
}
GOOGLE_HIT: Mapping[str, Route] = {
    "/books/v1/volumes": (200, recording("googlebooks_isbn_9788437604572.json"))
}
GOOGLE_MISS: Mapping[str, Route] = {
    "/books/v1/volumes": (200, recording("googlebooks_isbn_9789994444441_empty.json"))
}
# `GOOGLE_HIT` answers with a volume carrying no ISBN, which is the defect DEC-044
# repaired and is now rejected. `GOOGLE_CONFIRMED` is the verified counterpart, for
# proving the fallback still works rather than having been switched off.
CONFIRMED_ISBN = "9780307474728"
GOOGLE_CONFIRMED: Mapping[str, Route] = {
    "/books/v1/volumes": (200, recording("googlebooks_isbn_9780307474728.json"))
}
OPENLIBRARY_MISS_CONFIRMED: Mapping[str, Route] = {
    f"/isbn/{CONFIRMED_ISBN}.json": (404, {"error": "notfound"})
}


def unreachable_transport() -> httpx.MockTransport:
    """A transport that fails the test if the code under test calls a provider at all."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected provider call to {request.url}")

    return httpx.MockTransport(handler)


@contextlib.asynccontextmanager
async def enrichment_providers(
    *,
    openlibrary: Mapping[str, Route] | None = None,
    google: Mapping[str, Route] | None = None,
    forbid_calls: bool = False,
    on_request: Callable[[httpx.Request], None] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield real provider instances whose transports replay committed recordings.

    `on_request` observes every request the providers actually make. One enrichment is
    not one HTTP call — an Open Library edition drags in its authors and its work — and
    counting them is what turns a per-book cost into an import-sized one.
    """
    from book_tracker.infrastructure.providers import (
        GoogleBooksProvider,
        OpenLibraryProvider,
        create_provider_client,
    )

    providers: dict[str, Any] = {}
    clients: list[httpx.AsyncClient] = []
    try:
        if openlibrary is not None or forbid_calls:
            transport = (
                unreachable_transport()
                if forbid_calls
                else replay(openlibrary or {}, on_request=on_request)
            )
            client = create_provider_client(transport=transport)
            clients.append(client)
            providers["openlibrary"] = OpenLibraryProvider(client, "test@example.invalid")
        if google is not None:
            client = create_provider_client(transport=replay(google, on_request=on_request))
            clients.append(client)
            providers["googlebooks"] = GoogleBooksProvider(client, "test-key")
        yield providers
    finally:
        for client in clients:
            await client.aclose()
