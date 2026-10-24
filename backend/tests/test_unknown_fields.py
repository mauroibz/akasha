"""What the owner does not remember (Sprint 124, DEC-179): kept per entry and field, so a
question about it is not asked again."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import httpx
import pytest

from book_tracker.config import Settings
from book_tracker.main import create_app
from book_tracker.migrations import upgrade

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _add(client: httpx.AsyncClient, title: str, item_type: str, **entry: Any) -> int:
    created = await client.post(
        "/api/entries",
        json={
            "manual": {"item_type": item_type, "title": title, "metadata": {"creators": ["A"]}},
            "idempotency_key": f"{item_type}:{title}",
            **entry,
        },
    )
    assert created.status_code == 201, created.text
    return int(created.json()["entry"]["id"])


async def test_an_unknown_is_kept_returned_and_exported(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", user_agent_contact="t@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        book = await _add(client, "Rayuela", "book", status="read")
        fresh = (await client.get(f"/api/entries/{book}")).json()
        saved = await client.patch(
            f"/api/entries/{book}", json={"unknown_fields": ["date_finished", "formats"]}
        )
        again = (await client.get(f"/api/entries/{book}")).json()
        listed = (await client.get("/api/entries")).json()["items"][0]
        exported = (await client.get("/api/export?format=json")).json()
        cleared = (await client.patch(f"/api/entries/{book}", json={"unknown_fields": []})).json()
    assert fresh["unknown_fields"] == []
    assert saved.status_code == 200, saved.text
    assert again["unknown_fields"] == ["date_finished", "formats"]
    assert listed["unknown_fields"] == ["date_finished", "formats"]
    assert exported["entries"][0]["unknown_fields"] == ["date_finished", "formats"]
    assert cleared["unknown_fields"] == []


async def test_only_a_field_the_domain_has_can_be_unknown(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", user_agent_contact="t@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        film = await _add(client, "Dune", "movie", status="watched")
        started = await client.patch(
            f"/api/entries/{film}", json={"unknown_fields": ["date_started"]}
        )
        nonsense = await client.patch(f"/api/entries/{film}", json={"unknown_fields": ["score"]})
        place = await client.patch(f"/api/entries/{film}", json={"unknown_fields": ["location"]})
    assert started.status_code == 422
    assert nonsense.status_code == 422
    assert place.status_code == 200
    assert place.json()["unknown_fields"] == ["location"]


def test_migration_0033_arrives_and_leaves(tmp_path: Path) -> None:
    from alembic import command
    from book_tracker.migrations import alembic_config

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    configured = Settings(data_dir=data_dir, user_agent_contact="t@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url, revision="0032_shelf_suggestion_dismissals")
    upgrade(configured.database_url, revision="head")
    columns = lambda: {  # noqa: E731
        row[1]
        for row in sqlite3.connect(data_dir / "books.db").execute("PRAGMA table_info(entries)")
    }
    assert "unknown_fields" in columns()
    command.downgrade(alembic_config(configured.database_url), "0032_shelf_suggestion_dismissals")
    assert "unknown_fields" not in columns()
