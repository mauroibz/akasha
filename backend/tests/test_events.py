"""Background work you can see (Sprint 089, proposal I6 and §6.1).

`GET /api/events` streams the current person's jobs as Server-Sent Events, so a page
learns about progress without polling, and the shell can show that something is
running. A connection lives for `event_stream_seconds` and then ends; the browser's
EventSource reconnects by itself, which bounds every connection without a timer
anywhere else.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from book_tracker.config import Settings
from book_tracker.infrastructure.jobs import JobRepository
from book_tracker.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _add_user(engine, user_id: int) -> None:  # type: ignore[no-untyped-def]
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id,username,is_admin,created_at,updated_at) "
                "VALUES (:id,:name,0,'n','n')"
            ),
            {"id": user_id, "name": f"user{user_id}"},
        )


def _events(body: str) -> list[dict]:  # type: ignore[type-arg]
    events = []
    for block in body.split("\n\n"):
        lines = block.splitlines()
        if "event: job" in lines:
            data = next(line for line in lines if line.startswith("data: "))
            events.append(json.loads(data[len("data: ") :]))
    return events


def test_a_person_sees_their_own_jobs_and_not_anyone_elses(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    from book_tracker.database import create_engine
    from book_tracker.migrations import upgrade

    settings = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert settings.database_url is not None
    upgrade(settings.database_url)
    engine = create_engine(settings)
    try:
        _add_user(engine, 2)
        jobs = JobRepository(engine)
        mine = jobs.enqueue(None, "enrich_item", {}, user_id=1)
        theirs = jobs.enqueue(None, "enrich_item", {}, user_id=2)
        changed = jobs.changes_for_user(1, since=None)
        ids = {job["id"] for job in changed}
        assert mine in ids and theirs not in ids
        later = jobs.changes_for_user(1, since=datetime.now(UTC).isoformat())
        assert later == []
    finally:
        engine.dispose()
    del app


@pytest.mark.anyio
async def test_the_stream_carries_each_change_to_a_job(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        app.state.event_stream_seconds = 2.5
        # A kind nothing handles: the runner fails it at once, which is a finish.
        job_id = JobRepository(app.state.engine).enqueue(
            None, "nothing_handles_this", {}, user_id=1
        )
        response = await client.get("/api/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    states = [event["state"] for event in _events(response.text) if event["id"] == job_id]
    assert states, response.text
    # Claimed, then failed and requeued with a backoff (a missing handler is retried
    # like any failure): each change arrives as its own event, in order.
    assert "running" in states
    final = [event for event in _events(response.text) if event["id"] == job_id][-1]
    assert final["state"] == "queued"
    assert final["attempts"] == 1
    assert final["error_code"] == "no_handler"
    assert final["kind"] == "nothing_handles_this"


@pytest.mark.anyio
async def test_a_failed_job_can_be_retried_by_its_owner_only(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        app.state.job_runner.stop()  # keep the queue still while this test reads it
        _add_user(app.state.engine, 2)
        jobs = JobRepository(app.state.engine)
        mine = jobs.enqueue(None, "enrich_item", {}, user_id=1)
        theirs = jobs.enqueue(None, "enrich_item", {}, user_id=2)
        now = datetime.now(UTC)
        for job_id in (mine, theirs):
            for _ in range(3):
                jobs.fail(job_id, "provider down", now)
        assert (jobs.get_job(mine) or {})["state"] == "failed"

        retried = await client.post(f"/api/import/jobs/{mine}/retry")
        refused = await client.post(f"/api/import/jobs/{theirs}/retry")
    assert retried.status_code == 200
    assert retried.json()["state"] == "queued"
    assert retried.json()["attempts"] == 0
    assert refused.status_code == 404
