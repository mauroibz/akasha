"""The Diary as a timeline (Sprint 118, DEC-176): every year, every library, in order,
with what was finished and how scores changed."""

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
            "manual": {"item_type": item_type, "title": title},
            "idempotency_key": f"{item_type}:{title}",
            **entry,
        },
    )
    assert created.status_code == 201, created.text
    return int(created.json()["entry"]["id"])


def _shape(events: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    return [
        (e["kind"], e["entry"]["item"]["title"], e["score"], e["previous"], e["reason"])
        for e in events
    ]


async def test_finishes_and_score_changes_interleave_across_libraries(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", user_agent_contact="t@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        dune = await _add(
            client, "Dune", "book", status="read", score=7, date_finished="2019-03-02"
        )
        await _add(client, "Dune", "movie", status="watched", score=8, date_finished="2021-10-22")
        await _add(client, "Stoner", "book", status="to_read")
        # A later reread changes the book's score, with why.
        await client.patch(
            f"/api/entries/{dune}",
            json={"score": 9, "score_reason": "reread", "score_note": "Better now"},
        )
        everything = await client.get("/api/diary/timeline")
    assert everything.status_code == 200
    body = everything.json()
    assert _shape(body["events"]) == [
        ("score", "Dune", 9, 7, "reread"),
        ("finished", "Dune", 8, None, None),
        # Finished in 2019 at 7: the score it had then, not the 9 it has now.
        ("finished", "Dune", 7, None, None),
    ]
    assert body["events"][0]["note"] == "Better now"
    assert body["events"][1]["entry"]["item"]["type"] == "movie"
    assert body["events"][2]["at"] == "2019-03-02"
    assert body["next_cursor"] is None


async def test_the_timeline_pages_without_skipping_or_repeating(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", user_agent_contact="t@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        for index in range(7):
            # Two on one day, so the order inside a day is exercised too.
            await _add(
                client,
                f"Book {index}",
                "book",
                status="read",
                date_finished=f"2020-01-{1 + index // 2:02d}",
            )
        seen: list[str] = []
        cursor = None
        while True:
            params: dict[str, Any] = {"limit": 3}
            if cursor:
                params["before"] = cursor
            page = await client.get("/api/diary/timeline", params=params)
            assert page.status_code == 200, page.text
            seen += [event["entry"]["item"]["title"] for event in page.json()["events"]]
            cursor = page.json()["next_cursor"]
            if not cursor:
                break
        bad = await client.get("/api/diary/timeline", params={"before": "not a cursor"})
    assert len(seen) == 7 and len(set(seen)) == 7
    assert bad.status_code == 400


async def test_a_finish_shows_the_score_it_had_then(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "data", user_agent_contact="t@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        solaris = await _add(
            client, "Solaris", "book", status="read", score=7, date_finished="2019-05-01"
        )
        await client.patch(f"/api/entries/{solaris}", json={"score": 9, "score_reason": "reread"})
        undated = await _add(client, "Stoner", "book", status="read", score=8)
        await client.patch(f"/api/entries/{undated}", json={"date_finished": "2020-01-01"})
        events = (await client.get("/api/diary/timeline")).json()["events"]
    finished = {e["entry"]["item"]["title"]: e["score"] for e in events if e["kind"] == "finished"}
    # Solaris was a 7 when it was finished in 2019; the 9 came with the reread.
    assert finished["Solaris"] == 7
    # No history before the finish: the score it has is the best answer there is.
    assert finished["Stoner"] == 8
