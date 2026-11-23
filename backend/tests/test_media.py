"""Your media (Sprint 143, DEC-193): an ordered list per person, each medium front, kept or off."""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
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
from book_tracker.migrations import upgrade


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


def _entry(app: Any, title: str, item_type: str, status: str, user: int = 1, **values: Any) -> int:
    created = DomainRepository(app.state.engine, user).create_or_get_entry(
        title=title, item_type=item_type
    )
    assignments = ", ".join(["status = :status", *(f"{key} = :{key}" for key in values)])
    with app.state.engine.begin() as connection:
        connection.execute(
            text(f"UPDATE entries SET {assignments} WHERE id = :id"),
            {"status": status, "id": created.entry_id, **values},
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


def _pairs(body: dict[str, Any]) -> list[tuple[str, str]]:
    return [(row["item_type"], row["presence"]) for row in body["media"]]


@pytest.mark.anyio
async def test_a_new_library_shows_every_medium_until_the_person_chooses(tmp_path: Path) -> None:
    async with _client(tmp_path) as (_app, client):
        response = await client.get("/api/media")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["chosen"] is False
    # Registry order, everything in front: nothing is hidden from someone starting out.
    assert _pairs(body) == [(item_type, "front") for item_type in DOMAINS]
    book = body["media"][0]
    assert book == {
        "item_type": "book",
        "label": "Books",
        "presence": "front",
        "held": False,
    }


@pytest.mark.anyio
async def test_without_a_choice_only_the_media_held_are_shown(tmp_path: Path) -> None:
    """The proposal's rule: a medium with no entries that was never chosen is not shown."""
    async with _client(tmp_path) as (app, client):
        _entry(app, "Frieren", "anime", "watching")
        _entry(app, "Unsorted import", "movie", "unsorted")
        body = (await client.get("/api/media")).json()
    assert body["chosen"] is False
    presence = dict(_pairs(body))
    assert presence["anime"] == "front"
    # What an import left in the Inbox is not yet held.
    assert presence["movie"] == "off"
    assert presence["book"] == "off"
    assert [row["item_type"] for row in body["media"]] == list(DOMAINS)
    assert {row["item_type"] for row in body["media"] if row["held"]} == {"anime"}


@pytest.mark.anyio
async def test_a_chosen_order_and_presence_read_back(tmp_path: Path) -> None:
    async with _client(tmp_path) as (app, client):
        _entry(app, "Rayuela", "book", "read")
        _entry(app, "OK Computer", "album", "owned")
        chosen = [
            {"item_type": "anime", "presence": "front"},
            {"item_type": "book", "presence": "kept"},
        ]
        put = await client.put("/api/media", json={"media": chosen})
        got = (await client.get("/api/media")).json()
    assert put.status_code == 200, put.text
    assert got == put.json()
    assert got["chosen"] is True
    pairs = _pairs(got)
    assert pairs[:2] == [("anime", "front"), ("book", "kept")]
    rest = dict(pairs[2:])
    # A medium the list does not name: kept when the person holds some, off when not.
    assert rest["album"] == "kept"
    assert rest["movie"] == "off" and rest["series"] == "off"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("media", "code"),
    [
        ([{"item_type": "comic", "presence": "front"}], "unknown_medium"),
        (
            [
                {"item_type": "book", "presence": "front"},
                {"item_type": "book", "presence": "off"},
            ],
            "duplicate_medium",
        ),
    ],
)
async def test_a_list_naming_what_is_not_a_medium_or_one_twice_is_refused(
    tmp_path: Path, media: list[dict[str, str]], code: str
) -> None:
    async with _client(tmp_path) as (_app, client):
        response = await client.put("/api/media", json={"media": media})
        after = (await client.get("/api/media")).json()
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code
    assert after["chosen"] is False


@pytest.mark.anyio
async def test_a_presence_that_is_not_one_of_the_three_is_refused(tmp_path: Path) -> None:
    async with _client(tmp_path) as (_app, client):
        response = await client.put(
            "/api/media", json={"media": [{"item_type": "book", "presence": "hidden"}]}
        )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_one_persons_media_are_not_anothers(tmp_path: Path) -> None:
    async with _client(tmp_path, auth="on") as (app, client):
        bruno = _seed_bruno(app)
        admin = SessionStore(app.state.engine).create(1).token
        client.cookies.set(COOKIE_NAME, admin)
        await client.put("/api/media", json={"media": [{"item_type": "album", "presence": "off"}]})
        client.cookies.set(COOKIE_NAME, bruno)
        theirs = (await client.get("/api/media")).json()
        client.cookies.clear()
        anonymous = await client.get("/api/media")
    assert theirs["chosen"] is False
    assert dict(_pairs(theirs))["album"] == "front"
    assert anonymous.status_code == 401


@pytest.mark.anyio
async def test_the_front_of_the_library_reads_front_media_only(tmp_path: Path) -> None:
    year = datetime.now(UTC).year
    async with _client(tmp_path) as (app, client):
        reading = _entry(app, "Rayuela", "book", "reading")
        watching = _entry(app, "Frieren", "anime", "watching")
        listening = _entry(app, "Severance", "series", "watching")
        _entry(app, "Dune", "book", "to_read")
        _entry(app, "Mushishi", "anime", "plan_to_watch")
        _entry(app, "Ficciones", "book", "read", date_finished=f"{year}-01-02")
        _entry(app, "Monster", "anime", "completed", date_finished=f"{year}-01-03")
        everything = (await client.get("/api/home")).json()
        await client.put(
            "/api/media",
            json={
                "media": [
                    {"item_type": "book", "presence": "front"},
                    {"item_type": "anime", "presence": "kept"},
                    {"item_type": "series", "presence": "off"},
                ]
            },
        )
        front = (await client.get("/api/home")).json()
        # Kept and off media are still in the library itself.
        listed = (await client.get("/api/entries", params={"type": "anime"})).json()

    assert {row["id"] for row in everything["now"]} == {reading, watching, listening}
    assert [row["id"] for row in front["now"]] == [reading]
    assert {row["entry"]["item"]["type"] for row in front["lately"]} == {"book"}
    assert {row["entry"]["item"]["type"] for row in front["next"]} == {"book"}
    assert front["greeting"]["active"]["entry"]["id"] == reading
    assert listed["total"] == 3


@pytest.mark.anyio
async def test_the_greeting_says_nothing_is_under_way_when_only_kept_media_are(
    tmp_path: Path,
) -> None:
    async with _client(tmp_path) as (app, client):
        _entry(app, "Frieren", "anime", "watching")
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
        body = (await client.get("/api/home")).json()
    assert body["now"] == []
    assert body["greeting"]["active"] is None


# -- migration 0039 ---------------------------------------------------------------------


def test_0039_upgrades_and_downgrades_on_a_real_shaped_library(tmp_path: Path) -> None:
    from alembic import command
    from book_tracker.migrations import alembic_config

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    configured = Settings(data_dir=data_dir, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    database = data_dir / "books.db"
    upgrade(configured.database_url, revision="0038_item_embeddings")
    connection = sqlite3.connect(database)
    connection.execute(
        "INSERT INTO users (id,username,display_name,password_hash,password_salt,is_admin,"
        "created_at,updated_at) VALUES (2,'bruno','Bruno','x','y',0,'n','n')"
    )
    connection.execute(
        "INSERT INTO items (id, type, title, identifiers, metadata, created_at, updated_at)"
        " VALUES (1, 'book', 'Rayuela', '{}', '{}', 'n', 'n')"
    )
    connection.commit()
    assert not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name = 'media_preferences'"
    ).fetchone()
    connection.close()

    upgrade(configured.database_url, revision="head")
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys = ON")
    columns = {row[1]: row for row in connection.execute("PRAGMA table_info(media_preferences)")}
    assert set(columns) == {"user_id", "media_json", "updated_at"}
    assert columns["user_id"][5] == 1  # the primary key: one list per person
    keys = connection.execute("PRAGMA foreign_key_list(media_preferences)").fetchall()
    assert [(row[2], row[3], row[4], row[6]) for row in keys] == [
        ("users", "user_id", "id", "CASCADE")
    ]
    connection.execute(
        "INSERT INTO media_preferences (user_id, media_json, updated_at) VALUES (2, '[]', 'n')"
    )
    connection.execute("DELETE FROM users WHERE id = 2")
    assert connection.execute("SELECT count(*) FROM media_preferences").fetchone() == (0,)
    assert connection.execute("SELECT count(*) FROM items").fetchone() == (1,)
    connection.commit()
    connection.close()

    command.downgrade(alembic_config(configured.database_url), "0038_item_embeddings")
    connection = sqlite3.connect(database)
    assert not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name = 'media_preferences'"
    ).fetchone()
    assert connection.execute("SELECT count(*) FROM items").fetchone() == (1,)
    connection.close()
