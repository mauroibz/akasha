"""Fill in the gaps (Sprint 125, DEC-179): finished entries missing a finish date or a
format, unless the owner said they do not remember it; from stored data only."""

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


async def test_the_gaps_are_finished_entries_missing_what_can_be_asked(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", user_agent_contact="t@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        undated = await _add(client, "Rayuela", "book", status="read", formats=["physical"])
        formatless = await _add(
            client, "Ficciones", "book", status="read", date_finished="2020-01-02"
        )
        await _add(
            client, "Stoner", "book", status="read", date_finished="2020-01-02", formats=["digital"]
        )
        await _add(client, "Dune", "book", status="to_read")
        forgotten = await _add(client, "Solaris", "book", status="read", formats=["physical"])
        await client.patch(f"/api/entries/{forgotten}", json={"unknown_fields": ["date_finished"]})
        # An album has no finish date and no finished status: never a gap.
        await _add(client, "Kid A", "album", status="owned")
        film = await _add(client, "Alien", "movie", status="watched")
        found = (await client.get("/api/gaps")).json()
    ids = [entry["id"] for entry in found["entries"]]
    assert found["total"] == 3
    assert set(ids) == {undated, formatless, film}
