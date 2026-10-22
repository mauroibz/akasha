"""Episodes and chapters as optional marks on the entry (Sprint 107, DEC-171).

A mark is which episode or chapter is done, and nothing more: no status, score or date
of its own, and no row anywhere but its entry (DEC-077 stays closed). The marks drive the
existing `progress` count. The outline they are drawn against is declared by the domain
(`ProgressSpec.parts_field`, else one part of `total_field`), and arrives from a provider
only when asked: on add, on enrichment, on refresh, or through the outline action.

Provider behaviour is proven against recordings captured live on 2026-10-22 (DEC-025).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import httpx
import pytest
from recordings import recording, replay
from sqlalchemy import text

from book_tracker.config import Settings
from book_tracker.domain.registry import DOMAINS
from book_tracker.domain.spec import (
    InvalidProgress,
    resolve_outline,
    validate_entry_values,
    validate_progress_marks,
)
from book_tracker.domains.book.providers import OpenLibraryProvider
from book_tracker.domains.series.tvmaze import TvmazeSeriesProvider
from book_tracker.infrastructure.providers import create_provider_client
from book_tracker.main import create_app
from book_tracker.migrations import upgrade

pytestmark = pytest.mark.anyio

SERIES = DOMAINS["series"]
ANIME = DOMAINS["anime"]
BOOK = DOMAINS["book"]
MOVIE = DOMAINS["movie"]
ALBUM = DOMAINS["album"]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# -- the declarations -------------------------------------------------------------------


def test_series_declares_its_seasons_and_books_their_chapters() -> None:
    assert SERIES.progress is not None
    assert SERIES.progress.parts_field == "season_episodes"
    assert BOOK.progress is not None
    assert (BOOK.progress.label, BOOK.progress.unit_label) == ("Chapters read", "chapter")
    assert BOOK.progress.total_field == "chapters"
    assert ANIME.progress is not None and ANIME.progress.parts_field is None
    assert MOVIE.progress is None and ALBUM.progress is None


def test_a_status_that_stops_partway_is_declared_not_named() -> None:
    """The detail page asks how far you got when an entry is dropped (owner, 2026-10-22).

    Which status means "stopped partway" is each domain's declaration, as `in_progress`
    and `planned` are, so the screen never names `dropped`.
    """
    for domain in (SERIES, ANIME, BOOK):
        abandoned = [status.value for status in domain.statuses if status.abandoned]
        assert abandoned == ["dropped"], domain.item_type
    for domain in (MOVIE, ALBUM):
        assert not any(status.abandoned for status in domain.statuses)


# -- the outline ------------------------------------------------------------------------


def test_the_outline_is_the_parts_field_when_present() -> None:
    metadata = {
        "episodes": 62,
        "season_episodes": [{"season": 1, "episodes": 7}, {"season": 2, "episodes": 13}],
    }
    assert resolve_outline(SERIES, metadata) == [
        {"part": 1, "size": 7},
        {"part": 2, "size": 13},
    ]


def test_without_a_parts_field_the_outline_is_one_part_of_the_total() -> None:
    assert resolve_outline(SERIES, {"episodes": 62}) == [{"part": 1, "size": 62}]
    assert resolve_outline(ANIME, {"episodes": 12}) == [{"part": 1, "size": 12}]
    assert resolve_outline(BOOK, {"chapters": 38}) == [{"part": 1, "size": 38}]


def test_no_outline_where_nothing_says_how_many() -> None:
    assert resolve_outline(SERIES, {}) is None
    assert resolve_outline(BOOK, {"page_count": 300}) is None
    assert resolve_outline(MOVIE, {"runtime_minutes": 90}) is None


def test_unusable_rows_are_skipped_rather_than_drawn() -> None:
    metadata = {
        "season_episodes": [
            {"season": 1, "episodes": 7},
            {"season": 2, "episodes": None},
            {"season": None, "episodes": 4},
            {"season": 3, "episodes": 0},
        ]
    }
    assert resolve_outline(SERIES, metadata) == [{"part": 1, "size": 7}]


# -- the marks --------------------------------------------------------------------------


def test_marks_are_normalized_sorted_and_unique() -> None:
    marks = validate_progress_marks(SERIES, {"2": [3, 1, 1], "1": [7], "4": []})
    assert marks == {"1": [7], "2": [1, 3]}


def test_marks_refuse_a_bad_shape() -> None:
    for bad in (
        {"one": [1]},
        {"1": [0]},
        {"1": [-2]},
        {"1": ["3"]},
        {"1": [True]},
        {"0": [1]},
        {"1": 3},
        [1, 2],
    ):
        with pytest.raises(InvalidProgress):
            validate_progress_marks(SERIES, bad)


def test_marks_have_a_ceiling() -> None:
    validate_progress_marks(ANIME, {"1": list(range(1, 10_001))})
    with pytest.raises(InvalidProgress):
        validate_progress_marks(ANIME, {"1": list(range(1, 10_002))})


def test_a_domain_without_progress_refuses_marks() -> None:
    for domain in (MOVIE, ALBUM):
        with pytest.raises(InvalidProgress) as refused:
            validate_progress_marks(domain, {"1": [1]})
        assert domain.label in str(refused.value)
    assert validate_progress_marks(MOVIE, None) is None


def test_marks_set_the_count() -> None:
    values = validate_entry_values(SERIES, {"progress_marks": {"1": [1, 2, 3], "2": [1]}})
    assert values == {"progress_marks": {"1": [1, 2, 3], "2": [1]}, "progress": 4}


def test_no_marks_left_records_zero_and_stores_none() -> None:
    values = validate_entry_values(SERIES, {"progress_marks": {"1": []}})
    assert values == {"progress_marks": None, "progress": 0}


def test_a_typed_count_clears_the_marks() -> None:
    values = validate_entry_values(SERIES, {"progress": 12})
    assert values == {"progress": 12, "progress_marks": None}


def test_a_count_and_marks_together_are_refused() -> None:
    with pytest.raises(InvalidProgress):
        validate_entry_values(SERIES, {"progress": 2, "progress_marks": {"1": [1]}})


def test_clearing_the_marks_alone_leaves_the_count() -> None:
    assert validate_entry_values(SERIES, {"progress_marks": None}) == {"progress_marks": None}


# -- TVmaze: the season list ------------------------------------------------------------


def tvmaze(routes: dict[str, Any], **kwargs: Any) -> TvmazeSeriesProvider:
    async def no_sleep(_seconds: float) -> None:
        return None

    client = create_provider_client(replay(routes, **kwargs))
    return TvmazeSeriesProvider(client, "test@example.invalid", sleep=no_sleep)


BREAKING_BAD_SEASONS = [
    {"season": 1, "episodes": 7},
    {"season": 2, "episodes": 13},
    {"season": 3, "episodes": 13},
    {"season": 4, "episodes": 13},
    {"season": 5, "episodes": 16},
]
EPISODES_169 = {"/shows/169/episodes": (200, recording("tvmaze_show_169_episodes.json"))}


async def test_a_fetched_series_carries_its_seasons() -> None:
    routes = {
        "/shows/169": (200, recording("tvmaze_show_169_breaking_bad.json")),
        **EPISODES_169,
    }
    payload = await tvmaze(routes).fetch("169")
    assert payload.metadata["season_episodes"] == BREAKING_BAD_SEASONS


async def test_a_series_looked_up_by_imdb_carries_its_seasons() -> None:
    routes = {
        "/lookup/shows": (200, recording("tvmaze_lookup_tt0903747.json")),
        **EPISODES_169,
    }
    payload = await tvmaze(routes).fetch_by_identifier("imdb", "tt0903747")
    assert payload.metadata["season_episodes"] == BREAKING_BAD_SEASONS
    # Still never the total: Wikidata owns `episodes` (DEC-104).
    assert "episodes" not in payload.metadata


async def test_a_failed_episode_list_leaves_the_rest_of_the_record() -> None:
    routes = {
        "/shows/169": (200, recording("tvmaze_show_169_breaking_bad.json")),
        "/shows/169/episodes": (500, None),
    }
    payload = await tvmaze(routes).fetch("169")
    assert payload.title == "Breaking Bad"
    assert "season_episodes" not in payload.metadata


async def test_search_does_not_ask_for_episodes() -> None:
    seen: list[httpx.Request] = []
    routes = {"/search/shows": (200, recording("tvmaze_search_breaking_bad.json"))}
    await tvmaze(routes, on_request=seen.append).search("Breaking Bad")
    assert [request.url.path for request in seen] == ["/search/shows"]


# -- Open Library: the chapter count ----------------------------------------------------


def openlibrary(routes: dict[str, Any]) -> OpenLibraryProvider:
    return OpenLibraryProvider(create_provider_client(replay(routes)), "test@example.invalid")


async def test_a_book_with_numbered_contents_gets_its_chapters() -> None:
    routes = {
        "/books/OL26208390M.json": (
            200,
            recording("edition_OL26208390M_thinking_fast_and_slow.json"),
        ),
        "/works/OL15992072W.json": (200, recording("work_OL15992072W_thinking_fast_and_slow.json")),
    }
    payload = await openlibrary(routes).fetch("OL26208390M")
    # Fifty rows; the introduction, part headings and back matter are not chapters.
    assert payload.metadata["chapters"] == 38


async def test_a_book_without_contents_gets_no_chapters() -> None:
    routes = {
        "/books/OL19845805M.json": (200, recording("edition_OL19845805M.json")),
        "/authors/OL2631008A.json": (200, recording("author_OL2631008A.json")),
        "/works/OL14860424W.json": (200, recording("work_OL14860424W.json")),
    }
    payload = await openlibrary(routes).fetch("OL19845805M")
    assert "chapters" not in payload.metadata


def test_chapters_do_not_make_a_book_incomplete() -> None:
    """Most books have no contents; naming it would re-queue them on every backfill."""
    assert BOOK.enrichment is not None and SERIES.enrichment is not None
    assert "chapters" not in BOOK.enrichment.completeness_fields
    assert "season_episodes" not in SERIES.enrichment.completeness_fields


# -- the API ----------------------------------------------------------------------------


def _settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")


async def _entry(
    client: httpx.AsyncClient,
    app: Any,
    item_type: str,
    metadata: dict[str, Any] | None = None,
    identifiers: dict[str, str] | None = None,
) -> tuple[int, int]:
    created = await client.post(
        "/api/entries",
        json={
            "manual": {
                "item_type": item_type,
                "title": f"A {item_type}",
                "identifiers": identifiers or {},
            },
            "idempotency_key": f"{item_type}-{hash(json.dumps(metadata, sort_keys=True))}",
        },
    )
    assert created.status_code == 201, created.text
    entry = created.json()["entry"]
    if metadata is not None:
        with app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE items SET metadata = :metadata WHERE id = :id"),
                {"metadata": json.dumps(metadata), "id": entry["item_id"]},
            )
    return int(entry["id"]), int(entry["item_id"])


async def test_marks_round_trip_and_drive_the_count(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        entry_id, _item = await _entry(
            client, app, "series", {"season_episodes": BREAKING_BAD_SEASONS}
        )
        marked = await client.patch(
            f"/api/entries/{entry_id}",
            json={"progress_marks": {"1": [1, 2, 3, 4, 5, 6, 7], "2": [1, 2]}},
        )
        read = await client.get(f"/api/entries/{entry_id}")
        typed = await client.patch(f"/api/entries/{entry_id}", json={"progress": 30})
        both = await client.patch(
            f"/api/entries/{entry_id}", json={"progress": 3, "progress_marks": {"1": [1]}}
        )

    assert marked.status_code == 200, marked.text
    assert marked.json()["progress"] == 9
    assert read.json()["progress_marks"] == {"1": [1, 2, 3, 4, 5, 6, 7], "2": [1, 2]}
    assert typed.json()["progress"] == 30
    assert typed.json()["progress_marks"] is None
    assert both.status_code == 422


async def test_marks_outside_the_outline_are_kept_and_counted(tmp_path: Path) -> None:
    """The outline is never a bound (DEC-092): a refresh may shrink it under marks."""
    app = create_app(_settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        entry_id, _item = await _entry(client, app, "anime", {"episodes": 12})
        marked = await client.patch(
            f"/api/entries/{entry_id}", json={"progress_marks": {"1": [11, 12, 13], "2": [1]}}
        )

    assert marked.status_code == 200
    assert marked.json()["progress"] == 4
    assert marked.json()["progress_marks"] == {"1": [11, 12, 13], "2": [1]}


async def test_a_film_refuses_marks(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        entry_id, _item = await _entry(client, app, "movie")
        refused = await client.patch(
            f"/api/entries/{entry_id}", json={"progress_marks": {"1": [1]}}
        )

    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "invalid_progress"


async def test_the_item_carries_its_resolved_outline(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        series_entry, series_item = await _entry(
            client, app, "series", {"season_episodes": BREAKING_BAD_SEASONS[:2]}
        )
        book_entry, book_item = await _entry(client, app, "book", {"chapters": 32})
        film_entry, film_item = await _entry(client, app, "movie")
        series = await client.get(f"/api/items/{series_item}")
        book = (await client.get(f"/api/entries/{book_entry}")).json()["item"]
        film = await client.get(f"/api/items/{film_item}")

    assert series.json()["outline"] == [{"part": 1, "size": 7}, {"part": 2, "size": 13}]
    assert book["outline"] == [{"part": 1, "size": 32}]
    assert film.json().get("outline") is None


async def test_the_item_types_publish_the_new_declarations(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        published = {row["id"]: row for row in (await client.get("/api/item-types")).json()}

    assert published["series"]["progress"]["parts_field"] == "season_episodes"
    assert published["book"]["progress"]["total_field"] == "chapters"
    dropped = next(row for row in published["book"]["statuses"] if row["value"] == "dropped")
    assert dropped["abandoned"] is True


def _tvmaze_only(app: Any, routes: dict[str, Any]) -> None:
    app.state.providers = {"tvmaze": tvmaze(routes)}


async def test_the_outline_action_fills_a_series_that_had_none(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        _entry_id, item_id = await _entry(
            client, app, "series", {"episodes": 62}, identifiers={"imdb": "tt0903747"}
        )
        _tvmaze_only(
            app,
            {"/lookup/shows": (200, recording("tvmaze_lookup_tt0903747.json")), **EPISODES_169},
        )
        filled = await client.post(f"/api/items/{item_id}/outline")

    assert filled.status_code == 200, filled.text
    assert filled.json()["metadata"]["season_episodes"] == BREAKING_BAD_SEASONS
    assert [part["size"] for part in filled.json()["outline"]] == [7, 13, 13, 13, 16]


async def test_a_failed_outline_fetch_changes_nothing(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        _entry_id, item_id = await _entry(
            client, app, "series", {"episodes": 62}, identifiers={"imdb": "tt0903747"}
        )
        before = (await client.get(f"/api/items/{item_id}")).json()
        _tvmaze_only(app, {"/lookup/shows": (503, None)})
        failed = await client.post(f"/api/items/{item_id}/outline")
        after = (await client.get(f"/api/items/{item_id}")).json()

    assert failed.status_code == 502
    assert failed.json()["error"]["code"] == "provider_failure"
    assert after == before


async def test_an_outline_nobody_has_is_said_so(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        _entry_id, item_id = await _entry(
            client, app, "series", {}, identifiers={"imdb": "tt9999999"}
        )
        _tvmaze_only(app, {"/lookup/shows": (404, recording("tvmaze_lookup_no_match.json"))})
        missing = await client.post(f"/api/items/{item_id}/outline")
        film_entry, film_item = await _entry(client, app, "movie")
        film = await client.post(f"/api/items/{film_item}/outline")

    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "outline_unavailable"
    assert film.status_code == 422
    assert film.json()["error"]["code"] == "outline_unavailable"


async def test_an_item_that_has_an_outline_is_not_fetched_again(tmp_path: Path) -> None:
    """An explicit action, but not a refresh: a typed chapter count is never replaced."""
    app = create_app(_settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        _entry_id, item_id = await _entry(client, app, "book", {"chapters": 12})
        app.state.providers = {}
        kept = await client.post(f"/api/items/{item_id}/outline")

    assert kept.status_code == 200
    assert kept.json()["metadata"]["chapters"] == 12


async def test_the_json_export_carries_the_marks(tmp_path: Path) -> None:
    """Owner data, so the lossless export carries it. There is no JSON restore: the
    database backup is the restore path, and it carries the column as it is."""
    app = create_app(_settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        entry_id, _item = await _entry(client, app, "anime", {"episodes": 12})
        await client.patch(f"/api/entries/{entry_id}", json={"progress_marks": {"1": [1, 2, 5]}})
        exported = await client.get("/api/export", params={"format": "json"})

    assert exported.status_code == 200, exported.text
    (entry,) = exported.json()["entries"]
    assert entry["progress_marks"] == {"1": [1, 2, 5]}
    assert entry["progress"] == 3


# -- migration 0027 ---------------------------------------------------------------------


def test_the_column_arrives_and_leaves_without_touching_a_row(tmp_path: Path) -> None:
    from book_tracker.migrations import alembic_config

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    configured = Settings(data_dir=data_dir, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url, revision="0026_goals")
    database = data_dir / "books.db"
    connection = sqlite3.connect(database)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(entries)")}
    assert "progress_marks" not in columns
    connection.close()

    upgrade(configured.database_url, revision="head")
    connection = sqlite3.connect(database)
    columns = {row[1]: row for row in connection.execute("PRAGMA table_info(entries)")}
    assert columns["progress_marks"][3] == 0  # nullable: no marks is the default
    connection.close()

    from alembic import command

    command.downgrade(alembic_config(configured.database_url), "0026_goals")
    connection = sqlite3.connect(database)
    assert "progress_marks" not in {
        row[1] for row in connection.execute("PRAGMA table_info(entries)")
    }
    connection.close()
