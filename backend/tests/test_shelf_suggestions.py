"""Suggested shelves (Sprint 119, DEC-176): proposed from what the library holds, never from
a provider; accepted in one request or dismissed for good."""

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


async def _add(
    client: httpx.AsyncClient,
    title: str,
    creator: str,
    item_type: str = "book",
    **metadata: Any,
) -> int:
    created = await client.post(
        "/api/entries",
        json={
            "manual": {
                "item_type": item_type,
                "title": title,
                "metadata": {"creators": [creator], **metadata},
            },
            "idempotency_key": f"{item_type}:{title}:{creator}",
            "confirm_near_match": True,
        },
    )
    assert created.status_code == 201, created.text
    return int(created.json()["entry"]["id"])


async def _library(client: httpx.AsyncClient) -> dict[str, int]:
    ids: dict[str, int] = {}
    for title in ("The Dispossessed", "The Left Hand of Darkness", "The Lathe of Heaven"):
        ids[title] = await _add(client, title, "Ursula K. Le Guin")
    ids["Dune"] = await _add(client, "Dune", "Frank Herbert", series="Dune Chronicles")
    ids["Dune Messiah"] = await _add(
        client, "Dune Messiah", "Frank Herbert", series="Dune Chronicles"
    )
    ids["Dune film"] = await _add(client, "Dune: Part One", "Denis Villeneuve", "movie")
    ids["Stoner"] = await _add(client, "Stoner", "John Williams")
    return ids


async def test_shelves_are_proposed_from_creators_series_and_works(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", user_agent_contact="t@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        ids = await _library(client)
        found = await client.get("/api/shelves/suggestions")
    assert found.status_code == 200
    by_name = {row["name"]: row for row in found.json()}
    assert set(by_name) == {"Ursula K. Le Guin", "Dune Chronicles", "Dune"}
    assert by_name["Ursula K. Le Guin"]["reason"] == "3 by Ursula K. Le Guin"
    assert by_name["Dune Chronicles"]["reason"] == "2 in Dune Chronicles"
    assert by_name["Dune"]["reason"] == "Dune in 2 libraries"
    assert {m["entry_id"] for m in by_name["Dune"]["members"]} == {
        ids["Dune"],
        ids["Dune film"],
    }


async def test_accepting_makes_the_shelf_and_dismissing_is_for_good(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", user_agent_contact="t@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        ids = await _library(client)
        found = {
            row["name"]: row["key"] for row in (await client.get("/api/shelves/suggestions")).json()
        }
        accepted = await client.post(
            "/api/shelves/suggestions/accept", json={"key": found["Ursula K. Le Guin"]}
        )
        dismissed = await client.post(
            "/api/shelves/suggestions/dismiss", json={"key": found["Dune"]}
        )
        unknown = await client.post(
            "/api/shelves/suggestions/accept", json={"key": "creator:nobody"}
        )
        left = {row["name"] for row in (await client.get("/api/shelves/suggestions")).json()}
        shelf = await client.get("/api/entries", params={"shelf": accepted.json()["slug"]})
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["name"] == "Ursula K. Le Guin"
    assert dismissed.status_code == 204
    assert unknown.status_code == 404
    # The accepted one now matches a shelf, and the dismissed one never returns.
    assert left == {"Dune Chronicles"}
    assert {row["id"] for row in shelf.json()["items"]} == {
        ids["The Dispossessed"],
        ids["The Left Hand of Darkness"],
        ids["The Lathe of Heaven"],
    }


async def test_a_suggestion_is_never_asked_of_a_provider(tmp_path: Path) -> None:
    """No provider is consulted: the app has none wired and the answer still comes."""
    app = create_app(Settings(data_dir=tmp_path / "data", user_agent_contact="t@example.invalid"))
    async with app.router.lifespan_context(app):
        app.state.providers = {}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            await _library(client)
            found = await client.get("/api/shelves/suggestions")
    assert found.status_code == 200
    assert len(found.json()) == 3


def test_migration_0032_arrives_and_leaves(tmp_path: Path) -> None:
    from alembic import command
    from book_tracker.migrations import alembic_config

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    configured = Settings(data_dir=data_dir, user_agent_contact="t@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url, revision="0031_score_rank")
    upgrade(configured.database_url, revision="head")
    connection = sqlite3.connect(data_dir / "books.db")
    assert "shelf_suggestion_dismissals" in {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master")
    }
    connection.close()
    command.downgrade(alembic_config(configured.database_url), "0031_score_rank")
    connection = sqlite3.connect(data_dir / "books.db")
    assert "shelf_suggestion_dismissals" not in {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master")
    }
    connection.close()


async def test_a_member_s_cover_is_its_item_s(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", user_agent_contact="t@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        # A first entry whose id and item id differ from the next ones'.
        await _add(client, "Unrelated", "Nobody")
        await client.delete("/api/entries/1")
        await _library(client)
        entry = (await client.get("/api/entries/2")).json()
        from book_tracker.infrastructure.repositories import DomainRepository

        DomainRepository(app.state.engine, 1).set_cover_path(
            entry["item_id"], f"covers/{entry['item_id']}.jpg"
        )
        found = (await client.get("/api/shelves/suggestions")).json()
    covers = [
        member["cover_url"]
        for row in found
        for member in row["members"]
        if member["entry_id"] == entry["id"]
    ]
    assert covers and covers[0].startswith(f"/api/items/{entry['item_id']}/cover")
