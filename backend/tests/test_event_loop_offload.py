"""Sprint 059, Phase B: the offload seam does not stall other requests, and does
not let two real writer threads corrupt the ledger or fail with a raw driver error.

Phase A (`docs/decisions.md`, the Sprint 059 verdict) measured a large import commit
blocking the event loop for the whole call. `off_loop` (infrastructure/offload.py) is
the seam that moves it to a worker thread; these tests are the three things that
had to be proved rather than assumed before trusting a second real OS thread with
the same SQLite file: the per-connection pragmas still apply off-thread, concurrent
writers still leave a correct ledger, and a busy_timeout that still expires surfaces
as a typed error rather than an unhandled `database is locked`.
"""

import threading
import time
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.infrastructure.offload import off_loop
from book_tracker.main import create_app
from book_tracker.migrations import upgrade


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _pragmas(engine) -> dict[str, object]:  # type: ignore[no-untyped-def]
    with engine.connect() as connection:
        return {
            "foreign_keys": connection.execute(text("PRAGMA foreign_keys")).scalar(),
            "journal_mode": connection.execute(text("PRAGMA journal_mode")).scalar(),
            "busy_timeout": connection.execute(text("PRAGMA busy_timeout")).scalar(),
        }


@pytest.mark.anyio
async def test_pragmas_apply_to_a_connection_obtained_off_the_main_thread(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, sqlite_busy_timeout_ms=1234)
    assert settings.database_url is not None
    upgrade(settings.database_url)
    engine = create_engine(settings)
    try:
        on_loop = _pragmas(engine)
        off_thread = await off_loop(_pragmas, engine)
        assert on_loop == off_thread
        assert off_thread["foreign_keys"] == 1
        assert str(off_thread["journal_mode"]).lower() == "wal"
        assert off_thread["busy_timeout"] == 1234
    finally:
        engine.dispose()


@pytest.mark.anyio
async def test_a_slow_import_commit_does_not_block_a_concurrent_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The load-bearing regression for Phase A's finding: before the seam existed,
    this test's `GET /api/health/live` would not return until the slow commit did."""
    from book_tracker.application.imports import ImportService

    def slow_commit(self: ImportService, batch_id: str, choices: dict) -> dict:  # type: ignore[no-untyped-def]
        time.sleep(0.5)
        return {
            "batch_id": batch_id,
            "state": "committed",
            "created_items": 0,
            "created_entries": 0,
            "unchanged_entries": 0,
            "unsorted_entries": 0,
        }

    monkeypatch.setattr(ImportService, "commit", slow_commit)

    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        import asyncio

        started = time.perf_counter()
        commit_task = asyncio.create_task(
            client.post(
                "/api/import/goodreads/commit",
                json={"batch_id": "irrelevant-since-commit-is-patched", "choices": []},
            )
        )
        await asyncio.sleep(0.05)  # let the commit request actually start first
        health = await client.get("/api/health/live")
        health_elapsed = time.perf_counter() - started

        commit_response = await commit_task
        assert commit_response.status_code == 200
        assert health.status_code == 200
        # The health check must land well before the 0.5s commit does — if the
        # commit still ran on the loop, this would take >= 0.5s too.
        assert health_elapsed < 0.3, f"a concurrent request waited {health_elapsed:.3f}s"


@pytest.mark.anyio
async def test_concurrent_writes_through_the_offloaded_path_leave_a_correct_ledger(
    tmp_path: Path,
) -> None:
    """An import commit running through `off_loop` while another request writes
    through the same engine: no lost row, no partial batch, both land correctly."""
    csv_body = (
        "Book Id,Title,Author,Additional Authors,ISBN,ISBN13,My Rating,Publisher,"
        "Number of Pages,Year Published,Original Publication Year,Date Read,Date Added,"
        "Bookshelves,Exclusive Shelf,My Review,Read Count\n"
        '201,Rayuela,Julio Cortázar,,="",="9788437604572",4,Sudamericana,736,1963,1963,'
        ',2024/01/02,"read",read,,0\n'
        '202,El Aleph,Jorge Luis Borges,,="014118776X",="",0,Emecé,224,1949,1949,,'
        '2023/05/06,"to-read",to-read,,0\n'
    ).encode()
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        import asyncio

        preview = await client.post(
            "/api/import/goodreads/preview",
            files={"file": ("library.csv", csv_body, "text/csv")},
        )
        assert preview.status_code == 201
        batch_id = preview.json()["batch_id"]

        commit_task = asyncio.create_task(
            client.post("/api/import/goodreads/commit", json={"batch_id": batch_id, "choices": []})
        )
        manual_task = asyncio.create_task(
            client.post(
                "/api/entries",
                json={
                    "manual": {
                        "item_type": "book",
                        "title": "Concurrent write, unrelated to the import",
                        "metadata": {"creators": ["Sprint 059"]},
                    },
                    "status": "read",
                    "idempotency_key": "event-loop-concurrency-drill",
                },
            )
        )
        commit_response, manual_response = await asyncio.gather(commit_task, manual_task)

        assert commit_response.status_code == 200, commit_response.text
        assert commit_response.json()["created_entries"] == 2
        assert manual_response.status_code == 201, manual_response.text

        library = await client.get(
            "/api/entries", params={"limit": 200, "status": "unsorted", "sort": "date_added"}
        )
        imported_titles = {entry["item"]["title"] for entry in library.json()["items"]}
        assert {"Rayuela", "El Aleph"} <= imported_titles

        manual = await client.get(
            "/api/entries", params={"limit": 200, "status": "read", "sort": "date_added"}
        )
        manual_titles = {entry["item"]["title"] for entry in manual.json()["items"]}
        assert "Concurrent write, unrelated to the import" in manual_titles


@pytest.mark.anyio
async def test_a_queued_writer_surfaces_a_typed_error_rather_than_database_is_locked(
    tmp_path: Path,
) -> None:
    """A busy_timeout that still expires under real contention must not leak a raw
    driver message — Sprint 059 is the first time two real OS threads can contend
    for this engine's write lock at all."""
    settings = Settings(
        data_dir=tmp_path, user_agent_contact="test@example.invalid", sqlite_busy_timeout_ms=100
    )
    assert settings.database_url is not None
    upgrade(settings.database_url)
    holder_engine = create_engine(settings)

    release = threading.Event()
    acquired = threading.Event()

    def hold_the_write_lock() -> None:
        with holder_engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            acquired.set()
            release.wait(timeout=5)
            connection.exec_driver_sql("COMMIT")

    holder = threading.Thread(target=hold_the_write_lock, daemon=True)
    holder.start()
    assert acquired.wait(timeout=5), "the holder thread never acquired the write lock"

    try:
        app = create_app(settings)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
        ):
            response = await client.post(
                "/api/entries",
                json={
                    "manual": {
                        "item_type": "book",
                        "title": "Should not crash with a raw sqlite error",
                        "metadata": {"creators": ["Sprint 059"]},
                    },
                    "status": "read",
                    "idempotency_key": "event-loop-busy-drill",
                },
            )
    finally:
        release.set()
        holder.join(timeout=5)
        holder_engine.dispose()

    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "library_busy"
