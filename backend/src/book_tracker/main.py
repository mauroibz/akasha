from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from book_tracker.api.library import router as library_router
from book_tracker.api.providers import router as providers_router
from book_tracker.application.library import LibraryError
from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.domain.providers import Provider
from book_tracker.infrastructure.providers import GoogleBooksProvider, OpenLibraryProvider
from book_tracker.logging import configure_logging
from book_tracker.migrations import schema_is_current, upgrade


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(configured.log_level)
        for directory in ("", "covers", "imports", "backups"):
            (configured.data_dir / directory).mkdir(parents=True, exist_ok=True)
        if not getattr(app.state, "skip_migrations", False):
            assert configured.database_url is not None
            upgrade(configured.database_url)
        app.state.engine = create_engine(configured)
        provider_client = httpx.AsyncClient(
            timeout=httpx.Timeout(5), limits=httpx.Limits(max_connections=10)
        )
        providers: list[Provider] = [
            OpenLibraryProvider(
                provider_client, configured.user_agent_contact or "local@example.invalid"
            )
        ]
        google = GoogleBooksProvider(provider_client, configured.google_books_api_key)
        if google.enabled:
            providers.append(google)
        app.state.providers = {provider.name: provider for provider in providers}
        try:
            yield
        finally:
            await provider_client.aclose()
            app.state.engine.dispose()

    app = FastAPI(title="Akasha Book Tracker", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(LibraryError)
    async def library_error(_request: object, error: LibraryError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": error.code, "message": error.message, "details": {}}},
        )

    @app.get("/api/health/live")
    async def live() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/api/health/ready")
    async def ready() -> JSONResponse:
        try:
            with app.state.engine.connect() as database:
                database.execute(text("SELECT 1"))
            if not schema_is_current(app.state.engine):
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": {
                            "code": "schema_not_current",
                            "message": "Database migration is required",
                            "details": {},
                        }
                    },
                )
        except (SQLAlchemyError, OSError):
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "database_unavailable",
                        "message": "Database is unavailable",
                        "details": {},
                    }
                },
            )
        return JSONResponse({"status": "ready"})

    app.include_router(library_router)
    app.include_router(providers_router)

    @app.api_route(
        "/api/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        include_in_schema=False,
    )
    async def missing_api(path: str) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    static_dir = configured.static_dir
    if static_dir is not None:
        index = Path(static_dir) / "index.html"

        @app.get("/{path:path}", include_in_schema=False, response_model=None)
        async def spa(path: str) -> Response:
            root = Path(static_dir).resolve()
            candidate = (root / path).resolve()
            if candidate.is_relative_to(root) and candidate.is_file() and candidate != index:
                return FileResponse(candidate)
            return HTMLResponse(index.read_text(encoding="utf-8"))

    return app


app = create_app()
