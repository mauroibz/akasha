"""The year in review (Sprint 120, DEC-178): one year read back across every library."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from book_tracker.config import Settings
from book_tracker.main import create_app

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _add(
    client: httpx.AsyncClient, title: str, item_type: str, creator: str, **entry: Any
) -> int:
    created = await client.post(
        "/api/entries",
        json={
            "manual": {"item_type": item_type, "title": title, "metadata": {"creators": [creator]}},
            "idempotency_key": f"{item_type}:{title}",
            **entry,
        },
    )
    assert created.status_code == 201, created.text
    return int(created.json()["entry"]["id"])


async def test_a_year_is_read_back_across_libraries(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", user_agent_contact="t@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        await _add(
            client,
            "Monster",
            "anime",
            "Naoki Urasawa",
            status="completed",
            score=10,
            date_finished="2025-10-04",
        )
        await _add(
            client,
            "The Dispossessed",
            "book",
            "Ursula K. Le Guin",
            status="read",
            score=9,
            date_finished="2025-03-02",
            notes="Anarres stays with me.",
        )
        await _add(
            client,
            "The Lathe of Heaven",
            "book",
            "Ursula K. Le Guin",
            status="read",
            score=8,
            date_finished="2025-03-20",
        )
        await _add(
            client,
            "Dune",
            "movie",
            "Denis Villeneuve",
            status="watched",
            score=7,
            date_finished="2025-11-30",
        )
        # Finished in another year: not in 2025's review.
        await _add(
            client,
            "Stoner",
            "book",
            "John Williams",
            status="read",
            score=9,
            date_finished="2024-06-01",
        )
        review = await client.get("/api/diary/2025/review")
        empty = await client.get("/api/diary/2003/review")
    assert review.status_code == 200, review.text
    body = review.json()
    assert body["year"] == 2025
    assert body["finished"] == 4
    assert body["counts"] == {"anime": 1, "book": 2, "movie": 1}
    assert [row["entry"]["item"]["title"] for row in body["best"]][:2] == [
        "Monster",
        "The Dispossessed",
    ]
    assert body["best"][0]["score"] == 10
    assert body["scores"] == [0, 0, 0, 0, 0, 0, 1, 1, 1, 1]
    assert body["months"][2] == 2 and body["months"][9] == 1 and body["months"][10] == 1
    assert body["leader"] == {"name": "Ursula K. Le Guin", "count": 2}
    assert body["quote"]["text"] == "Anarres stays with me."
    assert body["quote"]["title"] == "The Dispossessed"
    assert body["changes"] == []
    assert empty.json()["finished"] == 0
    assert empty.json()["quote"] is None
