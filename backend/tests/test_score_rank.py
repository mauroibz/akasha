"""A rank inside a score (Sprint 116, DEC-176).

Entries that share a score can be put in order by choosing between two of them. The
order never changes a score; changing a score sets its rank aside. The library's score
sort reads score, then rank, then the newest, and its keyset cursor holds across pages.
"""

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
    client: httpx.AsyncClient, title: str, score: int | None, item_type: str = "book"
) -> dict[str, Any]:
    created = await client.post(
        "/api/entries",
        json={
            "manual": {"item_type": item_type, "title": title},
            "idempotency_key": f"{item_type}:{title}",
            "score": score,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["entry"]


def _titles(page: httpx.Response) -> list[str]:
    return [row["item"]["title"] for row in page.json()["items"]]


async def test_an_order_inside_a_score_sorts_the_library_and_never_changes_a_score(
    tmp_path: Path,
) -> None:
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        nine = await _add(client, "Nine", 9)
        a = await _add(client, "Eight A", 8)
        b = await _add(client, "Eight B", 8)
        c = await _add(client, "Eight C", 8)
        await _add(client, "Unscored", None)
        ranked = await client.put("/api/entries/rank", json={"entry_ids": [b["id"], c["id"]]})
        listed = await client.get(
            "/api/entries", params={"type": "book", "sort": "score", "order": "desc"}
        )
        eights = await client.get(
            "/api/entries",
            params={"type": "book", "score": 8, "sort": "score", "order": "desc"},
        )
        entry_b = await client.get(f"/api/entries/{b['id']}")
    assert ranked.status_code == 200, ranked.text
    assert [row["score_rank"] for row in ranked.json()] == [1, 2]
    # Ranked first, in their order, then the unranked eight; the unscored last.
    assert _titles(listed) == ["Nine", "Eight B", "Eight C", "Eight A", "Unscored"]
    assert _titles(eights) == ["Eight B", "Eight C", "Eight A"]
    assert entry_b.json()["score"] == 8
    assert entry_b.json()["score_rank"] == 1
    assert nine["score"] == 9 and a["score"] == 8


async def test_a_new_score_sets_the_old_rank_aside(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        a = await _add(client, "A", 8)
        b = await _add(client, "B", 8)
        await client.put("/api/entries/rank", json={"entry_ids": [a["id"], b["id"]]})
        moved = await client.patch(f"/api/entries/{a['id']}", json={"score": 7})
        same = await client.patch(f"/api/entries/{b['id']}", json={"notes": "still eight"})
    assert moved.json()["score_rank"] is None
    assert same.json()["score_rank"] == 2


async def test_an_order_is_refused_across_scores_libraries_and_people(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        a = await _add(client, "A", 8)
        b = await _add(client, "B", 7)
        film = await _add(client, "C", 8, "movie")
        unscored = await _add(client, "D", None)
        mixed = await client.put("/api/entries/rank", json={"entry_ids": [a["id"], b["id"]]})
        domains = await client.put("/api/entries/rank", json={"entry_ids": [a["id"], film["id"]]})
        nothing = await client.put("/api/entries/rank", json={"entry_ids": [unscored["id"]]})
        missing = await client.put("/api/entries/rank", json={"entry_ids": [a["id"], 999]})
        twice = await client.put("/api/entries/rank", json={"entry_ids": [a["id"], a["id"]]})
    assert mixed.status_code == 422
    assert mixed.json()["error"]["code"] == "invalid_rank"
    assert domains.status_code == 422
    assert nothing.status_code == 422
    assert missing.status_code == 404
    assert twice.status_code == 422


async def test_the_score_sort_pages_without_skipping_or_repeating(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        eights = [await _add(client, f"Eight {index}", 8) for index in range(5)]
        for index in range(3):
            await _add(client, f"Seven {index}", 7)
        await client.put(
            "/api/entries/rank",
            json={"entry_ids": [eights[3]["id"], eights[0]["id"], eights[4]["id"]]},
        )
        seen: list[str] = []
        after = None
        while True:
            params: dict[str, Any] = {"type": "book", "sort": "score", "limit": 2}
            if after:
                params["after"] = after
            page = await client.get("/api/entries", params=params)
            seen += _titles(page)
            after = page.json()["next_cursor"]
            if not after:
                break
    assert seen[:3] == ["Eight 3", "Eight 0", "Eight 4"]
    assert len(seen) == 8 and len(set(seen)) == 8
    assert all(title.startswith("Seven") for title in seen[5:])


async def test_the_json_export_carries_the_rank(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        a = await _add(client, "A", 8)
        await client.put("/api/entries/rank", json={"entry_ids": [a["id"]]})
        exported = await client.get("/api/export", params={"format": "json"})
    assert exported.json()["entries"][0]["score_rank"] == 1


def test_migration_0031_arrives_and_leaves(tmp_path: Path) -> None:
    from alembic import command
    from book_tracker.migrations import alembic_config

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    configured = Settings(data_dir=data_dir, user_agent_contact="t@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url, revision="0030_score_events")
    upgrade(configured.database_url, revision="head")
    connection = sqlite3.connect(data_dir / "books.db")
    assert "score_rank" in {row[1] for row in connection.execute("PRAGMA table_info(entries)")}
    connection.close()
    command.downgrade(alembic_config(configured.database_url), "0030_score_events")
    connection = sqlite3.connect(data_dir / "books.db")
    assert "score_rank" not in {row[1] for row in connection.execute("PRAGMA table_info(entries)")}
    connection.close()
