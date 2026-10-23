"""Duplicates, found from stored data and merged without loss (Sprint 113, DEC-176)."""

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


def _app(tmp_path: Path):  # type: ignore[no-untyped-def]
    return create_app(Settings(data_dir=tmp_path / "data", user_agent_contact="t@example.invalid"))


async def _add(
    client: httpx.AsyncClient,
    title: str,
    creator: str | None = "Julio Cortázar",
    item_type: str = "book",
    **entry: Any,
) -> dict[str, Any]:
    metadata = {"creators": [creator]} if creator else {}
    created = await client.post(
        "/api/entries",
        json={
            "manual": {"item_type": item_type, "title": title, "metadata": metadata},
            "idempotency_key": f"{item_type}:{title}:{creator}",
            # The add path asks before a second copy of a near match; an import does
            # not, which is how most duplicates arrive.
            "confirm_near_match": True,
            **entry,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["entry"]


async def test_the_same_work_twice_is_a_candidate_and_strangers_are_not(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        first = await _add(client, "Rayuela")
        second = await _add(client, "RAYUELA (Spanish Edition)", "julio cortazar")
        await _add(client, "Rayuela: edición conmemorativa", "Julio Cortázar ")
        await _add(client, "Rayuela", "Someone Else")
        await _add(client, "Rayuela", "Julio Cortázar", "movie")
        await _add(client, "Ficciones", "Jorge Luis Borges")
        found = await client.get("/api/duplicates")
    assert found.status_code == 200
    pairs = found.json()
    titles = sorted(
        tuple(sorted((pair["a"]["item"]["title"], pair["b"]["item"]["title"]))) for pair in pairs
    )
    # Three editions of one work by one author make three pairs; the other author's
    # Rayuela, the film and Ficciones make none.
    assert titles == [
        ("RAYUELA (Spanish Edition)", "Rayuela"),
        ("RAYUELA (Spanish Edition)", "Rayuela: edición conmemorativa"),
        ("Rayuela", "Rayuela: edición conmemorativa"),
    ]
    assert {pairs[0]["reason"]} == {"Same title and creator"}
    assert {pair["a"]["id"] for pair in pairs} | {pair["b"]["id"] for pair in pairs} >= {
        first["id"],
        second["id"],
    }


async def test_a_pair_said_to_differ_never_returns_and_can_be_taken_back(
    tmp_path: Path,
) -> None:
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        first = await _add(client, "Rayuela")
        second = await _add(client, "Rayuela (Alfaguara)")
        body = {"a": second["id"], "b": first["id"]}
        dismissed = await client.post("/api/duplicates/dismiss", json=body)
        again = await client.post("/api/duplicates/dismiss", json=body)
        after = await client.get("/api/duplicates")
        undone = await client.request("DELETE", "/api/duplicates/dismiss", json=body)
        back = await client.get("/api/duplicates")
    assert dismissed.status_code == 204
    assert again.status_code == 204
    assert after.json() == []
    assert undone.status_code == 204
    assert len(back.json()) == 1


async def test_a_merge_keeps_every_value_and_fills_only_what_is_empty(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        keep = await _add(client, "Rayuela", status="read", score=9)
        drop = await _add(client, "Rayuela (Alfaguara)", status="to_read", score=6)
        shelf_a = (await client.post("/api/shelves", json={"name": "Argentina"})).json()["id"]
        shelf_b = (await client.post("/api/shelves", json={"name": "Favourites"})).json()["id"]
        await client.patch(
            f"/api/entries/{keep['id']}",
            json={
                "notes": "Read it twice.",
                "date_finished": "2019-05-01",
                "shelf_ids": [shelf_a],
                "formats": ["digital"],
            },
        )
        await client.patch(
            f"/api/entries/{drop['id']}",
            json={
                "notes": "The hopscotch chapters.",
                "date_started": "2019-04-01",
                "date_finished": "2001-01-01",
                "shelf_ids": [shelf_a, shelf_b],
                "formats": ["physical"],
                "location": "Hall",
            },
        )
        await client.post(
            f"/api/entries/{drop['id']}/loans",
            json={"person": "Sofi", "lent_on": "2020-01-01", "returned_on": "2020-02-01"},
        )
        merged = await client.post(
            "/api/duplicates/merge", json={"keep": keep["id"], "drop": drop["id"]}
        )
        gone = await client.get(f"/api/entries/{drop['id']}")
        loans = await client.get(f"/api/entries/{keep['id']}/loans")
    assert merged.status_code == 200, merged.text
    entry = merged.json()
    # Kept as they were: status, score, the finish date.
    assert entry["status"] == "read"
    assert entry["score"] == 9
    assert entry["date_finished"] == "2019-05-01"
    # Filled where empty: the start date and the place.
    assert entry["date_started"] == "2019-04-01"
    assert entry["location"] == "Hall"
    # Both notes survive; neither is lost.
    assert entry["notes"] == "Read it twice.\n\nThe hopscotch chapters."
    assert sorted(shelf["name"] for shelf in entry["shelves"]) == ["Argentina", "Favourites"]
    assert sorted(entry["formats"]) == ["digital", "physical"]
    assert gone.status_code == 404
    assert [loan["person"] for loan in loans.json()] == ["Sofi"]


async def test_a_merge_is_refused_across_domains_users_and_open_loans(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        book = await _add(client, "Solaris", "Stanisław Lem")
        film = await _add(client, "Solaris", "Stanisław Lem", "movie")
        across = await client.post(
            "/api/duplicates/merge", json={"keep": book["id"], "drop": film["id"]}
        )
        itself = await client.post(
            "/api/duplicates/merge", json={"keep": book["id"], "drop": book["id"]}
        )
        other = await _add(client, "Solaris (Faber)", "Stanisław Lem")
        for entry_id, person in ((book["id"], "Ana"), (other["id"], "Juan")):
            await client.post(
                f"/api/entries/{entry_id}/loans", json={"person": person, "lent_on": "2026-01-01"}
            )
        both_out = await client.post(
            "/api/duplicates/merge", json={"keep": book["id"], "drop": other["id"]}
        )
        missing = await client.post(
            "/api/duplicates/merge", json={"keep": book["id"], "drop": 9999}
        )
    assert across.status_code == 422
    assert across.json()["error"]["code"] == "different_libraries"
    assert itself.status_code == 422
    assert both_out.status_code == 409
    assert both_out.json()["error"]["code"] == "both_lent"
    assert missing.status_code == 404


def test_migration_0029_arrives_and_leaves(tmp_path: Path) -> None:
    from alembic import command
    from book_tracker.migrations import alembic_config

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    configured = Settings(data_dir=data_dir, user_agent_contact="t@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url, revision="0028_location_and_loans")
    upgrade(configured.database_url, revision="head")
    connection = sqlite3.connect(data_dir / "books.db")
    assert "duplicate_dismissals" in {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master")
    }
    connection.close()
    command.downgrade(alembic_config(configured.database_url), "0028_location_and_loans")
    connection = sqlite3.connect(data_dir / "books.db")
    assert "duplicate_dismissals" not in {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master")
    }
    connection.close()
