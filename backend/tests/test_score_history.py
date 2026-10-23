"""The score history (Sprint 114, DEC-176).

Every change of an entry's score is kept with its date and why it changed: a reread, or
just time. The rows are written by triggers on `entries`, so no write path (a card, the
opinion dialog, bulk, import, undo, merge) can change a score without leaving one.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import httpx
import pytest

from book_tracker.config import Settings
from book_tracker.domain.registry import DOMAINS
from book_tracker.main import create_app
from book_tracker.migrations import upgrade

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _app(tmp_path: Path):  # type: ignore[no-untyped-def]
    return create_app(Settings(data_dir=tmp_path / "data", user_agent_contact="t@example.invalid"))


async def _add(client: httpx.AsyncClient, title: str, **entry: Any) -> dict[str, Any]:
    created = await client.post(
        "/api/entries",
        json={
            "manual": {"item_type": "book", "title": title, "metadata": {"creators": ["A"]}},
            "idempotency_key": title,
            **entry,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["entry"]


def _shape(events: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    return [(e["score"], e["previous"], e["reason"], e["note"]) for e in events]


async def test_each_change_is_kept_with_why(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        entry = await _add(client, "Solaris", score=7)
        url = f"/api/entries/{entry['id']}"
        await client.patch(url, json={"notes": "no score here"})
        await client.patch(url, json={"score": 8})
        await client.patch(url, json={"score": 9, "score_reason": "reread", "score_note": "Better"})
        await client.patch(url, json={"score": 9, "score_reason": "reread"})
        await client.patch(url, json={"score": None})
        history = await client.get(f"{url}/score-history")
    assert history.status_code == 200
    assert _shape(history.json()) == [
        (7, None, None, None),  # the first score has no "why"
        (8, 7, "time", None),  # changed with no reread: time
        (9, 8, "reread", "Better"),
        (9, 9, "reread", None),  # "Still a 9": a confirmation is history too
        (None, 9, "time", None),  # cleared
    ]
    dates = [event["recorded_at"] for event in history.json()]
    assert dates == sorted(dates)


async def test_a_reason_qualifies_a_score_and_only_these_two_exist(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        entry = await _add(client, "Stoner")
        url = f"/api/entries/{entry['id']}"
        alone = await client.patch(url, json={"score_reason": "time"})
        unknown = await client.patch(url, json={"score": 5, "score_reason": "mood"})
        long_note = await client.patch(
            url, json={"score": 5, "score_reason": "time", "score_note": "x" * 281}
        )
    assert alone.status_code == 422
    assert unknown.status_code == 422
    assert long_note.status_code == 422


async def test_bulk_and_merge_leave_history_too(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        keep = await _add(client, "Rayuela", score=8)
        drop = await _add(client, "Rayuela (Alfaguara)", score=6, confirm_near_match=True)
        bulk = await client.patch(
            "/api/entries/bulk", json={"entry_ids": [keep["id"]], "set": {"score": 9}}
        )
        assert bulk.status_code == 200, bulk.text
        merged = await client.post(
            "/api/duplicates/merge", json={"keep": keep["id"], "drop": drop["id"]}
        )
        assert merged.status_code == 200
        history = await client.get(f"/api/entries/{keep['id']}/score-history")
    # The other copy's history moves with the merge: the owner scored this work then.
    assert sorted(_shape(history.json()), key=str) == sorted(
        [(8, None, None, None), (9, 8, "time", None), (6, None, None, None)], key=str
    )


async def test_the_json_export_carries_the_history(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        entry = await _add(client, "Solaris", score=7)
        await client.patch(
            f"/api/entries/{entry['id']}", json={"score": 9, "score_reason": "reread"}
        )
        exported = await client.get("/api/export", params={"format": "json"})
    (row,) = exported.json()["entries"]
    assert [(e["score"], e["reason"]) for e in row["score_history"]] == [
        (7, None),
        (9, "reread"),
    ]


async def test_finished_is_declared_and_published(tmp_path: Path) -> None:
    finished = {
        domain.item_type: [status.value for status in domain.statuses if status.finished]
        for domain in DOMAINS.values()
    }
    assert finished == {
        "book": ["read"],
        "album": [],
        "anime": ["completed"],
        "movie": ["watched"],
        "series": ["completed"],
    }
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        types = (await client.get("/api/item-types")).json()
    book = next(row for row in types if row["id"] == "book")
    assert [s["value"] for s in book["statuses"] if s["finished"]] == ["read"]


def test_migration_0030_backfills_and_leaves(tmp_path: Path) -> None:
    from alembic import command
    from book_tracker.migrations import alembic_config

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    configured = Settings(data_dir=data_dir, user_agent_contact="t@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url, revision="0029_duplicate_dismissals")
    database = data_dir / "books.db"
    connection = sqlite3.connect(database)
    now = "2026-01-01T00:00:00Z"
    connection.execute(
        "INSERT INTO items (id, type, title, identifiers, metadata, created_at, updated_at) "
        "VALUES (1, 'book', 'A', '{}', '{}', ?, ?), (2, 'book', 'B', '{}', '{}', ?, ?), "
        "(3, 'book', 'C', '{}', '{}', ?, ?)",
        (now,) * 6,
    )
    connection.execute(
        "INSERT INTO entries (user_id, item_id, status, score, date_added, date_finished, "
        "reread_count, score_provisional, created_at, updated_at) VALUES "
        "(1, 1, 'read', 8, '2020-01-01', '2021-06-01', 0, 0, ?, ?), "
        "(1, 2, 'read', 6, '2022-03-01', NULL, 0, 0, ?, ?), "
        "(1, 3, 'to_read', NULL, '2023-01-01', NULL, 0, 0, ?, ?)",
        (now,) * 6,
    )
    connection.commit()
    connection.close()

    upgrade(configured.database_url, revision="head")
    connection = sqlite3.connect(database)
    rows = connection.execute(
        "SELECT entry_id, score, previous, reason, recorded_at FROM score_events ORDER BY entry_id"
    ).fetchall()
    assert rows == [(1, 8, None, None, "2021-06-01"), (2, 6, None, None, "2022-03-01")]
    # The triggers are live after the upgrade, outside the application too.
    connection.execute("UPDATE entries SET score = 9 WHERE id = 1")
    connection.commit()
    assert connection.execute(
        "SELECT score, previous, reason FROM score_events WHERE entry_id = 1 ORDER BY id DESC"
    ).fetchone() == (9, 8, "time")
    connection.close()

    command.downgrade(alembic_config(configured.database_url), "0029_duplicate_dismissals")
    connection = sqlite3.connect(database)
    names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    assert "score_events" not in names
    assert not any(name.startswith("score_events_") for name in names)
    connection.close()
