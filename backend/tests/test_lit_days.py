"""Every day (Sprint 147, DEC-193): a light per day something was read, watched or finished."""

from __future__ import annotations

import sqlite3
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
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.main import create_app
from book_tracker.migrations import alembic_config, upgrade


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@asynccontextmanager
async def _client(tmp_path: Path, **extra: Any) -> AsyncIterator[tuple[Any, httpx.AsyncClient]]:
    app = create_app(
        Settings(data_dir=tmp_path / "data", user_agent_contact="test@example.invalid", **extra)
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        yield app, client


def _entry(app: Any, title: str, item_type: str, status: str, user: int = 1) -> int:
    created = DomainRepository(app.state.engine, user).create_or_get_entry(
        title=title, item_type=item_type
    )
    with app.state.engine.begin() as connection:
        connection.execute(
            text("UPDATE entries SET status = :status WHERE id = :id"),
            {"status": status, "id": created.entry_id},
        )
    return created.entry_id


def _seed_bruno(app: Any) -> str:
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


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


async def _days(client: httpx.AsyncClient, start: str, end: str) -> dict[str, list[int]]:
    response = await client.get("/api/lit-days", params={"from": start, "to": end})
    assert response.status_code == 200, response.text
    return {
        row["day"]: [entry["id"] for entry in row["entries"]] for row in response.json()["days"]
    }


@pytest.mark.anyio
async def test_logging_progress_lights_today_for_that_entry(tmp_path: Path) -> None:
    today = _today()
    async with _client(tmp_path) as (app, client):
        reading = _entry(app, "Rayuela", "book", "reading")
        before = await _days(client, today, today)
        patched = await client.patch(f"/api/entries/{reading}", json={"progress": 40})
        after = await _days(client, today, today)
        # A change that is not progress lights nothing more.
        await client.patch(f"/api/entries/{reading}", json={"notes": "slow"})
        still = await _days(client, today, today)
    assert patched.status_code == 200, patched.text
    assert before == {}
    assert after == {today: [reading]}
    assert still == after


@pytest.mark.anyio
async def test_finishing_lights_the_day_it_was_finished(tmp_path: Path) -> None:
    async with _client(tmp_path) as (app, client):
        reading = _entry(app, "Rayuela", "book", "reading")
        done = await client.patch(
            f"/api/entries/{reading}", json={"status": "read", "date_finished": "2026-03-02"}
        )
        days = await _days(client, "2026-03-01", "2026-03-31")
    assert done.status_code == 200, done.text
    assert days == {"2026-03-02": [reading]}


@pytest.mark.anyio
async def test_a_medium_that_is_not_in_front_lights_nothing_by_itself(tmp_path: Path) -> None:
    today = _today()
    async with _client(tmp_path) as (app, client):
        watching = _entry(app, "Frieren", "anime", "watching")
        _entry(app, "Rayuela", "book", "read")
        await client.put(
            "/api/media",
            json={
                "media": [
                    {"item_type": "book", "presence": "front"},
                    {"item_type": "anime", "presence": "kept"},
                ]
            },
        )
        await client.patch(f"/api/entries/{watching}", json={"progress": 3})
        days = await _days(client, today, today)
    assert days == {}


@pytest.mark.anyio
async def test_lighting_a_day_by_hand_says_what_it_was_for_or_nothing(tmp_path: Path) -> None:
    today = _today()
    yesterday = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
    async with _client(tmp_path) as (app, client):
        book = _entry(app, "Rayuela", "book", "reading")
        show = _entry(app, "Frieren", "anime", "watching")
        both = await client.put(f"/api/lit-days/{today}", json={"entry_ids": [book, show]})
        bare = await client.put(f"/api/lit-days/{yesterday}", json={"entry_ids": []})
        days = await _days(client, yesterday, today)
        # Saying it again replaces what the day was for, and changes no entry.
        await client.put(f"/api/lit-days/{today}", json={"entry_ids": [show]})
        again = await _days(client, today, today)
        entry = (await client.get(f"/api/entries/{book}")).json()
    assert both.status_code == 200, both.text
    assert bare.status_code == 200, bare.text
    assert both.json() == {
        "day": today,
        "entries": both.json()["entries"],
    }
    assert sorted(days[today]) == sorted([book, show])
    assert days[yesterday] == []
    assert again == {today: [show]}
    assert entry["status"] == "reading" and entry["progress"] is None


@pytest.mark.anyio
async def test_unlighting_a_day_takes_everything_off_it(tmp_path: Path) -> None:
    today = _today()
    async with _client(tmp_path) as (app, client):
        book = _entry(app, "Rayuela", "book", "reading")
        await client.patch(f"/api/entries/{book}", json={"progress": 12})
        await client.put(f"/api/lit-days/{today}", json={"entry_ids": []})
        gone = await client.delete(f"/api/lit-days/{today}")
        days = await _days(client, today, today)
    assert gone.status_code == 204
    assert days == {}


@pytest.mark.anyio
async def test_what_cannot_be_lit_is_refused(tmp_path: Path) -> None:
    today = date.fromisoformat(_today())
    # Two days on, so the test holds whatever zone the server counts today in.
    future = (today + timedelta(days=2)).isoformat()
    async with _client(tmp_path) as (_app, client):
        ahead = await client.put(f"/api/lit-days/{future}", json={"entry_ids": []})
        malformed = await client.put("/api/lit-days/23-11-2026", json={"entry_ids": []})
        stranger = await client.put(
            f"/api/lit-days/{today.isoformat()}", json={"entry_ids": [9999]}
        )
        wide = await client.get("/api/lit-days", params={"from": "2026-01-01", "to": "2026-12-31"})
        backwards = await client.get(
            "/api/lit-days", params={"from": "2026-03-02", "to": "2026-03-01"}
        )
    assert ahead.status_code == 422
    assert ahead.json()["error"]["code"] == "future_day"
    assert malformed.status_code == 422
    assert stranger.status_code == 422
    assert stranger.json()["error"]["code"] == "unknown_entry"
    # A week or a month, never a year.
    assert wide.status_code == 422
    assert wide.json()["error"]["code"] == "range_too_long"
    assert backwards.status_code == 422


@pytest.mark.anyio
async def test_one_persons_days_and_entries_are_not_anothers(tmp_path: Path) -> None:
    today = _today()
    async with _client(tmp_path, auth="on") as (app, client):
        bruno = _seed_bruno(app)
        admin = SessionStore(app.state.engine).create(1).token
        mine = _entry(app, "Rayuela", "book", "reading", user=1)
        client.cookies.set(COOKIE_NAME, admin)
        await client.put(f"/api/lit-days/{today}", json={"entry_ids": [mine]})
        client.cookies.set(COOKIE_NAME, bruno)
        theirs = await _days(client, today, today)
        borrowed = await client.put(f"/api/lit-days/{today}", json={"entry_ids": [mine]})
        client.cookies.clear()
        anonymous = await client.get("/api/lit-days", params={"from": today, "to": today})
    assert theirs == {}
    assert borrowed.status_code == 422
    assert anonymous.status_code == 401


# -- migration 0040 ---------------------------------------------------------------------


def test_0040_backfills_from_stored_dates_and_cascades(tmp_path: Path) -> None:
    from alembic import command

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    configured = Settings(data_dir=data_dir, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    database = data_dir / "books.db"
    upgrade(configured.database_url, revision="0039_media_preferences")
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        "INSERT INTO users (id,username,display_name,password_hash,password_salt,is_admin,"
        "created_at,updated_at) VALUES (2,'bruno','Bruno','x','y',0,'n','n')"
    )
    for item in (1, 2, 3):
        connection.execute(
            "INSERT INTO items (id, type, title, identifiers, metadata, created_at, updated_at)"
            " VALUES (?, 'book', ?, '{}', '{}', 'n', 'n')",
            (item, f"Book {item}"),
        )
    rows = [
        (1, 1, 1, "read", "2026-03-01", "2026-03-09"),
        (2, 1, 2, "reading", "2026-03-09", None),
        # A date that is not a day, as an old import can leave: skipped, not fatal.
        (3, 2, 3, "read", None, "2026"),
    ]
    for entry, user, item, status, started, finished in rows:
        connection.execute(
            "INSERT INTO entries (id, user_id, item_id, status, date_added, date_started,"
            " date_finished, reread_count, score_provisional, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 'n', ?, ?, 0, 0, 'n', 'n')",
            (entry, user, item, status, started, finished),
        )
    connection.commit()
    connection.close()

    upgrade(configured.database_url, revision="head")
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys = ON")
    lit = connection.execute(
        "SELECT user_id, day, entry_id, source FROM lit_days ORDER BY day, entry_id"
    ).fetchall()
    assert lit == [
        (1, "2026-03-01", 1, "progress"),
        # Started and finished by two entries on one day: one row each.
        (1, "2026-03-09", 1, "finish"),
        (1, "2026-03-09", 2, "progress"),
    ]
    # A day lit by hand for nothing in particular, once per person and day.
    connection.execute(
        "INSERT INTO lit_days (user_id, day, entry_id, source, created_at)"
        " VALUES (1, '2026-03-10', NULL, 'tap', 'n')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO lit_days (user_id, day, entry_id, source, created_at)"
            " VALUES (1, '2026-03-10', NULL, 'tap', 'n')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO lit_days (user_id, day, entry_id, source, created_at)"
            " VALUES (1, '2026-03-09', 2, 'tap', 'n')"
        )
    connection.execute("DELETE FROM entries WHERE id = 2")
    assert connection.execute("SELECT count(*) FROM lit_days WHERE entry_id = 2").fetchone() == (0,)
    # A person's days go with the person.
    connection.execute(
        "INSERT INTO lit_days (user_id, day, entry_id, source, created_at)"
        " VALUES (2, '2026-03-11', NULL, 'tap', 'n')"
    )
    connection.execute("DELETE FROM entries WHERE user_id = 2")
    connection.execute("DELETE FROM users WHERE id = 2")
    assert connection.execute("SELECT count(*) FROM lit_days WHERE user_id = 2").fetchone() == (0,)
    connection.commit()
    connection.close()

    command.downgrade(alembic_config(configured.database_url), "0039_media_preferences")
    connection = sqlite3.connect(database)
    assert not connection.execute("SELECT 1 FROM sqlite_master WHERE name = 'lit_days'").fetchone()
    assert connection.execute("SELECT count(*) FROM items").fetchone() == (3,)
    connection.close()
