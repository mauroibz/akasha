"""Finishing (Sprint 123, DEC-179): starting something dates its start when nothing has."""

from __future__ import annotations

from datetime import date
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


async def test_starting_fills_an_empty_start_date_and_keeps_one(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", user_agent_contact="t@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        fresh = await _add(client, "Rayuela", "book", status="to_read")
        dated = await _add(client, "Ficciones", "book", status="to_read", date_started="2025-01-02")
        series = await _add(client, "Severance", "series", status="plan_to_watch")
        film = await _add(client, "Dune", "movie", status="watchlist")
        started = (await client.patch(f"/api/entries/{fresh}", json={"status": "reading"})).json()
        kept = (await client.patch(f"/api/entries/{dated}", json={"status": "reading"})).json()
        watching = (
            await client.patch(f"/api/entries/{series}", json={"status": "watching"})
        ).json()
        # Not under way: a finish does not date a start.
        finished = (await client.patch(f"/api/entries/{film}", json={"status": "watched"})).json()
        # A note written while reading does not move the date either.
        again = (await client.patch(f"/api/entries/{fresh}", json={"notes": "Hopscotch"})).json()
    today = date.today().isoformat()
    assert started["date_started"] == today
    assert kept["date_started"] == "2025-01-02"
    assert watching["date_started"] == today
    assert finished.get("date_started") is None
    assert again["date_started"] == today
