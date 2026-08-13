import asyncio
import contextlib
import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from book_tracker.api.imports import enrichment_router
from book_tracker.api.imports import router as imports_router
from book_tracker.api.library import router as library_router
from book_tracker.api.providers import router as providers_router
from book_tracker.application.enrichment import EnrichmentHandler
from book_tracker.application.library import LibraryError
from book_tracker.backup import BackupError, create_backup, read_manifest
from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.domain.providers import Provider
from book_tracker.infrastructure.jobs import JobRunner, RateLimiter
from book_tracker.infrastructure.providers import (
    GoogleBooksProvider,
    OpenLibraryProvider,
    create_provider_client,
)
from book_tracker.logging import configure_logging
from book_tracker.migrations import pending_revisions, schema_is_current, upgrade


class ProviderStatus(BaseModel):
    name: str
    available: bool
    reason: str | None = None


class ProviderHealth(BaseModel):
    providers: list[ProviderStatus]
    degraded: bool


def _current_revision(database_path: Path) -> str | None:
    connection = sqlite3.connect(database_path)
    try:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    except sqlite3.DatabaseError:
        return None
    finally:
        connection.close()
    return str(row[0]) if row else None


def _existing_pre_migration_backup(backup_dir: Path, revision: str | None) -> Path | None:
    if revision is None or not backup_dir.is_dir():
        return None
    for candidate in sorted(backup_dir.iterdir()):
        if not candidate.is_dir():
            continue
        manifest = read_manifest(candidate)
        if (
            manifest is not None
            and manifest.get("label") == "pre-migration"
            and manifest.get("alembic_revision") == revision
        ):
            return candidate
    return None


def _back_up_before_migrating(configured: Settings) -> None:
    """Copy an existing library before a migration touches it.

    Migration 0007 rewrites every item row. On a home server nobody is watching
    the upgrade, so it takes a rollback point first and refuses to run without
    one. A database with nothing in it yet is skipped: there is nothing to lose,
    and a first start should not pay for a backup of an empty schema.
    """
    assert configured.database_url is not None
    assert configured.backup_dir is not None
    database_path = configured.data_dir / "books.db"
    if not database_path.is_file():
        return
    pending = pending_revisions(configured.database_url)
    if not pending:
        return
    logger = logging.getLogger(__name__)
    current = _current_revision(database_path)
    existing = _existing_pre_migration_backup(configured.backup_dir, current)
    if existing is not None:
        # `restart: unless-stopped` plus a migration that keeps failing is a
        # loop, and this ran once per attempt: six identical copies in eleven
        # seconds during Sprint 018's upgrade drill. Nightly retention is scoped
        # by label and deliberately never prunes these, so the loop would fill
        # the disk. The rollback point wanted is the one from before the first
        # attempt anyway.
        logger.info(
            "pre_migration_backup_reused",
            extra={"path": str(existing), "revision": current},
        )
        return
    try:
        result = create_backup(
            database_path=database_path,
            data_dir=configured.data_dir,
            dest=configured.backup_dir,
            label="pre-migration",
        )
    except (BackupError, OSError) as error:
        raise RuntimeError(
            "Refusing to migrate without a backup: "
            f"could not write to {configured.backup_dir} ({error})"
        ) from error
    logger.info(
        "pre_migration_backup_written",
        extra={"path": str(result.path), "pending": pending},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(configured.log_level, scrub=(configured.google_books_api_key,))
        for directory in ("", "covers", "imports"):
            (configured.data_dir / directory).mkdir(parents=True, exist_ok=True)
        if not getattr(app.state, "skip_migrations", False):
            assert configured.database_url is not None
            _back_up_before_migrating(configured)
            upgrade(configured.database_url)
        app.state.engine = create_engine(configured)
        provider_client = create_provider_client()
        app.state.provider_client = provider_client
        app.state.data_dir = configured.data_dir
        app.state.calibre_dir = configured.calibre_dir
        providers: list[Provider] = [
            OpenLibraryProvider(
                provider_client, configured.user_agent_contact or "local@example.invalid"
            )
        ]
        google = GoogleBooksProvider(provider_client, configured.google_books_api_key)
        if google.enabled:
            providers.append(google)
        else:
            # Silently running on one provider is how search lost its Spanish-language
            # coverage without anyone noticing (product spec 4.2, DEC-024).
            logging.getLogger(__name__).warning(
                "GOOGLE_BOOKS_API_KEY is not set; search and enrichment run on Open "
                "Library alone and Spanish-language coverage will be poor"
            )
        app.state.providers = {provider.name: provider for provider in providers}
        # Durable job runner for background enrichment (Sprint 011)
        rate_limiter = RateLimiter(min_interval_seconds=0.5)
        enrichment_handler = EnrichmentHandler(
            app.state.engine,
            app.state.providers,
            rate_limiter=rate_limiter,
            cover_client=provider_client,
            data_dir=configured.data_dir,
        )
        job_runner = JobRunner(
            app.state.engine,
            {"enrich_item": enrichment_handler},
            rate_limiter=rate_limiter,
        )
        app.state.job_runner = job_runner
        # Reclaim expired jobs from a potential crash (best-effort;
        # the table may not exist on a fresh or unmigrated database).
        from datetime import UTC, datetime

        with contextlib.suppress(Exception):
            job_runner.repo.reclaim_expired(datetime.now(UTC))
        # Nothing drove the runner before Sprint 014, so enqueued enrichment never ran.
        worker = asyncio.create_task(job_runner.run_forever())
        try:
            yield
        finally:
            job_runner.stop()
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker
            await provider_client.aclose()
            app.state.engine.dispose()

    app = FastAPI(title="Akasha Book Tracker", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(LibraryError)
    async def library_error(_request: object, error: LibraryError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {"code": error.code, "message": error.message, "details": error.details}
            },
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

    @app.get("/api/health/providers", response_model=ProviderHealth)
    async def provider_health() -> ProviderHealth:
        """Which metadata providers are configured, so the UI can say search is degraded.

        Deliberately separate from readiness: a missing API key must never make the
        application look down (technical spec 8).
        """
        configured_providers = getattr(app.state, "providers", {})
        rows = [
            ProviderStatus(name="openlibrary", available="openlibrary" in configured_providers),
            ProviderStatus(
                name="googlebooks",
                available="googlebooks" in configured_providers,
                reason=(
                    None
                    if "googlebooks" in configured_providers
                    else "GOOGLE_BOOKS_API_KEY is not set"
                ),
            ),
        ]
        return ProviderHealth(providers=rows, degraded=not all(row.available for row in rows))

    app.include_router(library_router)
    app.include_router(providers_router)
    app.include_router(imports_router)
    app.include_router(enrichment_router)

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
