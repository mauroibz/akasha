"""Home's one read (Sprint 130, DEC-183): `GET /api/home`.

Five sections from stored data only: a greeting, what is under way, what is next, the
year, and one tile per registered domain that holds entries. No provider is consulted
while it renders, it answers per person, and it stays inside its time budget on a
10,000-entry library.
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
    assert set(body) == {"greeting", "now", "next", "year", "domains"}
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


@pytest.mark.anyio
async def test_the_five_sections_read_the_library(tmp_path: Path) -> None:
    today = date.today()
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
    assert greeting["goals"] == [
        {"item_type": "book", "target": 24, "count": 2},
        {"item_type": "movie", "target": 6, "count": 1},
    ]

    assert [row["id"] for row in body["now"]] == [reading, watching]

    nexts = body["next"]
    assert len(nexts) == 5
    assert all(row["reason"] in {"creator", "waiting"} for row in nexts)
    # The goal picks' order, per domain, taken in turn: the longest-waiting book and
    # the watchlisted film lead.
    assert nexts[0]["entry"]["id"] == pile[0]
    assert nexts[1]["entry"]["item"]["title"] == "Later"
    assert [row["entry"]["id"] for row in nexts[2:]] == pile[1:4]

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
    assert statistics.median(timings) < 0.150, timings
