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


def _awaits(function: object) -> bool:
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))  # type: ignore[arg-type]
    return any(
        isinstance(node, (ast.Await, ast.AsyncFor, ast.AsyncWith))
        for node in ast.walk(tree.body[0])
    )


def test_no_route_runs_synchronous_work_as_a_coroutine_that_never_awaits(tmp_path: Path) -> None:
    """Sprint 087's rule (production-grade proposal R3). FastAPI runs an `async def`
    endpoint on the event loop and a `def` endpoint on a worker thread. An `async def`
    that never awaits gains nothing from being a coroutine and runs every one of its
    synchronous queries on the loop, stalling every other request while it does. 45
    routes were exactly that. A route that genuinely awaits keeps `async def` and puts
    its synchronous part through `off_loop`."""
    import inspect

    from fastapi.routing import APIRoute

    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html>", encoding="utf-8")
    app = create_app(
        Settings(data_dir=tmp_path, static_dir=static, user_agent_contact="test@example.invalid")
    )
    offenders = sorted(
        f"{route.endpoint.__module__}.{route.endpoint.__name__}"
        for route in app.routes
        if isinstance(route, APIRoute)
        and inspect.iscoroutinefunction(route.endpoint)
        and not _awaits(route.endpoint)
    )
    assert offenders == []


async def _health_while(app, slow_request, window: float = 1.2) -> float:  # type: ignore[no-untyped-def]
    """The worst delay `/api/health/live` sees while `slow_request` is in flight.

    Sampled repeatedly across the window, and timed from before each pause, so a
    loop blocked at any moment shows up as a late sample rather than being hidden
    in the gap before a single timer starts."""
    import asyncio

    pause = 0.02
    worst = 0.0
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        slow = asyncio.create_task(slow_request(client))
        deadline = time.perf_counter() + window
        while time.perf_counter() < deadline:
            started = time.perf_counter()
            await asyncio.sleep(pause)
            health = await client.get("/api/health/live")
            assert health.status_code == 200
            worst = max(worst, time.perf_counter() - started - pause)
        await slow
    return worst


@pytest.mark.anyio
async def test_the_authentication_boundary_looks_people_up_off_the_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every authenticated request asks the database whether anyone has set up an
    account and whose session its cookie names. Both were synchronous calls inside
    the middleware, so a slow lookup held up every request behind it (Sprint 087)."""
    import book_tracker.app.middleware as main_module

    def slow_has_credentialed_user(engine) -> bool:  # type: ignore[no-untyped-def]
        time.sleep(0.5)
        return True

    monkeypatch.setattr(main_module, "has_credentialed_user", slow_has_credentialed_user)
    app = create_app(
        Settings(data_dir=tmp_path, auth="on", user_agent_contact="test@example.invalid")
    )
    elapsed = await _health_while(app, lambda client: client.get("/api/shelves"))
    assert elapsed < 0.3, f"health waited {elapsed:.3f}s behind a session lookup"


@pytest.mark.anyio
async def test_the_job_runner_claims_work_off_the_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runner lives in the same process as the API. Its claim, completion and
    reclaim queries ran on the event loop, so a contended jobs table stalled every
    request for as long as a claim waited on the write lock (Sprint 087)."""
    import asyncio

    from book_tracker.infrastructure.jobs import JobRepository

    def slow_claim(self, now):  # type: ignore[no-untyped-def]
        time.sleep(0.5)
        return None

    monkeypatch.setattr(JobRepository, "claim", slow_claim)
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    elapsed = await _health_while(app, lambda client: asyncio.sleep(0.6))
    assert elapsed < 0.3, f"health waited {elapsed:.3f}s behind a job claim"
