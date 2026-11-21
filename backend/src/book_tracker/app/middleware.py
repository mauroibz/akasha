"""The request path's two middlewares, outermost last (split out of `create_app`, 088)."""

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from book_tracker.api.auth import (
    client_address,
    error_response,
    has_credentialed_user,
    request_uses_https,
    set_session_cookie,
    strip_untrusted_identity_header,
    trusted_header_user,
    unauthenticated,
)
from book_tracker.api.auth import (
    setup_required as setup_required_response,
)
from book_tracker.api.identity import Principal, request_path, session_store, session_token
from book_tracker.api.security_log import security_event
from book_tracker.app.errors import NOT_FOUND
from book_tracker.config import Settings
from book_tracker.infrastructure.offload import off_loop

#: What an incoming `X-Request-Id` must look like to be kept: a proxy's own id
#: joins its logs to ours, but anything else is replaced rather than echoed.
_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{8,64}")

#: Methods a browser may send cross-site without asking first; everything else
#: on `/api/` must come from the application's own pages (F9).
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_SAME_SITE_FETCH = frozenset({"same-origin", "none"})

#: The only routes reachable without a session when authentication is on: the
#: container's own probes. Provider health names providers and their state, so
#: it waits behind the boundary like the rest (F18).
_PUBLIC_API = frozenset({"/api/health/live", "/api/health/ready"})

#: Paths that are not part of the shell even though they are GET and outside
#: `/api/`: the contract, the docs, and `/metrics` (F18).
_NOT_SHELL = frozenset({"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc", "/metrics"})

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob: https:; font-src 'self'; connect-src 'self'; "
    "manifest-src 'self'; worker-src 'self'; object-src 'none'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
}
#: FastAPI's interactive docs load their script from a CDN; they exist only
#: with authentication off, where the policy would simply break them.
_DOCS_PATHS = frozenset({"/docs", "/docs/oauth2-redirect", "/redoc"})


def cross_site_refusal(request: Request) -> Response | None:
    """Refuse an unsafe API request a browser sent from another site (F9).

    `Sec-Fetch-Site` decides when the browser sent it; otherwise an `Origin`
    must name this host. A request carrying neither is not from a browser page
    (curl, scripts, the test client) and is left to authentication.
    """
    if request.method in _SAFE_METHODS or not request_path(request).startswith("/api/"):
        return None
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site is not None:
        allowed = fetch_site.strip().casefold() in _SAME_SITE_FETCH
    else:
        origin = request.headers.get("origin")
        if origin is None:
            return None
        host = request.headers.get("host", "").strip().casefold()
        try:
            origin_host = urlsplit(origin.strip()).netloc.casefold()
        except ValueError:
            origin_host = ""
        allowed = bool(host) and origin_host == host
    if allowed:
        return None
    security_event(
        "cross_site_request_refused",
        client=client_address(request),
        method=request.method,
        route=request_path(request),
        fetch_site=fetch_site,
    )
    return error_response(
        403, "cross_site_request", "This request did not come from Akasha's own pages"
    )


def install_middleware(app: FastAPI, configured: Settings) -> None:
    @app.middleware("http")
    async def authentication_boundary(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        async def dispatch(principal: Principal | None = None) -> Response:
            try:
                return await call_next(request)
            finally:
                if principal is not None and principal.acting_as is not None:
                    route = request.scope.get("route")
                    logging.getLogger("book_tracker.audit").info(
                        "admin_acting_request",
                        extra={
                            "admin_user_id": principal.user_id,
                            "acting_as_user_id": principal.acting_as,
                            "method": request.method,
                            "route": getattr(route, "path", request_path(request)),
                        },
                    )

        # Every decision below reads the routed path, never the Host-built URL (F2).
        path = request_path(request)
        refusal = cross_site_refusal(request)
        if refusal is not None:
            return refusal
        if configured.auth == "off":
            if path.startswith("/api/auth/"):
                return JSONResponse(status_code=404, content=NOT_FOUND)
            return await call_next(request)
        strip_untrusted_identity_header(
            request, configured.trusted_proxy_header, configured.trusted_proxy_peers
        )
        if path in _PUBLIC_API:
            return await call_next(request)
        # The shell and its emitted assets must load before Sprint 078 can draw
        # a login screen. FastAPI's own contract/docs routes and `/metrics` are not
        # shell assets and remain behind the same boundary as the rest.
        is_spa_get = request.method in {"GET", "HEAD"} and path not in _NOT_SHELL
        if not path.startswith("/api/") and is_spa_get:
            return await call_next(request)

        # Both lookups below run on every authenticated request, so they leave the
        # event loop: a slow one used to hold up every request behind it (Sprint 087).
        needs_setup = not await off_loop(has_credentialed_user, request.app.state.engine)
        if needs_setup:
            if path not in {"/api/auth/me", "/api/auth/setup"}:
                return setup_required_response()
            return await call_next(request)

        token = session_token(request)
        sessions = session_store(request)
        identity = await off_loop(sessions.lookup, token) if token else None
        issued_token: str | None = None
        if (
            identity is None
            and configured.trusted_proxy_header
            and path not in {"/api/auth/login", "/api/auth/setup", "/api/auth/session"}
        ):
            asserted_identity = request.headers.get(configured.trusted_proxy_header)
            if asserted_identity:
                user = await off_loop(
                    trusted_header_user,
                    request.app.state.engine,
                    asserted_identity,
                    autocreate=configured.trusted_header_autocreate,
                )
                if user is None:
                    return error_response(
                        403,
                        "unknown_proxy_identity",
                        "This proxy identity is not allowed to use Akasha",
                    )
                created = await off_loop(
                    sessions.create, int(user["id"]), user_agent=request.headers.get("user-agent")
                )
                issued_token = created.token
                identity = await off_loop(sessions.lookup, created.token)
        principal = (
            Principal(
                user_id=identity.user_id,
                username=identity.username,
                is_admin=identity.is_admin,
                acting_as=identity.acting_as_user_id,
            )
            if identity is not None
            else None
        )
        if identity is not None:
            request.state.session_identity = identity
            request.state.session_id = identity.session_id

        async def dispatch_with_cookie() -> Response:
            response = await dispatch(principal)
            refresh_token = (
                token
                if identity is not None and identity.refreshed and path != "/api/auth/session"
                else None
            )
            cookie_token = issued_token or refresh_token
            if cookie_token is not None and not getattr(
                request.state, "suppress_session_cookie", False
            ):
                set_session_cookie(response, request, cookie_token)
            return response

        if path.startswith("/api/auth/"):
            if principal is not None:
                request.state.principal = principal
            return await dispatch_with_cookie()
        if identity is None:
            return unauthenticated()
        assert principal is not None
        request.state.principal = principal
        return await dispatch_with_cookie()

    # Registered last, so it is the outermost middleware: the id is bound before the
    # authentication boundary runs and covers every line logged under it (Sprint 087).
    @app.middleware("http")
    async def request_identity(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if _REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
        path = request_path(request)
        # One line per API request. Health checks run every few seconds from the
        # container's own probe, and shell assets are not requests anyone debugs.
        logged = path.startswith("/api/") and not path.startswith("/api/health/")
        started = time.perf_counter()
        status = 500
        with structlog.contextvars.bound_contextvars(request_id=request_id):
            try:
                response = await call_next(request)
                status = response.status_code
            finally:
                if logged:
                    route = request.scope.get("route")
                    request.app.state.request_timings.record(
                        request.method,
                        getattr(route, "path", "unmatched"),
                        status,
                        time.perf_counter() - started,
                    )
                    logging.getLogger("book_tracker.requests").info(
                        "request_finished",
                        extra={
                            "method": request.method,
                            # The template, never the concrete path or its query:
                            # `/api/entries/{entry_id}`, not what was asked for.
                            "route": getattr(route, "path", "unmatched"),
                            "status": status,
                            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                        },
                    )
        response.headers["X-Request-Id"] = request_id
        return response


def install_security_headers(app: FastAPI) -> None:
    """Browser hardening on every response (Sprint 128, F13).

    Registered after the other two so it is the outermost: even a refusal from
    the authentication boundary carries the headers.
    """

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        path = request_path(request)
        headers = response.headers
        for name, value in SECURITY_HEADERS.items():
            headers.setdefault(name, value)
        if path not in _DOCS_PATHS:
            headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        if request_uses_https(request):
            headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        if path.startswith("/api/") or path in {"/openapi.json", "/metrics"}:
            # Authenticated JSON never lands in a shared or disk cache.
            headers.setdefault("Cache-Control", "no-store")
        return response
