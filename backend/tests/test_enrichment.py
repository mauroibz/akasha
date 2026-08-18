"""Background enrichment behaviour, proven against recorded provider responses.

These tests deliberately do not mock `fetch_by_isbn`. The Sprint 011 enrichment tests
did, and that is why a wholly dead pipeline passed every gate until Sprint 014.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from recordings import (
    CONFIRMED_ISBN,
    GOOGLE_CONFIRMED,
    GOOGLE_HIT,
    GOOGLE_MISS,
    OPENLIBRARY_HIT,
    OPENLIBRARY_MISS,
    OPENLIBRARY_MISS_CONFIRMED,
    RECORDED_ISBN,
    enrichment_providers,
)
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from book_tracker.application.enrichment import EnrichmentHandler
from book_tracker.application.undo import UndoService
from book_tracker.config import Settings
from book_tracker.database import create_engine as create_sqlalchemy_engine
from book_tracker.infrastructure.jobs import JobRepository
from book_tracker.infrastructure.models import ImportEffectRow, JobRow
from book_tracker.main import create_app
from book_tracker.migrations import upgrade


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url)
    value = create_sqlalchemy_engine(configured)
    yield value
    value.dispose()


def create_item(engine: Engine, title: str, **columns: Any) -> int:
    with engine.begin() as connection:
        return connection.execute(
            text(
                "INSERT INTO items"
                "(title,year,cover_path,identifiers,metadata,created_at,updated_at) "
                "VALUES(:title,:year,:cover_path,'{}',:metadata,'n','n') RETURNING id"
            ),
            {
                "title": title,
                "year": columns.get("year"),
                "cover_path": columns.get("cover_path"),
                "metadata": json.dumps(columns.get("metadata", {})),
            },
        ).scalar_one()


def read_item(engine: Engine, item_id: int) -> Any:
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT title, year, cover_path, metadata FROM items WHERE id=:id"),
            {"id": item_id},
        ).one()


async def run_job(
    engine: Engine, providers: dict[str, Any], item_id: int, isbn: str = RECORDED_ISBN
) -> tuple[str, dict[str, Any]]:
    job_id = JobRepository(engine).enqueue(None, "enrich_item", {"item_id": item_id, "isbn": isbn})
    handler = EnrichmentHandler(engine, providers, rate_limiter=None)
    return job_id, await handler.process(job_id, datetime.now(UTC))


@pytest.mark.anyio
async def test_open_library_hit_fills_empty_fields_from_the_recorded_edition(
    engine: Engine,
) -> None:
    item_id = create_item(engine, "Rayuela")
    async with enrichment_providers(openlibrary=OPENLIBRARY_HIT) as providers:
        _job_id, result = await run_job(engine, providers, item_id)

    assert result["state"] == "succeeded"
    row = read_item(engine, item_id)
    assert row.year == 1984
    assert json.loads(row.metadata)["publisher"] == "Cátedra"
    assert json.loads(row.metadata)["page_count"] == 746


@pytest.mark.anyio
async def test_open_library_miss_falls_back_to_google_books(engine: Engine) -> None:
    """The fallback still works, when the volume can be tied to the requested ISBN."""
    item_id = create_item(engine, "Cien años de soledad")
    async with enrichment_providers(
        openlibrary=OPENLIBRARY_MISS_CONFIRMED, google=GOOGLE_CONFIRMED
    ) as providers:
        _job_id, result = await run_job(engine, providers, item_id, isbn=CONFIRMED_ISBN)

    assert result["state"] == "succeeded"
    assert result["progress"]["provider"] == "googlebooks"
    row = read_item(engine, item_id)
    assert row.year == 2009
    assert json.loads(row.metadata)["publisher"] == "Vintage Espanol"


@pytest.mark.anyio
async def test_an_unverifiable_google_volume_is_not_merged_at_all(engine: Engine) -> None:
    """DEC-044: the fallback answers, but not about the edition that was asked for.

    Before the repair this wrote `Ediciones Catedra S.A.` and 762 pages onto the item
    from a volume whose only identifier is a library barcode.
    """
    item_id = create_item(engine, "Rayuela")
    async with enrichment_providers(openlibrary=OPENLIBRARY_MISS, google=GOOGLE_HIT) as providers:
        _job_id, result = await run_job(engine, providers, item_id)

    assert result["state"] == "failed"
    assert result["error_code"] == "enrichment_no_data"
    assert "cannot be confirmed" in result["error"]
    row = read_item(engine, item_id)
    assert row.year is None
    assert json.loads(row.metadata) == {}


@pytest.mark.anyio
async def test_both_providers_missing_records_a_typed_human_readable_reason(
    engine: Engine,
) -> None:
    item_id = create_item(engine, "Unknown")
    async with enrichment_providers(openlibrary=OPENLIBRARY_MISS, google=GOOGLE_MISS) as providers:
        job_id, result = await run_job(engine, providers, item_id)

    assert result["state"] == "failed"
    assert result["error_code"] == "enrichment_no_data"
    assert f"Open Library has no edition for ISBN {RECORDED_ISBN}" in result["error"]
    assert "Google Books" in result["error"]
    assert read_item(engine, item_id).year is None
    assert JobRepository(engine).get_job(job_id)["state"] == "queued"


@pytest.mark.anyio
async def test_a_failed_job_exposes_the_typed_reason_through_the_jobs_endpoint(
    tmp_path: Path,
) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        engine = app.state.engine
        item_id = create_item(engine, "Unknown")
        async with enrichment_providers(
            openlibrary=OPENLIBRARY_MISS, google=GOOGLE_MISS
        ) as providers:
            job_id = JobRepository(engine).enqueue(
                None, "enrich_item", {"item_id": item_id, "isbn": RECORDED_ISBN}
            )
            runner = app.state.job_runner
            runner.handlers["enrich_item"] = EnrichmentHandler(engine, providers, rate_limiter=None)
            await runner.tick(datetime.now(UTC))

        response = await client.get(f"/api/import/jobs/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["error_code"] == "enrichment_no_data"
    assert f"ISBN {RECORDED_ISBN}" in body["error"]


@pytest.mark.anyio
async def test_google_books_absence_is_reported_as_unconfigured_not_as_an_error(
    engine: Engine,
) -> None:
    item_id = create_item(engine, "Unknown")
    async with enrichment_providers(openlibrary=OPENLIBRARY_MISS) as providers:
        _job_id, result = await run_job(engine, providers, item_id)

    assert result["state"] == "failed"
    assert result["error_code"] == "enrichment_no_data"
    assert "Google Books is not configured" in result["error"]


@pytest.mark.anyio
async def test_enrichment_never_overwrites_a_populated_field(engine: Engine) -> None:
    item_id = create_item(
        engine,
        "My Rayuela",
        year=1950,
        metadata={"publisher": "Manual Press", "creators": ["Someone Else"]},
    )
    async with enrichment_providers(openlibrary=OPENLIBRARY_HIT) as providers:
        await run_job(engine, providers, item_id)

    row = read_item(engine, item_id)
    assert row.title == "My Rayuela"
    assert row.year == 1950
    metadata = json.loads(row.metadata)
    assert metadata["publisher"] == "Manual Press"
    assert metadata["creators"] == ["Someone Else"]
    # Fields that were empty are still filled.
    assert metadata["page_count"] == 746


@pytest.mark.anyio
async def test_a_verified_google_volume_still_only_fills_empty_fields(engine: Engine) -> None:
    """DEC-008 across the path Sprint 020 changed, not only the Open Library one."""
    item_id = create_item(
        engine,
        "Cien años de soledad",
        year=1967,
        metadata={"publisher": "Editorial Sudamericana"},
    )
    async with enrichment_providers(
        openlibrary=OPENLIBRARY_MISS_CONFIRMED, google=GOOGLE_CONFIRMED
    ) as providers:
        _job_id, result = await run_job(engine, providers, item_id, isbn=CONFIRMED_ISBN)

    assert result["state"] == "succeeded"
    row = read_item(engine, item_id)
    # The user's first edition survives the 2009 reprint the provider answered with.
    assert row.year == 1967
    metadata = json.loads(row.metadata)
    assert metadata["publisher"] == "Editorial Sudamericana"
    assert metadata["page_count"] == 498


@pytest.mark.anyio
async def test_enrichment_records_an_import_effect_so_undo_covers_it(tmp_path: Path) -> None:
    from test_jobs import _create_committed_batch  # shared batch scaffolding

    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        item_id = create_item(engine, "Rayuela")
        batch_id = _create_committed_batch(engine)
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE import_records SET matched_item_id=:item WHERE batch_id=:batch"),
                {"item": item_id, "batch": batch_id},
            )
        job_id = JobRepository(engine).enqueue(
            batch_id, "enrich_item", {"item_id": item_id, "isbn": RECORDED_ISBN}
        )
        async with enrichment_providers(openlibrary=OPENLIBRARY_HIT) as providers:
            handler = EnrichmentHandler(engine, providers, rate_limiter=None)
            assert (await handler.process(job_id, datetime.now(UTC)))["state"] == "succeeded"

        with Session(engine) as session:
            effects = [
                effect
                for effect in session.scalars(
                    select(ImportEffectRow).where(ImportEffectRow.batch_id == batch_id)
                )
                if effect.effect_type == "fill_empty"
            ]
        assert effects
        for effect in effects:
            assert json.loads(effect.before_values) != json.loads(effect.after_values)


@pytest.mark.anyio
async def test_a_late_job_from_an_undone_batch_cancels_without_calling_a_provider(
    tmp_path: Path,
) -> None:
    from test_jobs import _create_committed_batch

    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        item_id = create_item(engine, "Rayuela")
        batch_id = _create_committed_batch(engine)
        UndoService(engine).undo(batch_id)
        job_id = JobRepository(engine).enqueue(
            batch_id, "enrich_item", {"item_id": item_id, "isbn": RECORDED_ISBN}
        )
        # `forbid_calls` makes any provider request an assertion failure, which is a
        # stronger statement than asserting on a mock's call count.
        async with enrichment_providers(forbid_calls=True) as providers:
            handler = EnrichmentHandler(engine, providers, rate_limiter=None)
            result = await handler.process(job_id, datetime.now(UTC))

        assert result["state"] == "cancelled"
        with Session(engine) as session:
            assert session.get(JobRow, job_id).state == "cancelled"
