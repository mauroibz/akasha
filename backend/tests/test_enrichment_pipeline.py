"""The enrichment pipeline end to end: enqueue, drain, fill, backfill.

Before Sprint 014 nothing in production code ever called `JobRepository.enqueue`, and
nothing ever called `JobRunner.tick`. Every part of this file exists because the queue
had no producer and no consumer, so no enrichment job had ever run.
"""

from __future__ import annotations

import asyncio
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from PIL import Image
from recordings import OPENLIBRARY_HIT, RECORDED_ISBN, enrichment_providers, replay
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from book_tracker.application.enrichment import EnrichmentHandler, enqueue_enrichment_backfill
from book_tracker.config import Settings
from book_tracker.infrastructure.jobs import JobRepository
from book_tracker.infrastructure.models import JobRow
from book_tracker.main import create_app

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")


def create_item_with_isbn(engine: Engine, title: str, isbn: str | None, **columns: Any) -> int:
    with engine.begin() as connection:
        item_id = connection.execute(
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
        if isbn:
            connection.execute(
                text(
                    "INSERT INTO item_identifiers"
                    "(item_id,kind,normalized_value,value,created_at,updated_at) "
                    "VALUES(:item,'isbn',:isbn,:isbn,'n','n')"
                ),
                {"item": item_id, "isbn": isbn},
            )
        return item_id


def queued_item_ids(engine: Engine) -> list[int]:
    with Session(engine) as session:
        return [
            json.loads(row.payload)["item_id"]
            for row in session.scalars(
                select(JobRow).where(JobRow.kind == "enrich_item").order_by(JobRow.created_at)
            )
        ]


# --------------------------------------------------------------------------------------
# The queue has a producer
# --------------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_committing_an_import_enqueues_enrichment_for_rows_with_an_isbn(
    tmp_path: Path,
) -> None:
    app = create_app(settings(tmp_path))
    content = (FIXTURES / "goodreads_valid.csv").read_bytes()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        preview = await client.post(
            "/api/import/goodreads/preview",
            files={"file": ("library.csv", content, "text/csv")},
        )
        batch_id = preview.json()["batch_id"]
        commit = await client.post("/api/import/goodreads/commit", json={"batch_id": batch_id})
        assert commit.status_code == 200

        jobs = JobRepository(app.state.engine).list_batch_jobs(batch_id)

    assert [job["kind"] for job in jobs] == ["enrich_item"]
    assert jobs[0]["state"] == "queued"


@pytest.mark.anyio
async def test_re_committing_the_same_batch_does_not_duplicate_jobs(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    content = (FIXTURES / "goodreads_valid.csv").read_bytes()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        preview = await client.post(
            "/api/import/goodreads/preview",
            files={"file": ("library.csv", content, "text/csv")},
        )
        batch_id = preview.json()["batch_id"]
        await client.post("/api/import/goodreads/commit", json={"batch_id": batch_id})
        await client.post("/api/import/goodreads/commit", json={"batch_id": batch_id})
        jobs = JobRepository(app.state.engine).list_batch_jobs(batch_id)

    assert len(jobs) == 1


# --------------------------------------------------------------------------------------
# The queue has a consumer
# --------------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_the_lifespan_drains_queued_jobs_without_anyone_calling_tick(
    tmp_path: Path,
) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        item_id = create_item_with_isbn(engine, "Rayuela", RECORDED_ISBN)
        async with enrichment_providers(openlibrary=OPENLIBRARY_HIT) as providers:
            app.state.job_runner.handlers["enrich_item"] = EnrichmentHandler(
                engine, providers, rate_limiter=None
            )
            job_id = JobRepository(engine).enqueue(
                None, "enrich_item", {"item_id": item_id, "isbn": RECORDED_ISBN}
            )
            for _ in range(100):
                if JobRepository(engine).get_job(job_id)["state"] == "succeeded":
                    break
                await asyncio.sleep(0.05)

        assert JobRepository(engine).get_job(job_id)["state"] == "succeeded"
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT year FROM items WHERE id=:id"), {"id": item_id}
                ).scalar_one()
                == 1984
            )


# --------------------------------------------------------------------------------------
# Covers
# --------------------------------------------------------------------------------------


def jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 60), (120, 30, 30)).save(buffer, "JPEG")
    return buffer.getvalue()


@pytest.mark.anyio
async def test_enrichment_installs_a_missing_cover_and_records_the_path(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        item_id = create_item_with_isbn(engine, "Rayuela", RECORDED_ISBN)
        cover_transport = replay(
            {
                "/b/id/15103185-L.jpg": (
                    200,
                    jpeg_bytes(),
                    {"content-type": "image/jpeg"},
                )
            }
        )
        async with (
            enrichment_providers(openlibrary=OPENLIBRARY_HIT) as providers,
            httpx.AsyncClient(transport=cover_transport) as cover_client,
        ):
            handler = EnrichmentHandler(
                engine,
                providers,
                rate_limiter=None,
                cover_client=cover_client,
                data_dir=tmp_path,
            )
            job_id = JobRepository(engine).enqueue(
                None, "enrich_item", {"item_id": item_id, "isbn": RECORDED_ISBN}
            )
            result = await handler.process(job_id, datetime.now(UTC))

        assert result["state"] == "succeeded"
        assert "cover" in result["progress"]["filled"]
        with engine.connect() as connection:
            cover_path = connection.execute(
                text("SELECT cover_path FROM items WHERE id=:id"), {"id": item_id}
            ).scalar_one()
        assert cover_path == f"covers/{item_id}.jpg"
        assert (tmp_path / "covers" / f"{item_id}.jpg").is_file()


@pytest.mark.anyio
async def test_enrichment_leaves_an_existing_cover_alone(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        item_id = create_item_with_isbn(
            engine, "Rayuela", RECORDED_ISBN, cover_path="covers/mine.jpg"
        )

        def refuse(request: httpx.Request) -> httpx.Response:
            raise AssertionError(f"cover was re-downloaded from {request.url}")

        async with (
            enrichment_providers(openlibrary=OPENLIBRARY_HIT) as providers,
            httpx.AsyncClient(transport=httpx.MockTransport(refuse)) as cover_client,
        ):
            handler = EnrichmentHandler(
                engine, providers, rate_limiter=None, cover_client=cover_client, data_dir=tmp_path
            )
            job_id = JobRepository(engine).enqueue(
                None, "enrich_item", {"item_id": item_id, "isbn": RECORDED_ISBN}
            )
            assert (await handler.process(job_id, datetime.now(UTC)))["state"] == "succeeded"

        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT cover_path FROM items WHERE id=:id"), {"id": item_id}
                ).scalar_one()
                == "covers/mine.jpg"
            )


# --------------------------------------------------------------------------------------
# Backfill
# --------------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_backfill_selects_only_items_that_an_isbn_lookup_could_still_help(
    tmp_path: Path,
) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        empty = create_item_with_isbn(engine, "Empty", RECORDED_ISBN)
        no_isbn = create_item_with_isbn(engine, "No ISBN", None)
        complete = create_item_with_isbn(
            engine,
            "Complete",
            "9780141187761",
            year=1949,
            cover_path="covers/9.jpg",
            metadata={"authors": ["A"], "publisher": "P", "page_count": 10, "description": "d"},
        )

        assert enqueue_enrichment_backfill(engine) == 1
        queued = queued_item_ids(engine)

    assert queued == [empty]
    assert no_isbn not in queued
    assert complete not in queued


@pytest.mark.anyio
async def test_backfill_does_not_queue_an_item_that_is_already_pending(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        create_item_with_isbn(engine, "Empty", RECORDED_ISBN)
        assert enqueue_enrichment_backfill(engine) == 1
        assert enqueue_enrichment_backfill(engine) == 0
        assert len(queued_item_ids(engine)) == 1


@pytest.mark.anyio
async def test_backfill_fills_empty_metadata_without_touching_entries_or_edits(
    tmp_path: Path,
) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        item_id = create_item_with_isbn(
            engine, "My own title", RECORDED_ISBN, metadata={"publisher": "Manual Press"}
        )
        with engine.begin() as connection:
            entry_id = connection.execute(
                text(
                    "INSERT INTO entries"
                    "(user_id,item_id,status,score,notes,date_added,reread_count,"
                    "score_provisional,created_at,updated_at) "
                    "VALUES(1,:item,'read',9,'my notes','n',0,0,'n','n') RETURNING id"
                ),
                {"item": item_id},
            ).scalar_one()

        assert enqueue_enrichment_backfill(engine) == 1
        job_id = _first_job_id(engine)
        async with enrichment_providers(openlibrary=OPENLIBRARY_HIT) as providers:
            handler = EnrichmentHandler(engine, providers, rate_limiter=None)
            assert (await handler.process(job_id, datetime.now(UTC)))["state"] == "succeeded"

        with engine.connect() as connection:
            item = connection.execute(
                text("SELECT title, year, metadata FROM items WHERE id=:id"), {"id": item_id}
            ).one()
            entry = connection.execute(
                text("SELECT status, score, notes FROM entries WHERE id=:id"), {"id": entry_id}
            ).one()

    assert item.title == "My own title"
    assert item.year == 1984
    metadata = json.loads(item.metadata)
    assert metadata["publisher"] == "Manual Press"
    assert metadata["page_count"] == 746
    assert (entry.status, entry.score, entry.notes) == ("read", 9, "my notes")


def _first_job_id(engine: Engine) -> str:
    with Session(engine) as session:
        return session.scalars(select(JobRow).order_by(JobRow.created_at)).first().id


@pytest.mark.anyio
async def test_backfill_endpoint_reports_how_many_items_were_queued(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        create_item_with_isbn(app.state.engine, "Empty", RECORDED_ISBN)
        response = await client.post("/api/enrichment/backfill")

    assert response.status_code == 202
    assert response.json() == {"queued": 1}
