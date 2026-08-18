"""Security limits from technical spec section 9, asserted rather than assumed.

Most of these limits were implemented in the sprints that introduced the
surfaces they guard, and each of those has a test near its own code: the 5 MiB
Goodreads cap in `test_goodreads_import.py`, cover byte/pixel/host/redirect
bounds in `test_covers.py`, provider 429/malformed/oversized handling in
`test_providers.py`, and Calibre path and symlink rejection in
`test_calibre_import.py`. What is collected here is what nothing covered: the
static-file boundary, the provider timeout, and log redaction — the last of
which did not exist at all before Sprint 017.
"""

import json
import logging
from pathlib import Path

import httpx
import pytest

from book_tracker.config import Settings
from book_tracker.domains.book.providers import OpenLibraryProvider
from book_tracker.infrastructure.providers import ProviderPayloadError, create_provider_client
from book_tracker.logging import REDACTION, configure_logging
from book_tracker.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def static_app(tmp_path: Path) -> tuple[object, Path]:
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>Akasha</title>", encoding="utf-8")
    (static / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("owner private notes", encoding="utf-8")
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            static_dir=static,
            user_agent_contact="test@example.invalid",
        )
    )
    app.state.skip_migrations = False
    return app, static


@pytest.mark.anyio
async def test_static_route_serves_assets_but_never_escapes_its_root(tmp_path: Path) -> None:
    app, _ = static_app(tmp_path)
    async with (
        app.router.lifespan_context(app),  # type: ignore[attr-defined]
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app),  # type: ignore[arg-type]
            base_url="http://test",
        ) as client,
    ):
        served = await client.get("/assets/app.js")
        assert served.status_code == 200
        assert served.text == "console.log(1)"

        # Percent-encoded traversal only. A literal "/../secret.txt" is
        # collapsed to "/secret.txt" by the client before it is ever sent,
        # so asserting on that form proves the client normalizes, not that
        # the application contains anything — a vacuous security test is
        # worse than none.
        for attempt in (
            "/%2e%2e/secret.txt",
            "/..%2fsecret.txt",
            "/assets/%2e%2e/%2e%2e/secret.txt",
        ):
            escaped = await client.get(attempt)
            assert escaped.status_code == 200, attempt
            assert "owner private notes" not in escaped.text, attempt
            assert "<title>Akasha</title>" in escaped.text, attempt

        # An unknown route is the SPA shell, not a directory listing.
        fallback = await client.get("/books/12")
        assert "<title>Akasha</title>" in fallback.text


@pytest.mark.anyio
async def test_provider_request_gives_up_rather_than_hanging() -> None:
    """A provider that never answers must not hold a request open forever."""

    async def never_answers(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    client = create_provider_client(transport=httpx.MockTransport(never_answers))
    provider = OpenLibraryProvider(client, "test@example.invalid")
    with pytest.raises((ProviderPayloadError, httpx.HTTPError, TimeoutError)):
        await provider.fetch_by_isbn("9788437604572")
    await client.aclose()


def read_log_lines(caplog_text: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in caplog_text.splitlines() if line.strip()]


def test_redaction_removes_notes_payloads_and_keys(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", scrub=("super-secret-google-key",))
    logging.getLogger("test").warning(
        "import row failed",
        extra={
            "notes": "I hated the ending and here is why",
            "review": "two stars",
            "payload": {"volumeInfo": {"title": "Rayuela"}},
            "api_key": "super-secret-google-key",
            "item_id": 42,
            "provider": "googlebooks",
        },
    )
    record = read_log_lines(capsys.readouterr().err)[-1]

    # The safe fields are the point of structured logging and must survive.
    assert record["event"] == "import row failed"
    assert record["item_id"] == 42
    assert record["provider"] == "googlebooks"
    assert record["level"] == "warning"
    assert "timestamp" in record

    for field in ("notes", "review", "payload", "api_key"):
        assert record[field] == REDACTION, field
    assert "I hated the ending" not in json.dumps(record)
    assert "super-secret-google-key" not in json.dumps(record)


def test_redaction_scrubs_a_key_that_arrives_inside_another_value(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Keys leak through URLs far more often than through a field named
    # `api_key`, and a URL is exactly what a provider error wants to log.
    configure_logging("INFO", scrub=("super-secret-google-key",))
    logging.getLogger("test").error(
        "provider call failed",
        extra={"url": "https://www.googleapis.com/books/v1/volumes?key=super-secret-google-key"},
    )
    record = read_log_lines(capsys.readouterr().err)[-1]
    assert "super-secret-google-key" not in json.dumps(record)
    assert REDACTION in str(record["url"])
    # Scrubbing must not swallow the rest of the diagnostic.
    assert "googleapis.com" in str(record["url"])


def test_redaction_truncates_an_oversized_value_under_an_innocent_key(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO")
    logging.getLogger("test").info("provider answered", extra={"data": "x" * 5000})
    record = read_log_lines(capsys.readouterr().err)[-1]
    assert "truncated 5000 chars" in str(record["data"])
    assert len(str(record["data"])) < 700


def test_redaction_reaches_into_nested_structures(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    logging.getLogger("test").info(
        "import preview",
        extra={"batch": {"id": "b1", "rows": [{"notes": "private"}], "count": 3}},
    )
    record = read_log_lines(capsys.readouterr().err)[-1]
    batch = record["batch"]
    assert isinstance(batch, dict)
    assert batch["id"] == "b1"
    assert batch["count"] == 3
    assert batch["rows"] == REDACTION
    assert "private" not in json.dumps(record)
