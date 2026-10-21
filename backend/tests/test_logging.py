from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from book_tracker.application.passwords import hash_password
from book_tracker.config import Settings
from book_tracker.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_each_acting_request_writes_one_minimal_audit_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app = create_app(
        Settings(data_dir=tmp_path / "data", user_agent_contact="test@example.invalid", auth="on")
    )
    async with app.router.lifespan_context(app):
        admin = hash_password("admin private password")
        target = hash_password("target private password")
        with app.state.engine.begin() as connection:
            connection.exec_driver_sql(
                "UPDATE users SET username='admin',display_name='Private Admin Name',"
                "password_hash=?,password_salt=? WHERE id=1",
                (admin.digest, admin.salt),
            )
            connection.exec_driver_sql(
                "INSERT INTO users (id,username,display_name,password_hash,password_salt,is_admin,"
                "created_at,updated_at) VALUES "
                "(2,'target','Private Target Name',?,?,0,'2026-09-10T00:00:00Z',"
                "'2026-09-10T00:00:00Z')",
                (target.digest, target.salt),
            )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            await client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "admin private password"},
            )
            await client.post("/api/auth/act-as/2")
            capsys.readouterr()
            response = await client.get(
                "/api/entries",
                params={"query": "private query words", "status": "unsorted"},
                headers={"cookie-probe": "private cookie words"},
            )
            assert response.status_code == 200

    lines = [
        json.loads(line) for line in capsys.readouterr().err.splitlines() if line.startswith("{")
    ]
    audit = [line for line in lines if line.get("event") == "admin_acting_request"]
    assert len(audit) == 1
    assert audit[0]["admin_user_id"] == 1
    assert audit[0]["acting_as_user_id"] == 2
    assert audit[0]["method"] == "GET"
    assert audit[0]["route"] == "/api/entries"
    rendered = json.dumps(audit[0])
    for private in (
        "Private Admin Name",
        "Private Target Name",
        "private query words",
        "private cookie words",
        "admin private password",
        "target private password",
    ):
        assert private not in rendered


def _json_lines(text: str) -> list[dict]:  # type: ignore[type-arg]
    return [json.loads(line) for line in text.splitlines() if line.startswith("{")]


async def _get(app, path: str, headers: dict[str, str] | None = None) -> httpx.Response:  # type: ignore[no-untyped-def]
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        return await client.get(path, headers=headers or {})


@pytest.mark.anyio
async def test_every_response_carries_a_request_id_that_its_log_line_shares(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Sprint 087 (production-grade proposal R7): a slow or failing request can be
    joined to the log lines it produced. The id goes out as `X-Request-Id`, and the
    one `request_finished` line per API request carries it with the route template,
    the status and the time taken — never the query string."""
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    capsys.readouterr()
    response = await _get(app, "/api/entries?query=private+query+words")
    assert response.status_code == 200
    request_id = response.headers["x-request-id"]
    assert len(request_id) == 32

    finished = [
        line
        for line in _json_lines(capsys.readouterr().err)
        if line.get("event") == "request_finished"
    ]
    assert len(finished) == 1
    line = finished[0]
    assert line["request_id"] == request_id
    assert line["method"] == "GET"
    assert line["route"] == "/api/entries"
    assert line["status"] == 200
    assert isinstance(line["duration_ms"], (int, float))
    assert "private query words" not in json.dumps(line)


@pytest.mark.anyio
async def test_a_well_formed_incoming_request_id_is_kept_and_anything_else_replaced(
    tmp_path: Path,
) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    kept = await _get(app, "/api/health/live", {"X-Request-Id": "proxy-abc.123_XYZ"})
    assert kept.headers["x-request-id"] == "proxy-abc.123_XYZ"
    for unusable in ("short", "has spaces in it", "x" * 65, 'quote"d-request-id'):
        replaced = await _get(app, "/api/health/live", {"X-Request-Id": unusable})
        assert replaced.headers["x-request-id"] != unusable
        assert len(replaced.headers["x-request-id"]) == 32


@pytest.mark.anyio
async def test_log_lines_written_while_a_job_runs_carry_the_job_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import logging
    from datetime import UTC, datetime

    from book_tracker.database import create_engine
    from book_tracker.infrastructure.jobs import JobRepository, JobRunner
    from book_tracker.logging import configure_logging
    from book_tracker.migrations import upgrade

    settings = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert settings.database_url is not None
    upgrade(settings.database_url)
    engine = create_engine(settings)
    configure_logging("INFO")

    class Talkative:
        async def process(self, job_id: str, now: datetime) -> dict[str, object]:
            logging.getLogger("book_tracker.test").info("handler_spoke")
            return {"state": "succeeded", "progress": {}}

    try:
        job_id = JobRepository(engine).enqueue(None, "talk", {})
        capsys.readouterr()
        assert await JobRunner(engine, {"talk": Talkative()}).tick(datetime.now(UTC))
    finally:
        engine.dispose()
    spoke = [
        line
        for line in _json_lines(capsys.readouterr().err)
        if line.get("event") == "handler_spoke"
    ]
    assert len(spoke) == 1
    assert spoke[0]["job_id"] == job_id
    assert spoke[0]["job_kind"] == "talk"
