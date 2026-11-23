"""Home's one read (Sprint 130, DEC-183): `GET /api/home`.

Five sections from stored data only: a greeting, what is under way, what is next, the
year, and one tile per registered domain that holds entries. No provider is consulted
while it renders, it answers per person, and it stays inside its time budget on a
10,000-entry library.
"""

from __future__ import annotations

import json
import os
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

from book_tracker.api.auth import COOKIE_NAME
from book_tracker.application.passwords import hash_password
from book_tracker.application.sessions import SessionStore
from book_tracker.config import Settings
from book_tracker.domain.registry import DOMAINS
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _settings(tmp_path: Path, **extra: Any) -> Settings:
    return Settings(data_dir=tmp_path / "data", user_agent_contact="test@example.invalid", **extra)


class _Forbidden:
    """A provider that fails the test the moment anything asks it for anything."""

    def __init__(self, name: str, item_type: str) -> None:
        self.name = name
        self.item_type = item_type
        self.enabled = True

    async def search(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError(f"Home consulted provider {self.name}")

    async def fetch(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError(f"Home consulted provider {self.name}")


def _forbid_the_network(app: Any) -> list[str]:
    """Replace every provider and the shared HTTP client with ones that fail the test."""
    calls: list[str] = []

    def refuse(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        raise AssertionError(f"Home made a network call to {request.url}")

    app.state.provider_client = httpx.AsyncClient(transport=httpx.MockTransport(refuse))
    forbidden = {
        name: _Forbidden(name, getattr(provider, "item_type", "book"))
        for name, provider in app.state.provider_catalog.items()
    }
    app.state.provider_catalog = forbidden
    app.state.providers = dict(forbidden)
    return calls


@asynccontextmanager
async def _client(tmp_path: Path, **extra: Any) -> AsyncIterator[tuple[Any, httpx.AsyncClient]]:
    app = create_app(_settings(tmp_path, **extra))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        yield app, client


def _entry(app: Any, title: str, item_type: str, status: str, user: int = 1, **values: Any) -> int:
    created = DomainRepository(app.state.engine, user).create_or_get_entry(
        title=title, item_type=item_type
    )
    cover = values.pop("cover", None)
    assignments = ", ".join(["status = :status", *(f"{key} = :{key}" for key in values)])
    with app.state.engine.begin() as connection:
        connection.execute(
            text(f"UPDATE entries SET {assignments} WHERE id = :id"),
            {"status": status, "id": created.entry_id, **values},
        )
        if cover:
            connection.execute(
                text("UPDATE items SET cover_path = :cover WHERE id = :id"),
                {"cover": cover, "id": created.item_id},
            )
    return created.entry_id


def _goal(app: Any, item_type: str, count: int, period: str, user: int = 1) -> None:
    now = datetime.now(UTC).isoformat()
    with app.state.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO goals (user_id, item_type, count, period, suggest, created_at,"
                " updated_at) VALUES (:user, :type, :count, :period, 1, :now, :now)"
            ),
            {"user": user, "type": item_type, "count": count, "period": period, "now": now},
        )


@pytest.mark.anyio
async def test_an_empty_library_answers_every_section_empty(tmp_path: Path) -> None:
    async with _client(tmp_path) as (_app, client):
        response = await client.get("/api/home")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "greeting",
        "now",
        "next",
        "year",
        "domains",
        "lately",
        "tidy",
        "question",
        "shelves",
        "lent",
        "suggested",
        "library_years",
        "shelf_modules",
    }
    assert body["greeting"]["today"] == date.today().isoformat()
    assert body["greeting"]["active"] is None
    assert body["greeting"]["entries"] == 0
    assert body["greeting"]["pile"] == 0
    assert body["greeting"]["goals"] == []
    assert body["now"] == []
    assert body["next"] == []
    assert body["year"]["year"] == date.today().year
    assert [month["month"] for month in body["year"]["months"]] == list(range(1, 13))
    assert all(month["count"] == 0 and month["covers"] == [] for month in body["year"]["months"])
    assert body["year"]["goals"] == []
    assert body["domains"] == []
    # Nothing to show is an empty section, which the screen hides.
    assert body["lately"] == []
    assert body["tidy"] == {
        "duplicates": 0,
        "without_cover": 0,
        "unscored": 0,
        "unscored_by_type": {},
    }
    assert body["question"] is None
    assert body["shelves"] == []
    assert body["lent"] == {"total": 0, "loans": []}
    assert body["suggested"] == []
    # A library with no finish this year and no goal draws nothing (Sprint 138).
    assert body["library_years"] == []
    assert body["shelf_modules"] == []


@pytest.mark.anyio
async def test_the_five_sections_read_the_library(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Late November of this year, whatever today is: how far a goal is from its pace,
    # which the ranked pile reads, depends on the day of the year.
    today = date(date.today().year, 11, 23)

    monkeypatch.setattr("book_tracker.api.home._today", lambda _zone: today)
    year = today.year
    started = (today - timedelta(days=31)).isoformat()
    async with _client(tmp_path) as (app, client):
        reading = _entry(
            app,
            "Designing Data-Intensive Applications",
            "book",
            "reading",
            date_started=started,
            updated_at="2026-11-20T00:00:00Z",
        )
        watching = _entry(app, "Frieren", "anime", "watching", updated_at="2026-11-01T00:00:00Z")
        _entry(app, "Rayuela", "book", "read", score=9, date_finished=f"{year}-03-02", cover="c/1")
        _entry(app, "Ficciones", "book", "read", score=7, date_finished=f"{year}-03-20")
        _entry(app, "Old", "book", "read", score=4, date_finished=f"{year - 1}-12-31", cover="c/2")
        _entry(app, "Up", "movie", "watched", score=8, date_finished=f"{year}-07-05", cover="c/3")
        pile = [
            _entry(app, f"Pile {index}", "book", "to_read", date_added=f"2026-01-0{index}")
            for index in range(1, 8)
        ]
        _entry(app, "Later", "movie", "watchlist", date_added="2025-06-01")
        _entry(app, "Kind of Blue", "album", "owned", score=10, cover="c/4")
        _entry(app, "Unsorted import", "book", "unsorted")
        _goal(app, "book", 2, "month")
        _goal(app, "movie", 6, "year")

        body = (await client.get("/api/home")).json()

    greeting = body["greeting"]
    assert greeting["active"]["entry"]["id"] == reading
    assert greeting["active"]["day"] == 32
    # Every entry but the one still in the Inbox; the pile is every planned entry.
    assert greeting["entries"] == 15
    assert greeting["pile"] == 8
    # One library: the book under way, beside the book goal (Sprint 131).
    assert greeting["goals"] == [{"item_type": "book", "target": 24, "count": 2}]

    assert [row["id"] for row in body["now"]] == [reading, watching]

    nexts = body["next"]
    assert len(nexts) == 5
    # The pile ranked across libraries (Sprint 132): both goals are short of their
    # pace and lift alike, so the longest waiting leads: the film, then the books.
    assert nexts[0]["entry"]["item"]["title"] == "Later"
    assert [row["entry"]["id"] for row in nexts[1:]] == pile[:4]
    assert nexts[0]["reasons"][0] == {
        "signal": "goal",
        "text": "Toward 6 movies this year; 1 so far",
    }
    assert nexts[1]["reasons"][0]["text"] == "Toward 24 books this year; 2 so far"

    months = {month["month"]: month for month in body["year"]["months"]}
    assert months[3]["count"] == 2
    assert {cover["title"] for cover in months[3]["covers"]} == {"Rayuela", "Ficciones"}
    assert months[7]["covers"][0]["item_type"] == "movie"
    assert months[7]["covers"][0]["cover_url"].startswith("/api/items/")
    assert months[12]["count"] == 0
    assert body["year"]["goals"] == [
        {"item_type": "book", "period": "month", "count": 2, "target": 24, "done": 2},
        {"item_type": "movie", "period": "year", "count": 6, "target": 6, "done": 1},
    ]

    tiles = {tile["item_type"]: tile for tile in body["domains"]}
    # Registry order, and only domains holding entries.
    assert [tile["item_type"] for tile in body["domains"]] == [
        item_type for item_type in DOMAINS if item_type in {"book", "album", "anime", "movie"}
    ]
    book = tiles["book"]
    assert book["count"] == 11
    assert book["status_counts"] == {"read": 3, "reading": 1, "to_read": 7}
    assert book["scores"] == [0, 0, 0, 1, 0, 0, 1, 0, 1, 0]
    assert book["mean_score"] == pytest.approx(6.7, abs=0.05)
    assert [cover["title"] for cover in book["covers"]] == ["Rayuela", "Old"]
    assert book["without_cover"] == 9
    assert tiles["album"]["covers"][0]["score"] == 10
    assert tiles["anime"]["mean_score"] is None


@pytest.mark.anyio
async def test_lately_groups_additions_by_the_persons_own_day(tmp_path: Path) -> None:
    """An evening import in Buenos Aires (UTC-3) is one day, not two (Sprint 132)."""
    async with _client(tmp_path) as (app, client):
        # 20:30 and 22:00 on 22 Nov in Buenos Aires; 23:30 on the 22nd and 01:00 on the
        # 23rd in UTC.
        _entry(app, "Evening one", "book", "to_read", date_added="2026-11-22T23:30:00Z")
        late = _entry(app, "Evening two", "book", "to_read", date_added="2026-11-23T01:00:00Z")
        _entry(app, "Morning", "book", "to_read", date_added="2026-11-22T12:00:00Z")

        local = (
            await client.get("/api/home", params={"tz": "America/Argentina/Buenos_Aires"})
        ).json()["lately"]
        utc = (await client.get("/api/home")).json()["lately"]
        unknown = await client.get("/api/home", params={"tz": "Mars/Olympus_Mons"})

    assert [(row["entry"]["id"], row["count"]) for row in local] == [(late, 3)]
    # The server's own zone (TZ, UTC by default) when the client names none.
    assert [row["count"] for row in utc] == [1, 2]
    # A zone the server does not know falls back to its own rather than failing Home.
    assert unknown.status_code == 200
    assert [row["count"] for row in unknown.json()["lately"]] == [1, 2]


def _shelve(app: Any, name: str, entries: list[int], user: int = 1) -> None:
    now = datetime.now(UTC).isoformat()
    with app.state.engine.begin() as connection:
        shelf = connection.execute(
            text(
                "INSERT INTO shelves (user_id, name, slug, created_at, updated_at)"
                " VALUES (:user, :name, :slug, :now, :now) RETURNING id"
            ),
            {"user": user, "name": name, "slug": name.lower(), "now": now},
        ).scalar_one()
        for entry in entries:
            connection.execute(
                text("INSERT INTO entry_shelves (entry_id, shelf_id) VALUES (:entry, :shelf)"),
                {"entry": entry, "shelf": shelf},
            )


def _score_event(app: Any, entry: int, score: int, previous: int, at: str) -> None:
    with app.state.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO score_events (entry_id, score, previous, reason, recorded_at)"
                " VALUES (:entry, :score, :previous, 'time', :at)"
            ),
            {"entry": entry, "score": score, "previous": previous, "at": at},
        )


def _lend(app: Any, entry: int, person: str, lent_on: str, returned_on: str | None = None) -> None:
    now = datetime.now(UTC).isoformat()
    with app.state.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO loans (entry_id, person, lent_on, returned_on, created_at,"
                " updated_at) VALUES (:entry, :person, :lent_on, :returned_on, :now, :now)"
            ),
            {
                "entry": entry,
                "person": person,
                "lent_on": lent_on,
                "returned_on": returned_on,
                "now": now,
            },
        )


@pytest.mark.anyio
async def test_the_remaining_modules_read_the_library(tmp_path: Path) -> None:
    async with _client(tmp_path) as (app, client):
        rayuela = _entry(
            app,
            "Rayuela",
            "book",
            "read",
            score=9,
            date_finished="2026-03-02",
            date_added="2025-01-01T09:00:00Z",
            cover="c/1",
        )
        ficciones = _entry(
            app, "Ficciones", "book", "read", date_finished="2026-03-20", date_added="2025-01-01"
        )
        _score_event(app, rayuela, 7, 9, "2026-04-01T10:00:00Z")
        # Two added the same day are one row of Lately.
        added = _entry(app, "Dune", "book", "to_read", date_added="2026-05-01T08:00:00Z")
        newest = _entry(app, "Dune Messiah", "book", "to_read", date_added="2026-05-01T09:00:00Z")
        _entry(app, "Unsorted import", "book", "unsorted", date_added="2026-06-01T00:00:00Z")
        watched = _entry(app, "Up", "movie", "watched", date_added="2024-01-01", cover="c/2")
        # Same work entered twice.
        twice = [
            _entry(app, "The Hobbit", "book", "to_read", date_added="2020-01-01"),
            _entry(app, "The Hobbit", "book", "read", date_added="2020-01-02"),
        ]
        with app.state.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE items SET creator_primary_normalized = 'tolkien'"
                    " WHERE title = 'The Hobbit'"
                )
            )
        _shelve(app, "Favourites", [rayuela, ficciones])
        _shelve(app, "Empty", [])
        _lend(app, rayuela, "Ana", "2026-01-05")
        _lend(app, ficciones, "Luis", "2025-11-01", returned_on="2025-12-01")
        body = (await client.get("/api/home")).json()

    lately = body["lately"]
    assert [(row["kind"], row["entry"]["id"]) for row in lately[:3]] == [
        ("added", newest),
        ("score", rayuela),
        ("finished", ficciones),
    ]
    assert lately[0]["count"] == 2
    assert added not in [row["entry"]["id"] for row in lately]
    assert lately[1]["score"] == 7 and lately[1]["previous"] == 9
    assert len(lately) <= 10
    assert all(row["entry"]["status"] != "unsorted" for row in lately)

    # The pair, every entry without a cover but the one in the Inbox, and finished
    # entries with no score (Ficciones, Up and the second Hobbit).
    assert body["tidy"] == {
        "duplicates": 1,
        "without_cover": 5,
        "unscored": 3,
        # Per library, in registry order: the library opens one domain at a time.
        "unscored_by_type": {"book": 2, "movie": 1},
    }
    assert watched

    question = body["question"]
    assert question["kind"] == "gap"
    assert question["entry"]["status"] in {"read", "watched"}

    assert [(shelf["name"], shelf["entry_count"]) for shelf in body["shelves"]] == [
        ("Favourites", 2)
    ]

    assert body["lent"]["total"] == 1
    (loan,) = body["lent"]["loans"]
    assert loan["person"] == "Ana"
    assert loan["entry"]["id"] == rayuela
    assert twice


@pytest.mark.anyio
async def test_tidy_ups_unscored_count_is_what_its_library_link_lists(tmp_path: Path) -> None:
    """Tidy up links each library's unscored count to `/library?type=…&unscored=true`."""
    finished = [
        status.value for domain in DOMAINS.values() for status in domain.statuses if status.finished
    ]
    async with _client(tmp_path) as (app, client):
        _entry(app, "Scored", "book", "read", score=8)
        _entry(app, "Unscored book", "book", "read")
        _entry(app, "Unscored film", "movie", "watched")
        _entry(app, "Waiting", "book", "to_read")
        tidy = (await client.get("/api/home")).json()["tidy"]
        listed = (
            await client.get("/api/entries", params={"status": finished, "unscored": "true"})
        ).json()
    assert tidy["unscored"] == 2
    assert tidy["unscored_by_type"] == {"book": 1, "movie": 1}
    assert {row["item"]["title"] for row in listed["items"]} == {"Unscored book", "Unscored film"}


@pytest.mark.anyio
async def test_one_question_asks_an_old_score_again_before_a_gap(tmp_path: Path) -> None:
    async with _client(tmp_path) as (app, client):
        old = _entry(app, "Pet Sematary", "book", "read", score=9, date_finished="2019-01-01")
        with app.state.engine.begin() as connection:
            # The score's own row, written when it was set, made six years old.
            connection.execute(
                text(
                    "UPDATE score_events SET recorded_at = '2019-01-02T00:00:00Z'"
                    " WHERE entry_id = :id"
                ),
                {"id": old},
            )
        _entry(app, "Undated", "book", "read")  # a gap: no finish date
        body = (await client.get("/api/home")).json()
    assert body["question"]["kind"] == "revisit"
    assert body["question"]["entry"]["id"] == old
    assert body["question"]["scored_at"].startswith("2019-01-02")


@pytest.mark.anyio
async def test_the_greeting_names_what_is_under_way_in_the_goals_library(tmp_path: Path) -> None:
    """Day N of a book beside the book goal, even when an anime was touched later."""
    today = date.today()
    async with _client(tmp_path) as (app, client):
        book = _entry(
            app,
            "A book",
            "book",
            "reading",
            date_started=(today - timedelta(days=4)).isoformat(),
            updated_at="2026-01-01T00:00:00Z",
        )
        _entry(app, "An anime", "anime", "watching", updated_at="2026-11-01T00:00:00Z")
        _goal(app, "book", 2, "month")
        body = (await client.get("/api/home")).json()
    greeting = body["greeting"]
    assert greeting["active"]["entry"]["id"] == book
    assert greeting["active"]["day"] == 5
    assert [goal["item_type"] for goal in greeting["goals"]] == ["book"]


@pytest.mark.anyio
async def test_the_greeting_shows_the_goal_of_the_library_it_names(tmp_path: Path) -> None:
    async with _client(tmp_path) as (app, client):
        anime = _entry(app, "An anime", "anime", "watching")
        _goal(app, "book", 2, "month")
        _goal(app, "anime", 20, "year")
        body = (await client.get("/api/home")).json()
    greeting = body["greeting"]
    assert greeting["active"]["entry"]["id"] == anime
    assert greeting["goals"] == [{"item_type": "anime", "target": 20, "count": 0}]


def _shelve(app: Any, name: str, entries: list[int], user: int = 1) -> int:
    with app.state.engine.begin() as connection:
        shelf = int(
            connection.execute(
                text(
                    "INSERT INTO shelves (user_id, name, slug, created_at, updated_at)"
                    " VALUES (:user, :name, :slug, 'n', 'n') RETURNING id"
                ),
                {"user": user, "name": name, "slug": name.lower()},
            ).scalar_one()
        )
        for entry_id in entries:
            connection.execute(
                text("INSERT INTO entry_shelves (entry_id, shelf_id) VALUES (:e, :s)"),
                {"e": entry_id, "s": shelf},
            )
    return shelf


@pytest.mark.anyio
async def test_each_librarys_year_and_a_placed_shelf_read_the_library(tmp_path: Path) -> None:
    """Sprint 138 (DEC-192): a library's year with and without a goal, and a shelf."""
    year = date.today().year
    async with _client(tmp_path) as (app, client):
        books = [
            _entry(app, f"Book {n}", "book", "read", date_finished=f"{year}-0{n}-02", cover="c.jpg")
            for n in (3, 1, 2)
        ]
        _entry(app, "Last year", "book", "read", date_finished=f"{year - 1}-05-05")
        film = _entry(app, "A film", "movie", "watched", date_finished=f"{year}-04-04")
        _goal(app, "book", 12, "year")
        _goal(app, "anime", 1, "month")
        favourite = _shelve(app, "Favorites", [books[0], film])
        hidden = _shelve(app, "Hidden", [books[1]])
        layout = (await client.get("/api/home/layout")).json()["modules"]
        for row in layout:
            if row["module"] == f"shelf:{favourite}":
                row["hidden"] = False
            if row["module"] == "year:series":
                row["hidden"] = True
        put = await client.put("/api/home/layout", json={"modules": layout})
        body = (await client.get("/api/home")).json()
    assert put.status_code == 200, put.text
    years = {row["item_type"]: row for row in body["library_years"]}
    # Registry order; series hidden, so not read; anime has a goal and nothing yet.
    assert [row["item_type"] for row in body["library_years"]] == ["book", "anime", "movie"]
    assert years["book"]["total"] == 3
    assert years["book"]["goal"] == {
        "item_type": "book",
        "period": "year",
        "count": 12,
        "target": 12,
        "done": 3,
    }
    # In the order finished, each opening its entry.
    assert [cover["entry_id"] for cover in years["book"]["covers"]] == [
        books[1],
        books[2],
        books[0],
    ]
    assert years["book"]["covers"][0]["cover_url"].startswith("/api/items/")
    assert years["anime"]["total"] == 0 and years["anime"]["goal"]["target"] == 12
    assert years["movie"]["goal"] is None
    assert [cover["entry_id"] for cover in years["movie"]["covers"]] == [film]
    assert body["shelf_modules"] == [
        {
            "id": favourite,
            "name": "Favorites",
            "slug": "favorites",
            "entry_count": 2,
            "covers": body["shelf_modules"][0]["covers"],
        }
    ]
    assert {cover["entry_id"] for cover in body["shelf_modules"][0]["covers"]} == {
        books[0],
        film,
    }
    assert hidden not in {row["id"] for row in body["shelf_modules"]}


@pytest.mark.anyio
async def test_home_consults_no_provider(tmp_path: Path) -> None:
    async with _client(tmp_path) as (app, client):
        _entry(app, "Rayuela", "book", "reading")
        _entry(app, "Missing cover", "movie", "watchlist")
        calls = _forbid_the_network(app)
        response = await client.get("/api/home")
    assert response.status_code == 200, response.text
    assert calls == []


def _seed_people(app: Any) -> str:
    """Admin (1) and Bruno (2); returns a session cookie for Bruno."""
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    credential = hash_password("second person's password")
    with app.state.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id,username,display_name,password_hash,password_salt,is_admin,"
                "created_at,updated_at) VALUES (2,'bruno','Bruno',:digest,:salt,0,:now,:now)"
            ),
            {"digest": credential.digest, "salt": credential.salt, "now": now},
        )
    return SessionStore(app.state.engine).create(2).token


@pytest.mark.anyio
async def test_home_answers_for_the_person_asking(tmp_path: Path) -> None:
    year = date.today().year
    async with _client(tmp_path, auth="on") as (app, client):
        token = _seed_people(app)
        _entry(app, "Admin reading", "book", "reading", user=1)
        _entry(app, "Admin pile", "book", "to_read", user=1)
        _entry(app, "Admin finished", "book", "read", user=1, date_finished=f"{year}-01-02")
        _goal(app, "book", 3, "month", user=1)
        mine = _entry(app, "Bruno watching", "anime", "watching", user=2)
        client.cookies.set(COOKIE_NAME, token)
        body = (await client.get("/api/home")).json()

    titles = json.dumps(body)
    assert "Admin" not in titles
    assert [row["id"] for row in body["now"]] == [mine]
    assert body["next"] == []
    assert body["greeting"]["entries"] == 1
    assert body["greeting"]["goals"] == []
    assert body["year"]["goals"] == []
    assert all(month["count"] == 0 for month in body["year"]["months"])
    assert [tile["item_type"] for tile in body["domains"]] == ["anime"]


@pytest.mark.anyio
async def test_home_without_a_session_is_refused_when_auth_is_on(tmp_path: Path) -> None:
    async with _client(tmp_path, auth="on") as (app, client):
        _seed_people(app)
        response = await client.get("/api/home")
    assert response.status_code == 401


def _seed_large(app: Any, count: int) -> None:
    """`count` entries over every domain, with scores, covers, finishes and a pile."""
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    year = date.today().year
    domains = list(DOMAINS.values())
    items: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    for index in range(1, count + 1):
        domain = domains[index % len(domains)]
        statuses = [status.value for status in domain.statuses]
        status = statuses[index % len(statuses)]
        finished = next((s.value for s in domain.statuses if s.finished), None)
        items.append(
            {
                "id": index,
                "type": domain.item_type,
                "title": f"Title {index:05d}",
                "cover_path": None if index % 13 == 0 else f"covers/{index}.jpg",
                "metadata": json.dumps({"creators": [f"Creator {index % 97}"]}),
                "creator_normalized": f"creator {index % 97}",
                "now": now,
            }
        )
        entries.append(
            {
                "id": index,
                "item_id": index,
                "status": status,
                "score": None if index % 7 == 0 else 1 + (index % 10),
                "date_added": f"20{10 + index % 16}-0{1 + index % 9}-01T00:00:00Z",
                "date_finished": f"{year - index % 3}-{1 + index % 12:02d}-10"
                if status == finished
                else None,
                "now": now,
            }
        )
    with app.state.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO items (id, type, title, cover_path, identifiers, metadata,"
                " creator_primary_normalized, created_at, updated_at)"
                " VALUES (:id, :type, :title, :cover_path, '{}', :metadata,"
                " :creator_normalized, :now, :now)"
            ),
            items,
        )
        connection.execute(
            text(
                "INSERT INTO entries (id, user_id, item_id, status, score, date_added,"
                " date_finished, reread_count, score_provisional, created_at, updated_at)"
                " VALUES (:id, 1, :item_id, :status, :score, :date_added, :date_finished,"
                " 0, 0, :now, :now)"
            ),
            entries,
        )
    for item_type in DOMAINS:
        if "date_finished" in DOMAINS[item_type].entry_fields:
            _goal(app, item_type, 2, "month")


#: Sprint 130's budget is a workstation figure: 117-133 ms measured on the owner's machine.
#: GitHub's shared runner measured the same code at 228 ms median (PR #41), about 1.9x
#: slower across the whole request, so CI gets the same budget scaled by 2 rather than
#: a different test.
_HOME_BUDGET = 0.150 * (2 if os.environ.get("CI") else 1)


@pytest.mark.anyio
async def test_home_answers_inside_its_budget_on_a_large_library(tmp_path: Path) -> None:
    async with _client(tmp_path) as (app, client):
        _seed_large(app, 10_000)
        first = await client.get("/api/home")
        assert first.status_code == 200, first.text
        assert sum(tile["count"] for tile in first.json()["domains"]) > 7_000
        timings = []
        for _ in range(5):
            started = time.perf_counter()
            response = await client.get("/api/home")
            timings.append(time.perf_counter() - started)
            assert response.status_code == 200
    print(f"home median {statistics.median(timings) * 1000:.1f} ms")
    assert statistics.median(timings) < _HOME_BUDGET, timings
