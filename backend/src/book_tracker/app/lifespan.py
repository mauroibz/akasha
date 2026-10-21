"""Start-up and shutdown: migrations, the engine, providers and the job runner."""

import asyncio
import contextlib
import logging
import sqlite3
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from book_tracker.api.auth import (
    LoginRateLimiter,
    bootstrap_admin,
)
from book_tracker.app.providers import build_provider_catalog
from book_tracker.application.enrichment import EnrichmentHandler
from book_tracker.application.import_search import ImportSearchHandler
from book_tracker.backup import BackupError, create_backup, read_manifest
from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.infrastructure.jobs import JobRunner, RateLimiter
from book_tracker.infrastructure.providers import create_provider_client
from book_tracker.infrastructure.quota import ProviderQuota
from book_tracker.logging import configure_logging
from book_tracker.migrations import pending_revisions, upgrade


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


def back_up_before_migrating(configured: Settings) -> None:
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


def make_lifespan(configured: Settings) -> Callable[[FastAPI], Any]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(configured.log_level, scrub=(configured.google_books_api_key,))
        for directory in ("", "covers", "imports", "attachments"):
            (configured.data_dir / directory).mkdir(parents=True, exist_ok=True)
        if not getattr(app.state, "skip_migrations", False):
            assert configured.database_url is not None
            back_up_before_migrating(configured)
            upgrade(configured.database_url)
        app.state.engine = create_engine(configured)
        app.state.auth = configured.auth
        app.state.cookie_secure = configured.cookie_secure
        app.state.trusted_proxy_peers = configured.trusted_proxy_peers
        app.state.trusted_proxy_header = configured.trusted_proxy_header
        app.state.trusted_header_autocreate = configured.trusted_header_autocreate
        app.state.login_limiter = LoginRateLimiter(
            configured.login_max_failures, configured.login_window_seconds
        )
        if (
            configured.auth == "on"
            and configured.admin_username is not None
            and configured.admin_password is not None
        ):
            bootstrap_admin(app.state.engine, configured.admin_username, configured.admin_password)
        provider_client = create_provider_client()
        app.state.provider_client = provider_client
        app.state.data_dir = configured.data_dir
        app.state.attachment_max_bytes = configured.attachment_max_bytes
        app.state.min_free_bytes = configured.min_free_bytes
        app.state.calibre_dir = configured.calibre_dir
        catalog = build_provider_catalog(provider_client, configured)
        app.state.provider_catalog = {provider.name: provider for provider in catalog}
        # What search, add and enrichment actually reach. A provider missing its
        # configuration is disabled, not failed (technical spec 6.2).
        app.state.providers = {
            name: provider
            for name, provider in app.state.provider_catalog.items()
            if getattr(provider, "enabled", True)
        }
        # Durable job runner for background enrichment (Sprint 011)
        rate_limiter = RateLimiter(min_interval_seconds=0.5)
        # Daily budgets, provider-agnostic (DEC-045). Enrichment is gated by them;
        # interactive search deliberately is not, so the last of a day's quota goes to
        # a search someone is waiting for rather than to background work.
        app.state.provider_quota = ProviderQuota(
            app.state.engine, limits=configured.provider_daily_limits
        )
        enrichment_handler = EnrichmentHandler(
            app.state.engine,
            app.state.providers,
            rate_limiter=rate_limiter,
            quota=app.state.provider_quota,
            cover_client=provider_client,
            data_dir=configured.data_dir,
        )
        search_handler = ImportSearchHandler(
            app.state.engine,
            app.state.providers,
            rate_limiter=rate_limiter,
            quota=app.state.provider_quota,
        )
        job_runner = JobRunner(
            app.state.engine,
            {"enrich_item": enrichment_handler, "search_import_rows": search_handler},
            rate_limiter=rate_limiter,
            data_dir=configured.data_dir,
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

    return lifespan
