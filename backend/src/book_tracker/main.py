"""The application factory. Each concern lives in `book_tracker.app` (Sprint 088)."""

from datetime import timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.datastructures import Headers
from starlette.middleware.gzip import DEFAULT_EXCLUDED_CONTENT_TYPES, GZipMiddleware
from starlette.staticfiles import NotModifiedResponse

from book_tracker.api.auth import router as auth_router
from book_tracker.api.auth import users_router
from book_tracker.api.events import router as events_router
from book_tracker.api.export import router as export_router
from book_tracker.api.goals import router as goals_router
from book_tracker.api.home import router as home_router
from book_tracker.api.imports import catalog_router, enrichment_router
from book_tracker.api.imports import router as imports_router
from book_tracker.api.library import ErrorResponse
from book_tracker.api.library import router as library_router
from book_tracker.api.providers import router as providers_router
from book_tracker.app.body_limits import install_body_limits
from book_tracker.app.cloudflare_access import install_cloudflare_access
from book_tracker.app.errors import NOT_FOUND, install_error_handlers
from book_tracker.app.health import install_health_routes
from book_tracker.app.lifespan import back_up_before_migrating, make_lifespan
from book_tracker.app.metrics import install_metrics
from book_tracker.app.middleware import install_middleware, install_security_headers
from book_tracker.config import Settings

#: Kept under its old name for the migration tests that call it directly.
_back_up_before_migrating = back_up_before_migrating

#: Vite names every file under `assets/` after its content, so a name never
#: changes meaning: a year, and no revalidation (Sprint 129).
IMMUTABLE = "public, max-age=31536000, immutable"
#: Everything else at the static root keeps its name across deployments (the
#: service worker above all), so the browser revalidates it on every use.
REVALIDATE = "no-cache"
#: Below this a compressed body saves less than the work costs.
GZIP_MINIMUM_BYTES = 1024
#: Close to level 9's size on text bundles and JSON, at a fraction of the CPU.
GZIP_LEVEL = 5
#: Starlette's own list (the event stream, archives, raster images, fonts) plus
#: attachments, which are served as opaque octet streams and are mostly EPUBs and
#: PDFs: already compressed, up to the attachment cap in size, and a download
#: keeps its `Content-Length` only uncompressed.
GZIP_EXCLUDED = (
    *DEFAULT_EXCLUDED_CONTENT_TYPES,
    "application/octet-stream",
    "application/pdf",
    "application/epub+zip",
)


def _not_modified(response: Response, request: Headers) -> bool:
    """Whether the request's validators match the file's, read as StaticFiles reads them."""
    if if_none_match := request.get("if-none-match"):
        if if_none_match.strip() == "*":
            return True
        etag = response.headers["etag"]
        return etag in {tag.strip().removeprefix("W/") for tag in if_none_match.split(",")}
    if_modified_since = request.get("if-modified-since")
    if if_modified_since is None:
        return False
    try:
        since = parsedate_to_datetime(if_modified_since)
        modified = parsedate_to_datetime(response.headers["last-modified"])
    except (TypeError, ValueError, IndexError):
        return False
    return since >= modified


def _static_file(path: Path, request: Request, cache_control: str) -> Response:
    """A file from the static root, answering a conditional request with 304."""
    response = FileResponse(path, stat_result=path.stat(), headers={"Cache-Control": cache_control})
    if _not_modified(response, request.headers):
        return NotModifiedResponse(response.headers)
    return response


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or Settings()
    # Every route that takes input documents the envelope for its 422, which is what
    # `request_validation_failed` returns, instead of FastAPI's own body.
    # With authentication on, the interactive docs are off (Sprint 128): they are
    # a map of the API for whoever reaches the hostname. `/openapi.json` stays,
    # behind the boundary, for the frontend's contract tooling.
    docs_on = configured.auth == "off"
    app = FastAPI(
        title="Akasha",
        version="2.9.0",
        lifespan=make_lifespan(configured),
        responses={422: {"model": ErrorResponse}},
        docs_url="/docs" if docs_on else None,
        redoc_url="/redoc" if docs_on else None,
    )
    # Available before lifespan for route inspection; requests still run only
    # after lifespan has installed the engine and session store dependencies.
    app.state.auth = configured.auth
    app.state.cookie_secure = configured.cookie_secure
    app.state.trusted_proxy_peers = configured.trusted_proxy_peers
    app.state.trusted_proxy_header = configured.trusted_proxy_header
    app.state.trusted_header_autocreate = configured.trusted_header_autocreate
    app.state.client_ip_header = configured.client_ip_header
    app.state.session_lifetime = timedelta(days=configured.session_days)

    install_error_handlers(app)
    # Innermost (Sprint 129), where it sees each route's own response: the
    # function middlewares above re-stream every body in chunks, and a streamed
    # body is compressed whatever its size. Starlette leaves `text/event-stream`
    # (`/api/events` must arrive event by event) and compressed images alone.
    app.add_middleware(
        GZipMiddleware,
        minimum_size=GZIP_MINIMUM_BYTES,
        compresslevel=GZIP_LEVEL,
        exclude_content_types=GZIP_EXCLUDED,
    )
    install_body_limits(app)
    install_middleware(app, configured)
    install_security_headers(app)
    install_health_routes(app)
    install_metrics(app, configured)

    auth_responses: dict[int | str, dict[str, Any]] = {
        401: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    }
    app.include_router(auth_router)
    app.include_router(users_router, responses=auth_responses)
    app.include_router(library_router, responses=auth_responses)
    app.include_router(goals_router, responses=auth_responses)
    app.include_router(home_router, responses=auth_responses)
    app.include_router(providers_router, responses=auth_responses)
    app.include_router(imports_router, responses=auth_responses)
    app.include_router(catalog_router, responses=auth_responses)
    app.include_router(enrichment_router, responses=auth_responses)
    app.include_router(export_router, responses=auth_responses)
    app.include_router(events_router, responses=auth_responses)

    @app.api_route(
        "/api/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        include_in_schema=False,
    )
    def missing_api(path: str) -> JSONResponse:
        return JSONResponse(status_code=404, content=NOT_FOUND)

    static_dir = configured.static_dir
    if static_dir is not None:
        root = Path(static_dir).resolve()
        index = root / "index.html"
        hashed = root / "assets"

        @app.get("/{path:path}", include_in_schema=False, response_model=None)
        def spa(path: str, request: Request) -> Response:
            candidate = (root / path).resolve()
            if candidate.is_relative_to(root) and candidate.is_file() and candidate != index:
                immutable = candidate.is_relative_to(hashed)
                return _static_file(candidate, request, IMMUTABLE if immutable else REVALIDATE)
            # The shell must be revalidated on every load, so a deployment's new
            # asset names (and security headers) reach the browser at once.
            return HTMLResponse(
                index.read_text(encoding="utf-8"), headers={"Cache-Control": "no-cache"}
            )

    # Last, so it is the outermost middleware (DEC-180 point 4).
    install_cloudflare_access(app, configured)
    return app


app = create_app()
