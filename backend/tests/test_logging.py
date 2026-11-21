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


# Sprint 128, F19: a configured secret reached the log through the one path the
# scrubber did not walk — an exception. `exc_info` arrived as a tuple, the
# traceback was rendered after redaction (or not at all: `<traceback object>`),
# and the exception's own text went out raw.
SECRET = "configured-secret-value-0123456789"


def _fail_with_secret() -> None:
    raise RuntimeError(f"provider refused https://example.invalid/?key={SECRET}")


def test_a_stdlib_exception_traceback_is_rendered_and_scrubbed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    import logging

    from book_tracker.logging import REDACTION, configure_logging

    configure_logging("INFO", scrub=(SECRET,))
    try:
        _fail_with_secret()
    except RuntimeError:
        logging.getLogger("book_tracker.test").exception("provider_failed")
    line = _json_lines(capsys.readouterr().err)[-1]

    assert line["event"] == "provider_failed"
    assert SECRET not in json.dumps(line)
    exception = line["exception"]
    assert exception.startswith("Traceback (most recent call last):")
    assert "_fail_with_secret" in exception
    # The line that says what went wrong is the last one; it must survive any cap.
    assert f"RuntimeError: provider refused https://example.invalid/?key={REDACTION}" in exception
    assert "<traceback object" not in json.dumps(line)


def test_a_structlog_exception_traceback_is_rendered_and_scrubbed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    import structlog

    from book_tracker.logging import configure_logging

    configure_logging("INFO", scrub=(SECRET,))
    try:
        _fail_with_secret()
    except RuntimeError:
        structlog.get_logger("book_tracker.test").exception("provider_failed")
    line = _json_lines(capsys.readouterr().err)[-1]

    assert line["event"] == "provider_failed"
    assert "Traceback (most recent call last):" in line["exception"]
    assert SECRET not in json.dumps(line)


def test_an_exception_passed_as_a_field_is_scrubbed(capsys: pytest.CaptureFixture[str]) -> None:
    import logging

    from book_tracker.logging import configure_logging

    configure_logging("INFO", scrub=(SECRET,))
    try:
        _fail_with_secret()
    except RuntimeError as error:
        logging.getLogger("book_tracker.test").warning(
            "provider_failed", extra={"error": error, "errors": [error]}
        )
    line = _json_lines(capsys.readouterr().err)[-1]

    assert "RuntimeError" in line["error"]
    assert SECRET not in json.dumps(line)


def test_uvicorn_loggers_go_through_the_same_redacting_handler(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The container runs `uvicorn` without `--log-config`, so uvicorn installs its
    own handlers (with propagation off) before the application starts. Its error
    logger is the one that reports an unhandled exception in a request, so it
    must reach the JSON handler and the scrubber, not a plain formatter."""
    import logging
    import logging.config

    from uvicorn.config import LOGGING_CONFIG

    from book_tracker.logging import configure_logging

    logging.config.dictConfig(LOGGING_CONFIG)
    configure_logging("INFO", scrub=(SECRET,))
    try:
        _fail_with_secret()
    except RuntimeError:
        logging.getLogger("uvicorn.error").exception("Exception in ASGI application")
    logging.getLogger("uvicorn.access").info(
        '%s - "%s %s HTTP/%s" %d', "127.0.0.1:1", "GET", f"/api/x?k={SECRET}", "1.1", 200
    )
    logging.getLogger("uvicorn").info("Started server process [%d]", 1)
    err = capsys.readouterr().err

    assert SECRET not in err
    events = [line["event"] for line in _json_lines(err)]
    assert "Exception in ASGI application" in events
    assert "Started server process [1]" in events
    assert any(event.startswith("127.0.0.1:1 - ") for event in events)
    # Nothing was printed past the JSON handler in uvicorn's own format.
    assert all(line.startswith("{") for line in err.splitlines() if line.strip())


@pytest.mark.anyio
async def test_every_configured_secret_is_scrubbed_once_the_app_starts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import logging

    secrets = {
        "google": "google-books-key-value-0123456789",
        "tmdb": "tmdb-read-token-value-0123456789",
        "admin": "admin-bootstrap-password-0123456789",
    }
    app = create_app(
        Settings(
            data_dir=tmp_path,
            user_agent_contact="test@example.invalid",
            GOOGLE_BOOKS_API_KEY=secrets["google"],
            TMDB_READ_TOKEN=secrets["tmdb"],
            auth="on",
            admin_username="admin",
            admin_password=secrets["admin"],
        )
    )
    async with app.router.lifespan_context(app):
        capsys.readouterr()
        logging.getLogger("book_tracker.test").warning(
            "leak_probe", extra={"detail": " ".join(secrets.values())}
        )
    line = next(
        line for line in _json_lines(capsys.readouterr().err) if line.get("event") == "leak_probe"
    )
    for value in secrets.values():
        assert value not in line["detail"]
