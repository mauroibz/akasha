"""Sprint 132: the pile, ranked locally with a true reason each (DEC-183 point 3).

Each signal is shown moving the entry it should, against a fixture library, and each
reason is checked against the data it cites. The ranking reads stored data only and
answers inside its budget on a 2,000-entry pile.
"""

from __future__ import annotations

import json
import statistics
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from book_tracker.application.ranking import rank_pile
from book_tracker.config import Settings
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.main import create_app

TODAY = date(2026, 11, 23)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@asynccontextmanager
async def _app(tmp_path: Path) -> AsyncIterator[Any]:
    app = create_app(Settings(data_dir=tmp_path / "data", user_agent_contact="t@example.invalid"))
    async with app.router.lifespan_context(app):
        yield app


def _entry(
    app: Any,
    title: str,
    status: str,
    *,
    item_type: str = "book",
    creators: tuple[str, ...] = ("Nobody",),
    metadata: dict[str, Any] | None = None,
    user: int = 1,
    **values: Any,
) -> int:
    created = DomainRepository(app.state.engine, user).create_or_get_entry(
        title=title, creators=list(creators), item_type=item_type
    )
    values.setdefault("date_added", "2026-11-01T12:00:00Z")
    assignments = ", ".join(["status = :status", *(f"{key} = :{key}" for key in values)])
    with app.state.engine.begin() as connection:
        connection.execute(
            text(f"UPDATE entries SET {assignments} WHERE id = :id"),
            {"status": status, "id": created.entry_id, **values},
        )
        if metadata:
            current = json.loads(
                connection.execute(
                    text("SELECT metadata FROM items WHERE id = :id"), {"id": created.item_id}
                ).scalar_one()
            )
            connection.execute(
                text("UPDATE items SET metadata = :metadata WHERE id = :id"),
                {"metadata": json.dumps({**current, **metadata}), "id": created.item_id},
            )
    return created.entry_id


def _rank(app: Any, item_type: str | None = "book", limit: int = 10) -> list[dict[str, Any]]:
    engine: Engine = app.state.engine
    return rank_pile(engine, 1, item_type, limit, today=TODAY)


def _ids(ranked: list[dict[str, Any]]) -> list[int]:
    return [pick["entry_id"] for pick in ranked]


def _reasons(pick: dict[str, Any]) -> dict[str, str]:
    return {reason["signal"]: reason["text"] for reason in pick["reasons"]}


@pytest.mark.anyio
async def test_waiting_alone_surfaces_the_old_pile_first(tmp_path: Path) -> None:
    async with _app(tmp_path) as app:
        newer = _entry(app, "Newer", "to_read", date_added="2025-01-10T00:00:00Z")
        oldest = _entry(app, "Oldest", "to_read", date_added="2023-03-01T00:00:00Z")
        _entry(app, "Not on the pile", "read", date_added="2020-01-01T00:00:00Z")
        _entry(app, "Wished for", "wishlist", date_added="2020-01-01T00:00:00Z")

        ranked = _rank(app)

    assert _ids(ranked) == [oldest, newer]
    assert _reasons(ranked[0]) == {"waiting": "Waiting since Mar 2023"}
    # Waiting is small: three and a half years is less than one strong signal.
    assert ranked[0]["score"] < 1.5


@pytest.mark.anyio
async def test_the_next_in_a_series_rises_and_names_the_one_before(tmp_path: Path) -> None:
    async with _app(tmp_path) as app:
        _entry(
            app,
            "The Final Empire",
            "read",
            score=9,
            metadata={"series": "Mistborn #1"},
            date_finished="2026-10-01",
        )
        third = _entry(app, "The Hero of Ages", "to_read", metadata={"series": "Mistborn #3"})
        second = _entry(
            app, "The Well of Ascension", "to_read", metadata={"series": "Mistborn, #2"}
        )
        waiting = _entry(app, "Long waiting", "to_read", date_added="2021-01-01T00:00:00Z")

        ranked = _rank(app)

    assert _ids(ranked)[0] == second
    assert _reasons(ranked[0])["series"] == "Next in Mistborn; you gave book 1 a 9"
    # Only the next one: the third waits its turn, behind the long-waiting book.
    assert _ids(ranked)[1:] == [waiting, third]
    assert "series" not in _reasons(ranked[2])


@pytest.mark.anyio
async def test_a_goodreads_title_names_its_series_and_place(tmp_path: Path) -> None:
    async with _app(tmp_path) as app:
        _entry(app, "Leviathan Wakes (The Expanse, #1)", "read", score=8)
        _entry(app, "Caliban's War (The Expanse, #2)", "reading")
        third = _entry(app, "Abaddon's Gate (The Expanse, #3)", "to_read")
        other = _entry(app, "Old pile", "to_read", date_added="2020-01-01T00:00:00Z")

        ranked = _rank(app)

    assert _ids(ranked) == [third, other]
    assert _reasons(ranked[0])["series"] == "Next in The Expanse; you're on book 2 now"


@pytest.mark.anyio
async def test_a_series_without_places_or_after_a_drop(tmp_path: Path) -> None:
    async with _app(tmp_path) as app:
        _entry(app, "Wolf Hall", "read", metadata={"series": "Thomas Cromwell"})
        # Another name is another series, however alike.
        other_series = _entry(
            app, "Bring Up the Bodies", "to_read", metadata={"series": "Cromwell"}
        )
        same = _entry(
            app, "The Mirror and the Light", "to_read", metadata={"series": "Thomas Cromwell"}
        )
        # Read the first, dropped the second: the third is not pushed.
        _entry(app, "Dune", "read", score=9, metadata={"series": "Dune #1"})
        _entry(app, "Dune Messiah", "dropped", metadata={"series": "Dune #2"})
        after_drop = _entry(app, "Children of Dune", "to_read", metadata={"series": "Dune #3"})
        # A series the person did not like is not pushed either.
        _entry(app, "Disliked one", "read", score=4, metadata={"series": "Meh #1"})
        disliked_next = _entry(app, "Disliked two", "to_read", metadata={"series": "Meh #2"})

        ranked = {pick["entry_id"]: pick for pick in _rank(app)}

    assert _reasons(ranked[same])["series"] == "Next in Thomas Cromwell after Wolf Hall"
    assert "series" not in _reasons(ranked[other_series])
    assert "series" not in _reasons(ranked[after_drop])
    assert "series" not in _reasons(ranked[disliked_next])


@pytest.mark.anyio
async def test_a_series_after_one_finished_leads_one_after_one_under_way(tmp_path: Path) -> None:
    async with _app(tmp_path) as app:
        _entry(app, "Leviathan Wakes (The Expanse, #1)", "read", score=8)
        _entry(app, "Caliban's War (The Expanse, #2)", "reading")
        under_way = _entry(app, "Abaddon's Gate (The Expanse, #3)", "to_read")
        _entry(
            app,
            "El problema de los tres cuerpos",
            "read",
            score=8,
            metadata={"series": "Tres Cuerpos #1"},
        )
        finished = _entry(
            app, "El bosque oscuro", "to_read", metadata={"series": "Tres Cuerpos #2"}
        )

        ranked = _rank(app)

    # Book 2 of the Expanse is not done yet; book 2 of the other is ready to start.
    assert _ids(ranked) == [finished, under_way]
    assert _reasons(ranked[0])["series"] == "Next in Tres Cuerpos; you gave book 1 an 8"


@pytest.mark.anyio
async def test_a_subject_on_almost_everything_is_no_reason(tmp_path: Path) -> None:
    async with _app(tmp_path) as app:
        # Lately the scores are higher across the board; "Fiction" is on all of them.
        for index in range(6):
            _entry(
                app,
                f"Long ago {index}",
                "read",
                score=6,
                metadata={"subjects": ["Fiction"]},
                date_finished=f"201{index}-05-05",
                creators=(f"A{index}",),
            )
            _entry(
                app,
                f"Lately {index}",
                "read",
                score=9,
                metadata={"subjects": ["Fiction", "Horror" if index < 3 else "Poetry"]},
                date_finished=f"2026-0{index + 1}-05",
                creators=(f"B{index}",),
            )
        plain = _entry(app, "Plain", "to_read", metadata={"subjects": ["Fiction"]})
        horror = _entry(app, "Horror", "to_read", metadata={"subjects": ["Fiction", "Horror"]})

        ranked = {pick["entry_id"]: pick for pick in _rank(app)}

    assert "affinity" not in _reasons(ranked[plain])
    assert _reasons(ranked[horror])["affinity"] == "You rate Horror 9.0 across 3 books"


@pytest.mark.anyio
async def test_a_catalogue_category_reads_as_a_subject_and_general_is_none(
    tmp_path: Path,
) -> None:
    # The owner's real library (the 3.0 rehearsal): Google Books stores categories as
    # shouted paths ("FICTION / Horror") and Open Library tags many books "General".
    # "You rate General 6.9 across 7 books" names nothing, and the path reads as one.
    async with _app(tmp_path) as app:
        for index in range(3):
            _entry(
                app,
                f"Horror {index}",
                "read",
                score=9,
                metadata={"subjects": ["FICTION / Horror", "General"]},
                creators=(f"H{index}",),
            )
            _entry(
                app,
                f"Shelf filler {index}",
                "read",
                score=9,
                metadata={"subjects": ["Fiction / General"]},
                creators=(f"G{index}",),
            )
        for index in range(6):
            _entry(app, f"Plain {index}", "read", score=5, creators=(f"P{index}",))
        horror = _entry(
            app, "Waiting horror", "to_read", metadata={"subjects": ["Fiction / Horror"]}
        )
        general = _entry(
            app,
            "Waiting general",
            "to_read",
            metadata={"subjects": ["General", "Fiction / General"]},
        )

        ranked = {pick["entry_id"]: pick for pick in _rank(app)}

    assert _reasons(ranked[horror])["affinity"] == "You rate Fiction / Horror 9.0 across 3 books"
    assert "affinity" not in _reasons(ranked[general])


@pytest.mark.anyio
async def test_a_favourite_creator_lifts_their_waiting_book(tmp_path: Path) -> None:
    async with _app(tmp_path) as app:
        for index, score in enumerate((9, 8, 9, 8, 8)):
            _entry(app, f"Le Guin {index}", "read", creators=("Ursula K. Le Guin",), score=score)
        for index, score in enumerate((6, 7, 5, 6)):
            _entry(app, f"Other {index}", "read", creators=(f"Other {index}",), score=score)
        _entry(app, "Lukewarm 1", "read", creators=("Lukewarm",), score=6)
        _entry(app, "Lukewarm 2", "read", creators=("Lukewarm",), score=6)
        lukewarm = _entry(app, "Lukewarm 3", "to_read", creators=("Lukewarm",))
        older = _entry(app, "Older", "to_read", date_added="2024-01-01T00:00:00Z")
        favourite = _entry(app, "The Lathe of Heaven", "to_read", creators=("Ursula K. Le Guin",))

        ranked = _rank(app)

    assert _ids(ranked) == [favourite, older, lukewarm]
    assert _reasons(ranked[0])["creator"] == "You rate Ursula K. Le Guin 8.4 across 5"
    # Below the person's own average is no reason to read something next.
    assert "creator" not in _reasons(ranked[2])


@pytest.mark.anyio
async def test_recent_high_scores_on_a_subject_lift_what_carries_it(tmp_path: Path) -> None:
    async with _app(tmp_path) as app:
        for index in range(3):
            _entry(
                app,
                f"Recent fantasy {index}",
                "read",
                score=9,
                metadata={"subjects": ["Fantasy", "Fiction"]},
                date_finished=f"2026-0{index + 1}-10",
                creators=(f"F{index}",),
            )
            _entry(
                app,
                f"Old history {index}",
                "read",
                score=9,
                metadata={"subjects": ["History", "Fiction"]},
                date_finished=f"2014-0{index + 1}-10",
                creators=(f"H{index}",),
            )
            _entry(
                app,
                f"Plain {index}",
                "read",
                score=6,
                metadata={"subjects": ["Fiction"]},
                creators=(f"P{index}",),
            )
        history = _entry(app, "A history", "to_read", metadata={"subjects": ["history"]})
        fantasy = _entry(app, "A fantasy", "to_read", metadata={"subjects": ["Fantasy", "Fiction"]})
        plain = _entry(app, "Plain fiction", "to_read", metadata={"subjects": ["Fiction"]})

        ranked = _rank(app)

    # Both subjects were scored 9 three times; the recent one counts for more.
    assert _ids(ranked) == [fantasy, history, plain]
    assert _reasons(ranked[0])["affinity"] == "You rate Fantasy 9.0 across 3 books"
    assert _reasons(ranked[1])["affinity"] == "You rate History 9.0 across 3 books"
    assert "affinity" not in _reasons(ranked[2])


@pytest.mark.anyio
async def test_a_library_short_of_its_goal_is_lifted_across_libraries(tmp_path: Path) -> None:
    async with _app(tmp_path) as app:
        film = _entry(
            app, "A film", "watchlist", item_type="movie", date_added="2025-01-01T00:00:00Z"
        )
        book = _entry(app, "A book", "to_read", date_added="2026-06-01T00:00:00Z")
        _entry(app, "Done", "read", date_finished="2026-02-01")
        now = datetime.now(UTC).isoformat()
        with app.state.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO goals (user_id, item_type, count, period, suggest, created_at,"
                    " updated_at) VALUES (1, 'book', 2, 'month', 1, :now, :now)"
                ),
                {"now": now},
            )

        across = _rank(app, None)
        books_only = _rank(app, "book")

    assert _ids(across) == [book, film]
    assert _reasons(across[0])["goal"] == "Toward 24 books this year; 1 so far"
    # Inside one library the goal lifts every entry alike, so it is not a reason there.
    assert "goal" not in _reasons(books_only[0])


@pytest.mark.anyio
async def test_a_goal_on_pace_lifts_nothing(tmp_path: Path) -> None:
    async with _app(tmp_path) as app:
        film = _entry(app, "A film", "watchlist", item_type="movie", date_added="2025-01-01")
        _entry(app, "A book", "to_read", date_added="2026-06-01T00:00:00Z")
        for month in range(1, 12):
            _entry(app, f"Done {month}", "read", date_finished=f"2026-{month:02d}-01")
        now = datetime.now(UTC).isoformat()
        with app.state.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO goals (user_id, item_type, count, period, suggest, created_at,"
                    " updated_at) VALUES (1, 'book', 12, 'year', 1, :now, :now)"
                ),
                {"now": now},
            )

        across = _rank(app, None)

    assert _ids(across)[0] == film
    assert all("goal" not in _reasons(pick) for pick in across)


@pytest.mark.anyio
async def test_something_set_aside_lately_is_pushed_down(tmp_path: Path) -> None:
    recently = (datetime.now(UTC) - timedelta(days=3)).isoformat().replace("+00:00", "Z")
    long_ago = "2025-01-01T00:00:00Z"
    async with _app(tmp_path) as app:
        set_aside = _entry(
            app,
            "Set aside",
            "to_read",
            date_added="2020-01-01T00:00:00Z",
            date_started="2026-11-01",
            updated_at=recently,
        )
        then_left = _entry(
            app,
            "Set aside long ago",
            "to_read",
            date_added="2020-06-01T00:00:00Z",
            date_started="2024-12-01",
            updated_at=long_ago,
        )
        fresh = _entry(app, "Fresh", "to_read", date_added="2026-11-20T00:00:00Z")

        ranked = rank_pile(app.state.engine, 1, "book", 10, today=datetime.now(UTC).date())

    assert _ids(ranked) == [then_left, fresh, set_aside]
    assert _reasons(ranked[2])["set_aside"] == "Started 1 Nov 2026, then set aside"
    assert ranked[2]["reasons"][0]["signal"] == "set_aside"
    assert "set_aside" not in _reasons(ranked[0])


@pytest.mark.anyio
async def test_the_order_is_stable_and_ties_break_on_entry_id(tmp_path: Path) -> None:
    async with _app(tmp_path) as app:
        ids = [
            _entry(app, f"Same {index}", "to_read", date_added="2025-05-05T00:00:00Z")
            for index in range(6)
        ]
        first = _rank(app, limit=4)
        second = _rank(app, limit=4)

    assert first == second
    assert _ids(first) == ids[:4]


@pytest.mark.anyio
async def test_reasons_are_strongest_first_and_only_signals_that_fired(tmp_path: Path) -> None:
    async with _app(tmp_path) as app:
        for index in range(3):
            _entry(app, f"Kept {index}", "read", creators=("Loved",), score=10)
        _entry(app, "Meh", "read", creators=("Meh",), score=5)
        pick = _entry(app, "Next by Loved", "to_read", creators=("Loved",), date_added="2025-11-01")

        ranked = _rank(app)

    assert _ids(ranked) == [pick]
    assert [reason["signal"] for reason in ranked[0]["reasons"]] == ["creator", "waiting"]
    assert ranked[0]["reasons"][0]["text"] == "You rate Loved 10.0 across 3"


@pytest.mark.anyio
async def test_another_persons_library_is_not_read(tmp_path: Path) -> None:
    async with _app(tmp_path) as app:
        with app.state.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id, username, display_name, password_hash, password_salt,"
                    " is_admin, created_at, updated_at)"
                    " VALUES (2, 'other', 'Other', 'x', 'x', 0, '2026-01-01', '2026-01-01')"
                )
            )
        for index in range(3):
            _entry(app, f"Theirs {index}", "read", creators=("Theirs",), score=10, user=2)
        theirs = _entry(app, "Their pile", "to_read", creators=("Theirs",), user=2)
        mine = _entry(app, "My pile", "to_read", creators=("Theirs",))

        ranked = _rank(app)

    assert _ids(ranked) == [mine]
    assert theirs not in _ids(ranked)
    assert "creator" not in _reasons(ranked[0])


def _seed_pile(app: Any, pile: int, rest: int) -> None:
    """`pile` waiting books and `rest` finished ones, with series, subjects and creators."""
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    subjects = ["Fantasy", "History", "Science fiction", "Mystery", "Poetry", "Fiction"]
    items: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    for index in range(1, pile + rest + 1):
        waiting = index <= pile
        meta: dict[str, Any] = {
            "creators": [f"Creator {index % 150}"],
            "subjects": [subjects[index % 6], subjects[(index * 7) % 6], "Fiction"],
        }
        if index % 5 == 0:
            meta["series"] = f"Saga {index % 40} #{1 + index % 9}"
        items.append(
            {
                "id": index,
                "title": f"Title {index:05d}",
                "metadata": json.dumps(meta),
                "creator": f"creator {index % 150}",
                "now": now,
            }
        )
        entries.append(
            {
                "id": index,
                "item_id": index,
                "status": "to_read" if waiting else "read",
                "score": None if waiting or index % 4 == 0 else 1 + index % 10,
                "date_added": f"20{10 + index % 16}-0{1 + index % 9}-01T00:00:00Z",
                "date_finished": None if waiting else f"20{14 + index % 12}-0{1 + index % 9}-11",
                "date_started": "2026-11-01" if index % 97 == 0 else None,
                "now": now,
            }
        )
    with app.state.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO items (id, type, title, cover_path, identifiers, metadata,"
                " creator_primary_normalized, created_at, updated_at)"
                " VALUES (:id, 'book', :title, NULL, '{}', :metadata, :creator, :now, :now)"
            ),
            items,
        )
        connection.execute(
            text(
                "INSERT INTO entries (id, user_id, item_id, status, score, date_added,"
                " date_started, date_finished, reread_count, score_provisional, created_at,"
                " updated_at) VALUES (:id, 1, :item_id, :status, :score, :date_added,"
                " :date_started, :date_finished, 0, 0, :now, :now)"
            ),
            entries,
        )


@pytest.mark.anyio
async def test_a_two_thousand_entry_pile_ranks_inside_its_budget(tmp_path: Path) -> None:
    async with _app(tmp_path) as app:
        _seed_pile(app, 2_000, 3_000)
        first = rank_pile(app.state.engine, 1, None, 5, today=TODAY)
        assert len(first) == 5
        timings = []
        for _ in range(5):
            started = time.perf_counter()
            again = rank_pile(app.state.engine, 1, None, 5, today=TODAY)
            timings.append(time.perf_counter() - started)
            assert again == first
    print(f"pile median {statistics.median(timings) * 1000:.1f} ms")
    assert statistics.median(timings) < 0.100, timings


class _Refuse(httpx.MockTransport):
    def __init__(self, calls: list[str]) -> None:
        def refuse(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            raise AssertionError(f"The pile made a network call to {request.url}")

        super().__init__(refuse)


@pytest.mark.anyio
async def test_the_pile_route_ranks_with_reasons_and_no_network(tmp_path: Path) -> None:
    async with _app(tmp_path) as app:
        calls: list[str] = []
        app.state.provider_client = httpx.AsyncClient(transport=_Refuse(calls))
        app.state.providers = {}
        app.state.provider_catalog = {}
        _entry(app, "Book one", "read", score=9, metadata={"series": "Saga #1"})
        second = _entry(app, "Book two", "to_read", metadata={"series": "Saga #2"})
        film = _entry(app, "A film", "watchlist", item_type="movie", date_added="2024-02-01")
        _entry(app, "An album", "owned", item_type="album")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            every = await client.get("/api/pile")
            films = await client.get("/api/pile", params={"type": "movie", "limit": 1})
            albums = await client.get("/api/pile", params={"type": "album"})
            refused = await client.get("/api/pile", params={"type": "comic"})
            too_many = await client.get("/api/pile", params={"limit": 0})
            picks = await client.get("/api/goals/book/picks")

    assert every.status_code == 200, every.text
    body = every.json()
    assert [row["entry"]["id"] for row in body] == [second, film]
    assert body[0]["reasons"][0] == {
        "signal": "series",
        "text": "Next in Saga; you gave book 1 a 9",
    }
    assert isinstance(body[0]["score"], float)
    assert [row["entry"]["id"] for row in films.json()] == [film]
    assert films.json()[0]["reasons"] == [{"signal": "waiting", "text": "Waiting since Feb 2024"}]
    assert albums.json() == []
    assert refused.status_code == 422
    assert too_many.status_code == 422
    assert [row["entry"]["id"] for row in picks.json()] == [second]
    assert picks.json()[0]["reasons"][0]["signal"] == "series"
    assert calls == []


# --- Sprint 136: close to what you scored highly ---------------------------------------

MODEL = "gemini:gemini-embedding-001@3"


def _item_of(app: Any, entry_id: int) -> int:
    with app.state.engine.connect() as connection:
        return int(
            connection.execute(
                text("SELECT item_id FROM entries WHERE id = :id"), {"id": entry_id}
            ).scalar_one()
        )


def _similar_library(app: Any) -> dict[str, int]:
    """Two loved books, one disliked, and a pile of four that differ only by vector."""
    entries = {
        "Rayuela": _entry(app, "Rayuela", "read", score=9, date_finished="2026-01-10"),
        "Ficciones": _entry(app, "Ficciones", "read", score=8, date_finished="2025-06-01"),
        "Manual": _entry(app, "A manual", "read", score=3, date_finished="2025-02-01"),
        "62": _entry(app, "62: Modelo para armar", "to_read", date_added="2026-10-01"),
        "Aleph": _entry(app, "El Aleph", "to_read", date_added="2026-10-01"),
        "Physics": _entry(app, "Physics", "to_read", date_added="2026-10-01"),
        "Cooking": _entry(app, "Cooking", "to_read", date_added="2026-10-01"),
    }
    return entries


def _store_similar_vectors(app: Any, entries: dict[str, int], model: str = MODEL) -> None:
    from book_tracker.application.embeddings import store_vectors

    vectors = {
        "Rayuela": [1.0, 0.1, 0.0],
        "Ficciones": [0.6, 1.0, 0.0],
        "Manual": [0.0, 0.0, 1.0],
        "62": [1.0, 0.15, 0.0],
        "Aleph": [0.55, 1.0, 0.05],
        "Physics": [0.0, 0.2, 1.0],
        "Cooking": [0.1, 0.0, 1.0],
    }
    store_vectors(
        app.state.engine,
        model,
        [(_item_of(app, entries[name]), "h", vector) for name, vector in vectors.items()],
    )


@pytest.mark.anyio
async def test_without_embeddings_the_order_is_sprint_132s_exactly(tmp_path: Path) -> None:
    async with _app(tmp_path) as app:
        entries = _similar_library(app)
        before = _rank(app)
        _store_similar_vectors(app, entries)
        # Vectors are stored, but no endpoint is configured: they are not read.
        unconfigured = rank_pile(app.state.engine, 1, "book", 10, today=TODAY)
        other_model = rank_pile(
            app.state.engine, 1, "book", 10, today=TODAY, embedding_model="openai:other@x"
        )
        every = rank_pile(app.state.engine, 1, None, 10, today=TODAY)
    assert unconfigured == before
    assert other_model == before
    assert all(reason["signal"] != "similarity" for pick in every for reason in pick["reasons"])


@pytest.mark.anyio
async def test_what_stands_closest_to_the_best_scored_rises_and_names_it(
    tmp_path: Path,
) -> None:
    async with _app(tmp_path) as app:
        entries = _similar_library(app)
        _store_similar_vectors(app, entries)
        ranked = rank_pile(app.state.engine, 1, "book", 10, today=TODAY, embedding_model=MODEL)
    order = _ids(ranked)
    assert order[:2] == [entries["62"], entries["Aleph"]]
    assert _reasons(ranked[0])["similarity"] == "Close to what you scored 9: Rayuela"
    assert _reasons(ranked[1])["similarity"] == "Close to what you scored 8: Ficciones"
    assert ranked[0]["reasons"][0]["signal"] == "similarity"
    # Close to the one scored 3 is no reason: it is below the person's mean.
    for pick in ranked[2:]:
        assert "similarity" not in _reasons(pick)


@pytest.mark.anyio
async def test_a_pile_too_small_to_compare_lifts_nothing(tmp_path: Path) -> None:
    async with _app(tmp_path) as app:
        entries = _similar_library(app)
        _store_similar_vectors(app, entries)
        with app.state.engine.begin() as connection:
            connection.execute(
                text("DELETE FROM item_embeddings WHERE item_id IN (:a, :b)"),
                {"a": _item_of(app, entries["Physics"]), "b": _item_of(app, entries["Cooking"])},
            )
        ranked = rank_pile(app.state.engine, 1, "book", 10, today=TODAY, embedding_model=MODEL)
    assert all("similarity" not in _reasons(pick) for pick in ranked)


@pytest.mark.anyio
async def test_up_next_and_the_pile_route_read_the_configured_model(tmp_path: Path) -> None:
    async with _app(tmp_path) as app:
        entries = _similar_library(app)
        _store_similar_vectors(app, entries)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            assert app.state.embedding_model is None
            off = (await client.get("/api/pile", params={"type": "book"})).json()
            app.state.embedding_model = MODEL
            on = (await client.get("/api/pile", params={"type": "book"})).json()
            home = (await client.get("/api/home")).json()
            picks = (await client.get("/api/goals/book/picks")).json()
    assert all(r["signal"] != "similarity" for pick in off for r in pick["reasons"])
    assert on[0]["entry"]["id"] == entries["62"]
    assert on[0]["reasons"][0] == {
        "signal": "similarity",
        "text": "Close to what you scored 9: Rayuela",
    }
    assert home["next"][0]["entry"]["id"] == entries["62"]
    assert picks[0]["entry"]["id"] == entries["62"]
