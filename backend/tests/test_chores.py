"""The deck's chores (Sprint 112, DEC-176): the queues they read."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from book_tracker.config import Settings
from book_tracker.main import create_app

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_the_library_lists_what_has_no_cover(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", user_agent_contact="t@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        ids = []
        for title in ("Covered", "Bare", "Also bare"):
            created = await client.post(
                "/api/entries",
                json={"manual": {"item_type": "book", "title": title}, "idempotency_key": title},
            )
            ids.append(created.json()["entry"]["item_id"])
        from book_tracker.infrastructure.repositories import DomainRepository

        DomainRepository(app.state.engine, 1).set_cover_path(ids[0], f"covers/{ids[0]}.jpg")
        bare = await client.get("/api/entries", params={"cover": "missing", "limit": 1})
        nonsense = await client.get("/api/entries", params={"cover": "present"})
    assert bare.status_code == 200
    assert bare.json()["total"] == 2
    assert bare.json()["items"][0]["item"]["title"] in {"Bare", "Also bare"}
    assert nonsense.status_code == 422
