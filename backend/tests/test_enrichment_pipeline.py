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
async def test_a_commit_queues_only_its_own_rows_not_the_whole_library(tmp_path: Path) -> None:
    """Found in the Sprint 014 walkthrough: a four-row import queued seven jobs."""
    app = create_app(settings(tmp_path))
    content = (FIXTURES / "goodreads_valid.csv").read_bytes()
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        engine = app.state.engine
        # An ISBN neither fixture row carries, so it can only be swept up by a
        # library-wide scan.
        stranger = create_item_with_isbn(engine, "Nothing to do with the import", "9788420437989")
        preview = await client.post(
            "/api/import/goodreads/preview",
            files={"file": ("library.csv", content, "text/csv")},
        )
        batch_id = preview.json()["batch_id"]
        await client.post("/api/import/goodreads/commit", json={"batch_id": batch_id})
        jobs = JobRepository(engine).list_batch_jobs(batch_id)
        queued = queued_item_ids(engine)

    assert len(jobs) == 1
    assert stranger not in queued


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
    # A realistic cover shape: `prepare_cover` now rejects provider images too small
    # to use, and the 40x60 stand-in this used to be would be one of them.
    Image.new("RGB", (400, 600), (120, 30, 30)).save(buffer, "JPEG")
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
            metadata={"creators": ["A"], "publisher": "P", "page_count": 10, "description": "d"},
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


@pytest.mark.anyio
async def test_an_album_is_never_queued_for_enrichment(tmp_path: Path) -> None:
    """Seam 6: the album domain declares no background enrichment.

    A Goodreads row starts as little more than an ISBN, which is why books enrich. One
    MusicBrainz release fetch already returns title, date, country, label, catalogue
    number, language, tracks and the credit — so there is nothing left for a job to
    fill, and no ISBN to key one on.
    """
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        book = create_item_with_isbn(engine, "Rayuela", RECORDED_ISBN)
        album = create_item_with_isbn(engine, "Kind of Blue", "9788437604573")
        with engine.begin() as connection:
            connection.execute(text("UPDATE items SET type='album' WHERE id=:id"), {"id": album})

        queued = enqueue_enrichment_backfill(engine)

        with engine.connect() as connection:
            payloads = [
                row[0]
                for row in connection.execute(
                    text("SELECT payload FROM jobs WHERE kind='enrich_item'")
                )
            ]

    assert queued == 1
    assert [json.loads(payload)["item_id"] for payload in payloads] == [book]


# --------------------------------------------------------------------------------------
# Sprint 039: the backfill is keyed on each domain's own identifier and its own
# incompleteness rule (DEC-067 row 3). Everything below used to be books' alone.
# --------------------------------------------------------------------------------------


def create_typed_item(
    engine: Engine,
    title: str,
    item_type: str,
    identifier: tuple[str, str] | None,
    **columns: Any,
) -> int:
    """An item of any domain, with an identifier of any kind."""
    with engine.begin() as connection:
        item_id = connection.execute(
            text(
                "INSERT INTO items"
                "(type,title,year,cover_path,identifiers,metadata,created_at,updated_at) "
                "VALUES(:type,:title,:year,:cover_path,'{}',:metadata,'n','n') RETURNING id"
            ),
            {
                "type": item_type,
                "title": title,
                "year": columns.get("year"),
                "cover_path": columns.get("cover_path"),
                "metadata": json.dumps(columns.get("metadata", {})),
            },
        ).scalar_one()
        if identifier is not None:
            kind, value = identifier
            connection.execute(
                text(
                    "INSERT INTO item_identifiers(item_id,kind,normalized_value,value,"
                    "created_at,updated_at) VALUES(:item,:kind,:value,:value,'n','n')"
                ),
                {"item": item_id, "kind": kind, "value": value},
            )
    return item_id


def queued_payloads(engine: Engine) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT payload FROM jobs WHERE kind='enrich_item' ORDER BY id")
        ).scalars()
        return [json.loads(row) for row in rows]


@pytest.mark.anyio
async def test_each_domain_is_queued_on_its_own_identifier(tmp_path: Path) -> None:
    """A book is found by its ISBN and an anime by its MyAnimeList id.

    Before this, the backfill joined `item_identifiers` on the literal `'isbn'`, so an
    anime could declare enrichment and be queued nothing at all.
    """
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        book = create_typed_item(engine, "A book", "book", ("isbn", RECORDED_ISBN))
        anime = create_typed_item(engine, "An anime", "anime", ("mal", "22199"))

        assert enqueue_enrichment_backfill(engine) == 2
        payloads = {row["item_id"]: row for row in queued_payloads(engine)}

    assert payloads[book]["kind"] == "isbn"
    assert payloads[book]["value"] == RECORDED_ISBN
    assert payloads[anime]["kind"] == "mal"
    assert payloads[anime]["value"] == "22199"


@pytest.mark.anyio
async def test_an_item_carrying_the_wrong_kind_of_identifier_is_not_queued(
    tmp_path: Path,
) -> None:
    """An anime with an ISBN is not something AniList can look up."""
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        create_typed_item(engine, "Mislabelled", "anime", ("isbn", RECORDED_ISBN))
        assert enqueue_enrichment_backfill(engine) == 0


@pytest.mark.anyio
async def test_a_domain_that_does_not_enrich_is_never_queued(tmp_path: Path) -> None:
    """Albums declare `enrichment=None`: one release fetch already returns everything."""
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        create_typed_item(engine, "An album", "album", ("mal", "1"))
        assert enqueue_enrichment_backfill(engine) == 0


@pytest.mark.anyio
async def test_completeness_is_judged_by_each_domain_s_own_fields(tmp_path: Path) -> None:
    """The sharp one. The rule was `publisher`/`page_count`/`description` for every
    domain, and an anime has none of the three — so every anime would have looked
    incomplete for ever and been re-queued on every backfill."""
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        complete = create_typed_item(
            engine,
            "A complete anime",
            "anime",
            ("mal", "22199"),
            year=2014,
            cover_path="covers/1.jpg",
            metadata={"creators": ["White Fox"], "genres": ["Action"], "synopsis": "..."},
        )
        thin = create_typed_item(engine, "A thin anime", "anime", ("mal", "44511"))

        assert enqueue_enrichment_backfill(engine) == 1
        queued = [row["item_id"] for row in queued_payloads(engine)]

    assert queued == [thin]
    assert complete not in queued


@pytest.mark.anyio
async def test_a_book_missing_only_an_anime_field_is_still_complete(tmp_path: Path) -> None:
    """The mirror of the case above: a book has no `synopsis` and never will, and
    judging it by anime's rule would re-queue every book in the library."""
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        create_typed_item(
            engine,
            "A complete book",
            "book",
            ("isbn", RECORDED_ISBN),
            year=1949,
            cover_path="covers/1.jpg",
            metadata={"publisher": "P", "page_count": 10, "description": "d"},
        )
        assert enqueue_enrichment_backfill(engine) == 0
