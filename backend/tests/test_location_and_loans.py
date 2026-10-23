"""Where a thing is, and who has it (Sprint 110, DEC-176).

A location is one line of free text on the entry; a loan is a row of its own, because a
thing is lent more than once and the history is worth keeping. Both are shared across
every domain: nothing about "where is it" or "who has it" belongs to books alone.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import httpx
import pytest

from book_tracker.config import Settings
from book_tracker.main import create_app
from book_tracker.migrations import upgrade

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", user_agent_contact="test@example.invalid")


async def _entry(client: httpx.AsyncClient, title: str, item_type: str = "book") -> int:
    created = await client.post(
        "/api/entries",
        json={"manual": {"item_type": item_type, "title": title}, "idempotency_key": title},
    )
    assert created.status_code == 201, created.text
    return int(created.json()["entry"]["id"])


async def test_a_location_is_set_trimmed_cleared_and_bounded(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        entry_id = await _entry(client, "Rayuela")
        fresh = await client.get(f"/api/entries/{entry_id}")
        placed = await client.patch(
            f"/api/entries/{entry_id}", json={"location": "  Living room, shelf 2 "}
        )
        cleared = await client.patch(f"/api/entries/{entry_id}", json={"location": "   "})
        too_long = await client.patch(f"/api/entries/{entry_id}", json={"location": "x" * 121})
    assert fresh.json()["location"] is None
    assert fresh.json()["loan"] is None
    assert placed.json()["location"] == "Living room, shelf 2"
    assert cleared.json()["location"] is None
    assert too_long.status_code == 422


async def test_an_album_and_a_film_have_a_place_too(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        album = await _entry(client, "Kid A", "album")
        film = await client.post(
            "/api/entries",
            json={
                "manual": {"item_type": "movie", "title": "Solaris"},
                "idempotency_key": "film",
            },
        )
        placed = await client.patch(f"/api/entries/{album}", json={"location": "Vinyl crate"})
        film_placed = await client.patch(
            f"/api/entries/{film.json()['entry']['id']}", json={"location": "DVD box"}
        )
    assert placed.json()["location"] == "Vinyl crate"
    assert film_placed.json()["location"] == "DVD box"


async def test_a_thing_is_lent_once_at_a_time_and_its_history_is_kept(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        entry_id = await _entry(client, "Rayuela")
        lent = await client.post(
            f"/api/entries/{entry_id}/loans",
            json={"person": " Sofi ", "lent_on": "2026-04-02", "note": "with the bookmark"},
        )
        twice = await client.post(
            f"/api/entries/{entry_id}/loans", json={"person": "Juan", "lent_on": "2026-04-03"}
        )
        nameless = await client.post(
            f"/api/entries/{entry_id}/loans", json={"person": "  ", "lent_on": "2026-04-03"}
        )
        on_entry = await client.get(f"/api/entries/{entry_id}")
        loan_id = lent.json()["id"]
        returned = await client.patch(f"/api/loans/{loan_id}", json={"returned_on": "2026-05-10"})
        early = await client.patch(f"/api/loans/{loan_id}", json={"returned_on": "2026-03-01"})
        again = await client.post(
            f"/api/entries/{entry_id}/loans", json={"person": "Juan", "lent_on": "2026-06-01"}
        )
        history = await client.get(f"/api/entries/{entry_id}/loans")
        removed = await client.delete(f"/api/loans/{again.json()['id']}")
        after = await client.get(f"/api/entries/{entry_id}/loans")
    assert lent.status_code == 201, lent.text
    assert lent.json()["person"] == "Sofi"
    assert lent.json()["returned_on"] is None
    assert twice.status_code == 409
    assert twice.json()["error"]["code"] == "already_lent"
    assert nameless.status_code == 422
    assert on_entry.json()["loan"]["person"] == "Sofi"
    assert returned.json()["returned_on"] == "2026-05-10"
    # A return before the loan is a typing slip, refused rather than stored.
    assert early.status_code == 422
    assert again.status_code == 201
    assert [row["person"] for row in history.json()] == ["Juan", "Sofi"]
    assert removed.status_code == 204
    assert [row["person"] for row in after.json()] == ["Sofi"]


async def test_what_is_out_and_the_places_used(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        first = await _entry(client, "Rayuela")
        second = await _entry(client, "Ficciones")
        third = await _entry(client, "Stoner")
        await client.post(
            f"/api/entries/{second}/loans", json={"person": "Juan", "lent_on": "2026-05-01"}
        )
        older = await client.post(
            f"/api/entries/{first}/loans", json={"person": "Sofi", "lent_on": "2026-04-02"}
        )
        back = await client.post(
            f"/api/entries/{third}/loans", json={"person": "Ana", "lent_on": "2026-01-01"}
        )
        await client.patch(f"/api/loans/{back.json()['id']}", json={"returned_on": "2026-02-01"})
        for entry_id, place in ((first, "Hall"), (second, "Hall"), (third, "Study")):
            await client.patch(f"/api/entries/{entry_id}", json={"location": place})
        out = await client.get("/api/loans", params={"open": "true"})
        every = await client.get("/api/loans")
        places = await client.get("/api/locations")
        in_hall = await client.get("/api/entries", params={"location": "Hall"})
        lent_out = await client.get("/api/entries", params={"lent": "true"})
    assert [row["person"] for row in out.json()] == ["Sofi", "Juan"]
    assert out.json()[0]["entry"]["item"]["title"] == "Rayuela"
    assert out.json()[0]["id"] == older.json()["id"]
    assert len(every.json()) == 3
    assert places.json() == [{"location": "Hall", "count": 2}, {"location": "Study", "count": 1}]
    assert {row["item"]["title"] for row in in_hall.json()["items"]} == {"Rayuela", "Ficciones"}
    assert {row["item"]["title"] for row in lent_out.json()["items"]} == {"Rayuela", "Ficciones"}


async def test_deleting_an_entry_takes_its_loans(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        entry_id = await _entry(client, "Rayuela")
        await client.post(
            f"/api/entries/{entry_id}/loans", json={"person": "Sofi", "lent_on": "2026-04-02"}
        )
        await client.delete(f"/api/entries/{entry_id}")
        out = await client.get("/api/loans")
    assert out.json() == []


async def test_the_json_export_carries_location_and_loans(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        entry_id = await _entry(client, "Rayuela")
        await client.patch(f"/api/entries/{entry_id}", json={"location": "Hall"})
        await client.post(
            f"/api/entries/{entry_id}/loans",
            json={"person": "Sofi", "lent_on": "2026-04-02", "note": "careful"},
        )
        exported = await client.get("/api/export", params={"format": "json"})
    (entry,) = exported.json()["entries"]
    assert entry["location"] == "Hall"
    assert entry["loans"] == [
        {"person": "Sofi", "lent_on": "2026-04-02", "returned_on": None, "note": "careful"}
    ]


def test_migration_0028_arrives_and_leaves(tmp_path: Path) -> None:
    from alembic import command
    from book_tracker.migrations import alembic_config

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    configured = Settings(data_dir=data_dir, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url, revision="0027_progress_marks")
    upgrade(configured.database_url, revision="head")
    database = data_dir / "books.db"
    connection = sqlite3.connect(database)
    columns = {row[1]: row for row in connection.execute("PRAGMA table_info(entries)")}
    assert columns["location"][3] == 0
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    assert "loans" in tables
    connection.close()

    command.downgrade(alembic_config(configured.database_url), "0027_progress_marks")
    connection = sqlite3.connect(database)
    assert "location" not in {row[1] for row in connection.execute("PRAGMA table_info(entries)")}
    assert "loans" not in {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    connection.close()
