"""The revisit deck's queue (Sprint 121, DEC-178): old scores, oldest first, resting a year
once looked at."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import text

from book_tracker.config import Settings
from book_tracker.main import create_app

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _add(client: httpx.AsyncClient, title: str, item_type: str, **entry: Any) -> int:
    created = await client.post(
        "/api/entries",
        json={
            "manual": {"item_type": item_type, "title": title},
            "idempotency_key": f"{item_type}:{title}",
            **entry,
        },
    )
    assert created.status_code == 201, created.text
    return int(created.json()["entry"]["id"])


async def test_old_scores_come_back_oldest_first_and_rest_once_looked_at(
    tmp_path: Path,
) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", user_agent_contact="t@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        stoner = await _add(
            client, "Stoner", "book", status="read", score=9, date_finished="2021-10-24"
        )
        dune = await _add(
            client, "Dune", "movie", status="watched", score=7, date_finished="2019-10-22"
        )
        await _add(client, "Recent", "book", status="read", score=8, date_finished="2026-01-01")
        await _add(client, "Unscored", "book", status="read", date_finished="2018-01-01")
        await _add(client, "Reading", "book", status="reading", score=6)
        first = await client.get("/api/revisit")
        # Kept today: it rests for a year.
        await client.patch(f"/api/entries/{stoner}", json={"score": 9, "score_reason": "time"})
        second = await client.get("/api/revisit")
        with app.state.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE score_events SET recorded_at = '2024-01-01T00:00:00Z' "
                    "WHERE entry_id = :id AND previous IS NOT NULL"
                ),
                {"id": stoner},
            )
        later = await client.get("/api/revisit")
    assert first.status_code == 200
    assert [card["entry"]["id"] for card in first.json()["cards"]] == [dune, stoner]
    assert first.json()["cards"][0]["scored_at"] == "2019-10-22"
    assert first.json()["total"] == 2
    assert [card["entry"]["id"] for card in second.json()["cards"]] == [dune]
    assert [card["entry"]["id"] for card in later.json()["cards"]] == [dune, stoner]
