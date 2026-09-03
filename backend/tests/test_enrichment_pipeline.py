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
        # Genuinely nothing left to ask for (DEC-130): a source recorded too, not
        # only complete metadata — otherwise this fixture would itself prove the
        # opposite of what it is meant to.
        add_source(engine, complete)

        assert enqueue_enrichment_backfill(engine) == 1
        queued = queued_item_ids(engine)

    assert queued == [empty]
    assert no_isbn not in queued
    assert complete not in queued


@pytest.mark.anyio
async def test_backfill_reaches_a_complete_item_that_was_never_given_a_source(
    tmp_path: Path,
) -> None:
    """DEC-130's retroactive path: an item enriched before that fix — full metadata,
    cover, and year, but zero `item_sources` rows — could never be reached by the
    ordinary completeness scan above, and would stay permanently unrefreshable
    without this. `queued` is asserted rather than the ordinary-complete item's own
    exclusion, since that is already this file's first backfill test."""
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        stuck = create_item_with_isbn(
            engine,
            "Obsession",
            "9780141187761",
            year=1949,
            cover_path="covers/9.jpg",
            metadata={"creators": ["A"], "publisher": "P", "page_count": 10, "description": "d"},
        )
        assert enqueue_enrichment_backfill(engine) == 1
        assert queued_item_ids(engine) == [stuck]


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


def add_source(engine: Engine, item_id: int, source: str = "openlibrary") -> None:
    """A provider source already recorded (DEC-130) — what a search-added item
    always has and an imported one, before this fix, never did. A "complete"
    fixture needs one too, or it only proves the old, narrower rule."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO item_sources(item_id,source,source_id,is_primary,"
                "created_at,updated_at) VALUES(:item,:source,:item,1,'n','n')"
            ),
            {"item": item_id, "source": source},
        )


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
    """Every registered domain declares an `EnrichmentSpec` as of Sprint 064 (albums
    were the last one), so this is proven against a type outside every registered
    domain rather than against any one domain's declaration — the schema enforces
    no CHECK on `items.type` (DEC-057's line), so a stale or mistyped row is real."""
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        create_typed_item(engine, "A widget", "widget", ("mal", "1"))
        assert enqueue_enrichment_backfill(engine) == 0


@pytest.mark.anyio
async def test_a_spotify_identified_album_is_queued_and_a_search_added_one_is_not(
    tmp_path: Path,
) -> None:
    """AC4: the whole reason `enrichment=None` was right until Sprint 064. A
    search-added album carries no `spotify` identifier at all, so it must never be
    queued — asserted rather than assumed, since it is the one behaviour this
    sprint's change could most easily have broken."""
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        imported = create_typed_item(engine, "Plastic Beach", "album", ("spotify", "abc123"))
        searched = create_typed_item(engine, "Kind of Blue", "album", None)

        assert enqueue_enrichment_backfill(engine) == 1
        payloads = {row["item_id"]: row for row in queued_payloads(engine)}

    assert payloads[imported]["kind"] == "spotify"
    assert payloads[imported]["value"] == "abc123"
    assert searched not in payloads


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
        add_source(engine, complete, "anilist")
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
        book = create_typed_item(
            engine,
            "A complete book",
            "book",
            ("isbn", RECORDED_ISBN),
            year=1949,
            cover_path="covers/1.jpg",
            metadata={"publisher": "P", "page_count": 10, "description": "d"},
        )
        add_source(engine, book)
        assert enqueue_enrichment_backfill(engine) == 0


# --------------------------------------------------------------------------------------
# Movies: a key that is neither an ISBN nor a MyAnimeList id (Sprint 046)
# --------------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_movie_is_queued_on_its_letterboxd_film(tmp_path: Path) -> None:
    """The third distinct enrichment key. A film's export carries no ISBN and no
    MyAnimeList id; what it carries is a Letterboxd film (DEC-067 row 3)."""
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        movie = create_typed_item(engine, "Suspiria", "movie", ("letterboxd", "suspiria"))

        assert enqueue_enrichment_backfill(engine) == 1
        payloads = {row["item_id"]: row for row in queued_payloads(engine)}

    assert payloads[movie]["kind"] == "letterboxd"
    assert payloads[movie]["value"] == "suspiria"


@pytest.mark.anyio
async def test_a_movie_known_only_by_its_imdb_id_is_queued_on_that(tmp_path: Path) -> None:
    """This asserted the opposite until Sprint 053, and the opposite was the defect.

    The movie domain declared `letterboxd` alone, so a film that arrived from an IMDb
    export — carrying a `tt` id and no Letterboxd URI, because IMDb does not publish
    one — was never queued for anything: no poster, no genres, no runtime, and every
    gate green. The domain declares both keys now (DEC-113).
    """
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        movie = create_typed_item(engine, "Untitled", "movie", ("imdb", "tt0076786"))
        assert enqueue_enrichment_backfill(engine) == 1
        payloads = {row["item_id"]: row for row in queued_payloads(engine)}

    assert payloads[movie]["kind"] == "imdb"
    assert payloads[movie]["value"] == "tt0076786"


@pytest.mark.anyio
async def test_a_movie_with_neither_key_is_never_queued(tmp_path: Path) -> None:
    """The negative that still holds: a film added by hand and matched to nothing has
    nothing to look it up by, and a job with no key is a job that can only fail."""
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        create_typed_item(engine, "Untitled", "movie", ("tmdb", "1396"))
        assert enqueue_enrichment_backfill(engine) == 0


@pytest.mark.anyio
async def test_movie_enrichment_fills_only_what_is_empty(tmp_path: Path) -> None:
    """Against the real recorded Wikidata boundary, not a mock of the fetch under test.

    The owner's own title, year and edits survive: enrichment is a filler of blanks and
    never a corrector of somebody's library.
    """
    from recordings import recording  # noqa: PLC0415
    from test_wikidata_provider import FETCH_1977, claim_key, wikidata_route_key  # noqa: PLC0415

    from book_tracker.domains.movie.providers import WikidataMovieProvider  # noqa: PLC0415
    from book_tracker.infrastructure.providers import create_provider_client  # noqa: PLC0415

    routes = {
        claim_key("P6127", "suspiria"): (200, recording("wikidata_search_p6127_suspiria.json")),
        **FETCH_1977,
    }
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        item_id = create_typed_item(
            engine,
            # The skeletal record a Letterboxd export creates, with one field already
            # written by hand so the fill-empty-only rule has something to respect.
            "Suspiria (mi copia)",
            "movie",
            ("letterboxd", "suspiria"),
            metadata={"description": "La que vi en el cine club"},
        )
        client = create_provider_client(replay(routes, key=wikidata_route_key))
        handler = EnrichmentHandler(
            engine,
            {"wikidata": WikidataMovieProvider(client, "test@example.invalid")},
            rate_limiter=None,
            data_dir=tmp_path,
        )
        job_id = JobRepository(engine).enqueue(
            None, "enrich_item", {"item_id": item_id, "kind": "letterboxd", "value": "suspiria"}
        )
        assert (await handler.process(job_id, datetime.now(UTC)))["state"] == "succeeded"
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT title, year, metadata FROM items WHERE id = :id"), {"id": item_id}
            ).one()
            sources = connection.execute(
                text("SELECT source, source_id, is_primary FROM item_sources WHERE item_id = :id"),
                {"id": item_id},
            ).all()
        await client.aclose()

    metadata = json.loads(row.metadata)
    assert row.title == "Suspiria (mi copia)"
    assert row.year == 1977
    assert metadata["description"] == "La que vi en el cine club"
    assert metadata["creators"] == ["Dario Argento"]
    assert metadata["runtime"] == 94
    assert "cine de terror" in metadata["genres"]
    # The import path that created this item (Letterboxd) has no provider of its
    # own to record a source from, so it reached enrichment with none at all.
    # Left unrecorded, the item would enrich successfully here and then fail
    # every later refresh or cover-fetch with "no provider source" -- exactly
    # the gap a real Letterboxd import surfaced.
    assert [(s.source, s.is_primary) for s in sources] == [("wikidata", 1)]
    assert sources[0].source_id


@pytest.mark.anyio
async def test_an_item_that_already_has_a_source_is_not_given_a_second_one(
    tmp_path: Path,
) -> None:
    """A source recorded by any earlier path is left alone.

    Guarded on "no source at all", not on "this job's own provider" — an item
    that already carries the primary source a search-add or an earlier
    enrichment recorded must not have that pick disturbed just because a
    second provider also happens to resolve it.
    """
    from recordings import recording  # noqa: PLC0415
    from test_wikidata_provider import FETCH_1977, claim_key, wikidata_route_key  # noqa: PLC0415

    from book_tracker.domains.movie.providers import WikidataMovieProvider  # noqa: PLC0415
    from book_tracker.infrastructure.providers import create_provider_client  # noqa: PLC0415

    routes = {
        claim_key("P6127", "suspiria"): (200, recording("wikidata_search_p6127_suspiria.json")),
        **FETCH_1977,
    }
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        item_id = create_typed_item(
            engine, "Suspiria (mi copia)", "movie", ("letterboxd", "suspiria")
        )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO item_sources(item_id,source,source_id,is_primary,"
                    "created_at,updated_at) VALUES(:item,'cinemeta','tt0076786',1,'n','n')"
                ),
                {"item": item_id},
            )
        client = create_provider_client(replay(routes, key=wikidata_route_key))
        handler = EnrichmentHandler(
            engine,
            {"wikidata": WikidataMovieProvider(client, "test@example.invalid")},
            rate_limiter=None,
            data_dir=tmp_path,
        )
        job_id = JobRepository(engine).enqueue(
            None, "enrich_item", {"item_id": item_id, "kind": "letterboxd", "value": "suspiria"}
        )
        assert (await handler.process(job_id, datetime.now(UTC)))["state"] == "succeeded"
        with engine.connect() as connection:
            sources = connection.execute(
                text("SELECT source, source_id, is_primary FROM item_sources WHERE item_id = :id"),
                {"id": item_id},
            ).all()
        await client.aclose()

    assert [(s.source, s.source_id, s.is_primary) for s in sources] == [
        ("cinemeta", "tt0076786", 1)
    ]


@pytest.mark.anyio
async def test_a_movie_provider_miss_is_a_typed_outcome_and_not_a_crash(tmp_path: Path) -> None:
    """A Letterboxd film Wikidata does not carry leaves the item exactly as it was."""
    from recordings import recording  # noqa: PLC0415
    from test_wikidata_provider import claim_key, wikidata_route_key  # noqa: PLC0415

    from book_tracker.domains.movie.providers import WikidataMovieProvider  # noqa: PLC0415
    from book_tracker.infrastructure.providers import create_provider_client  # noqa: PLC0415

    routes = {
        claim_key("P6127", "this-film-does-not-exist-xyz"): (
            200,
            recording("wikidata_search_p6127_no_match.json"),
        )
    }
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        item_id = create_typed_item(
            engine, "Something", "movie", ("letterboxd", "this-film-does-not-exist-xyz")
        )
        client = create_provider_client(replay(routes, key=wikidata_route_key))
        handler = EnrichmentHandler(
            engine,
            {"wikidata": WikidataMovieProvider(client, "test@example.invalid")},
            rate_limiter=None,
            data_dir=tmp_path,
        )
        job_id = JobRepository(engine).enqueue(
            None,
            "enrich_item",
            {
                "item_id": item_id,
                "kind": "letterboxd",
                "value": "this-film-does-not-exist-xyz",
            },
        )
        result = await handler.process(job_id, datetime.now(UTC))
        with engine.connect() as connection:
            title = connection.execute(
                text("SELECT title FROM items WHERE id = :id"), {"id": item_id}
            ).scalar_one()
        await client.aclose()

    assert title == "Something"
    assert result["state"] == "failed"
    # The reason is written for a person reading a failed job, and names the film it
    # could not find rather than leaking a provider exception.
    assert "this-film-does-not-exist-xyz" in str(result["error"])
    assert "Wikidata" in str(result["error"])


# ----------------------------------------------------------------------------------
# Sprint 055, deliverable 2: the cover/year conditions belong to the declaration.
# ----------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_domain_that_does_not_want_a_cover_is_not_requeued_without_one(
    tmp_path: Path,
) -> None:
    """DEC-100's first recorded defect: a null `cover_path` counted as "worth a
    lookup" in every domain regardless of what the domain's providers can
    return. Movies are the recorded case — they shipped coverless because the
    Wikidata adapter carries no poster, so every movie sat re-queueable for ever
    against a provider that would never answer. Post-Sprint-048 the movie
    provider does carry posters, so every enriching domain today *can* supply a
    cover; the fix makes the condition a declaration (`wants_cover`) rather than
    an assumption, and the guard test is the unit seam: a domain that opts out
    is never selected for a missing cover."""
    from dataclasses import replace as dc_replace

    from book_tracker.application.enrichment import _backfillable_items
    from book_tracker.domain.registry import DOMAINS
    from book_tracker.domain.spec import EnrichmentSpec

    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        # A book row that has everything except a cover: complete by every other
        # measure, coverless on purpose for this test.
        coverless = create_item_with_isbn(
            engine,
            "Coverless",
            RECORDED_ISBN,
            year=1949,
            metadata={"creators": ["A"], "publisher": "P", "page_count": 10, "description": "d"},
        )

        # The declaration as it ships: a missing cover counts.
        assert enqueue_enrichment_backfill(engine) == 1
        assert [row["item_id"] for row in queued_payloads(engine)] == [coverless]

        # The same domain opting out of the cover condition: the identical row
        # is no longer worth a lookup, and nothing is queued.
        book = DOMAINS["book"]
        opted_out = dc_replace(
            book,
            enrichment=dc_replace(
                book.enrichment
                or EnrichmentSpec(
                    identity_kinds=("isbn",),
                    provider_order=("openlibrary",),
                    completeness_fields=(),
                ),
                wants_cover=False,
            ),
        )
        DOMAINS["book"] = opted_out
        try:
            from book_tracker.infrastructure.models import JobRow  # noqa: F401

            assert _backfillable_items(engine) == []
        finally:
            DOMAINS["book"] = book


@pytest.mark.anyio
async def test_a_domain_that_does_not_want_a_year_is_not_requeued_without_one(
    tmp_path: Path,
) -> None:
    """The sharper half of the same defect: no provider contract guarantees a
    year, so a domain whose rows legitimately carry none would be re-queued on
    every backfill for ever. A book with no year, complete on the domain's own
    fields, is the case."""
    from dataclasses import replace as dc_replace

    from book_tracker.application.enrichment import _backfillable_items
    from book_tracker.domain.registry import DOMAINS
    from book_tracker.domain.spec import EnrichmentSpec

    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        engine = app.state.engine
        # No year, no cover needed either (both supplied), complete otherwise.
        yearless = create_item_with_isbn(
            engine,
            "Yearless",
            RECORDED_ISBN,
            cover_path="covers/7.jpg",
            metadata={"creators": ["A"], "publisher": "P", "page_count": 10, "description": "d"},
        )
        assert enqueue_enrichment_backfill(engine) == 1
        assert [row["item_id"] for row in queued_payloads(engine)] == [yearless]

        book = DOMAINS["book"]
        base = book.enrichment or EnrichmentSpec(
            identity_kinds=("isbn",), provider_order=("openlibrary",), completeness_fields=()
        )
        DOMAINS["book"] = dc_replace(book, enrichment=dc_replace(base, wants_year=False))
        try:
            assert _backfillable_items(engine) == []
        finally:
            DOMAINS["book"] = book
