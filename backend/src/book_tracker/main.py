"""The application factory. Each concern lives in `book_tracker.app` (Sprint 088)."""

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from book_tracker.api.auth import router as auth_router
from book_tracker.api.auth import users_router
from book_tracker.api.events import router as events_router
from book_tracker.api.export import router as export_router
from book_tracker.api.goals import router as goals_router
from book_tracker.api.imports import catalog_router, enrichment_router
from book_tracker.api.imports import router as imports_router
from book_tracker.api.library import ErrorResponse
from book_tracker.api.library import router as library_router
from book_tracker.api.providers import router as providers_router
from book_tracker.app.errors import NOT_FOUND, install_error_handlers
from book_tracker.app.health import install_health_routes
from book_tracker.app.lifespan import back_up_before_migrating, make_lifespan
from book_tracker.app.metrics import install_metrics
from book_tracker.app.middleware import install_middleware
from book_tracker.config import Settings

#: Kept under its old name for the migration tests that call it directly.
_back_up_before_migrating = back_up_before_migrating


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or Settings()
    # Every route that takes input documents the envelope for its 422, which is what
    # `request_validation_failed` returns, instead of FastAPI's own body.
    app = FastAPI(
        title="Akasha",
        version="2.7.0",
        lifespan=make_lifespan(configured),
        responses={422: {"model": ErrorResponse}},
    )
    # Available before lifespan for route inspection; requests still run only
    # after lifespan has installed the engine and session store dependencies.
    app.state.auth = configured.auth
    app.state.cookie_secure = configured.cookie_secure
    app.state.trusted_proxy_peers = configured.trusted_proxy_peers
    app.state.trusted_proxy_header = configured.trusted_proxy_header
    app.state.trusted_header_autocreate = configured.trusted_header_autocreate

    install_error_handlers(app)
    install_middleware(app, configured)
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
        index = Path(static_dir) / "index.html"

        @app.get("/{path:path}", include_in_schema=False, response_model=None)
        def spa(path: str) -> Response:
            root = Path(static_dir).resolve()
            candidate = (root / path).resolve()
            if candidate.is_relative_to(root) and candidate.is_file() and candidate != index:
                return FileResponse(candidate)
            return HTMLResponse(index.read_text(encoding="utf-8"))

    return app


app = create_app()
