"""Sprint 109: a provisional score can be written back, so an undo restores it (DEC-176)."""

from pathlib import Path

import httpx
import pytest

from book_tracker.config import Settings
from book_tracker.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _app(tmp_path: Path):  # type: ignore[no-untyped-def]
    return create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))


@pytest.mark.anyio
async def test_a_score_can_be_written_back_as_provisional(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        created = await client.post(
            "/api/entries",
            json={"manual": {"item_type": "book", "title": "Undo"}, "idempotency_key": "u"},
        )
        entry_id = created.json()["entry"]["id"]
        restored = await client.patch(
            f"/api/entries/{entry_id}", json={"score": 7, "score_provisional": True}
        )
        confirmed = await client.patch(f"/api/entries/{entry_id}", json={"score": 8})
        explicit_false = await client.patch(
            f"/api/entries/{entry_id}", json={"score": 6, "score_provisional": False}
        )
        without_score = await client.patch(
            f"/api/entries/{entry_id}", json={"score_provisional": True}
        )
    assert restored.status_code == 200
    assert restored.json()["score"] == 7
    assert restored.json()["score_provisional"] is True
    assert confirmed.json()["score_provisional"] is False
    assert explicit_false.json()["score_provisional"] is False
    # A flag with no score to qualify is meaningless, and refused rather than ignored.
    assert without_score.status_code == 422
