"""Durable job runner, enrichment, and undo tests for Sprint 011."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from book_tracker.application.undo import UndoExpiredError, UndoService
from book_tracker.config import Settings
from book_tracker.database import create_engine as create_sqlalchemy_engine
from book_tracker.infrastructure.jobs import JobRepository, RateLimiter
from book_tracker.infrastructure.models import JobRow
from book_tracker.main import create_app
from book_tracker.migrations import upgrade

# ---------------------------------------------------------------------------
# Sync engine fixture for DB-only tests
# ---------------------------------------------------------------------------


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url)
    value = create_sqlalchemy_engine(configured)
    yield value
    value.dispose()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _create_committed_batch(
    eng: Engine,
    batch_id: str = "batch-undo-1",
    *,
    kind: str = "goodreads",
    undo_hours: int = 24,
) -> str:
    now = _now_iso()
    expires = (datetime.now(UTC) + timedelta(hours=undo_hours)).isoformat().replace("+00:00", "Z")
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO import_batches"
                "(id,kind,fingerprint,state,source_descriptor,preview_summary,"
                "counters,error,committed_at,undo_expires_at,created_at,updated_at) "
                "VALUES(:id,:kind,'fp-test','committed','{}','{}',:counters,NULL,"
                ":committed_at,:expires,:now,:now)"
            ),
            {
                "id": batch_id,
                "kind": kind,
                "counters": json.dumps(
                    {"created_items": 1, "created_entries": 1, "unchanged_entries": 0}
                ),
                "committed_at": now,
                "expires": expires,
                "now": now,
            },
        )
        conn.execute(
            text(
                "INSERT INTO import_records"
                "(batch_id,row_number,normalized_payload,matched_item_id,"
                "matched_entry_id,match_kind,planned_action,conflicts,"
                "validation_errors,created_at,updated_at) "
                "VALUES(:bid,1,'{}',NULL,NULL,NULL,NULL,'{}','[]',:now,:now)"
            ),
            {"bid": batch_id, "now": now},
        )
    return batch_id


def _add_create_effect(
    eng: Engine, batch_id: str, record_id: int, entity_type: str, entity_id: int
) -> int:
    with eng.begin() as conn:
        return conn.execute(
            text(
                "INSERT INTO import_effects"
                "(batch_id,record_id,effect_type,entity_type,entity_id,"
                "before_values,after_values) "
                "VALUES(:bid,:rid,'create',:etype,:eid,'{}',:after) RETURNING effect_id"
            ),
            {
                "bid": batch_id,
                "rid": record_id,
                "etype": entity_type,
                "eid": str(entity_id),
                "after": json.dumps({"created": True}),
            },
        ).scalar_one()


def _add_fill_empty_effect(
    eng: Engine,
    batch_id: str,
    record_id: int,
    entity_type: str,
    entity_id: str,
    field: str,
    before: Any,
    after: Any,
) -> int:
    with eng.begin() as conn:
        return conn.execute(
            text(
                "INSERT INTO import_effects"
                "(batch_id,record_id,effect_type,entity_type,entity_id,"
                "before_values,after_values) "
                "VALUES(:bid,:rid,'fill_empty',:etype,:eid,:before,:after) "
                "RETURNING effect_id"
            ),
            {
                "bid": batch_id,
                "rid": record_id,
                "etype": entity_type,
                "eid": entity_id,
                "before": json.dumps({field: before}),
                "after": json.dumps({field: after}),
            },
        ).scalar_one()


def _create_item(
    eng: Engine, title: str, year: int | None = None, metadata: dict | None = None
) -> int:
    with eng.begin() as conn:
        return conn.execute(
            text(
                "INSERT INTO items"
                "(title,year,cover_path,identifiers,metadata,created_at,updated_at) "
                "VALUES(:title,:year,NULL,'{}',:metadata,'n','n') RETURNING id"
            ),
            {
                "title": title,
                "year": year,
                "metadata": json.dumps(metadata or {"authors": ["A"]}),
            },
        ).scalar_one()


def _create_entry(
    eng: Engine, item_id: int, status: str = "unsorted", score: int | None = None
) -> int:
    with eng.begin() as conn:
        return conn.execute(
            text(
                "INSERT INTO entries"
                "(user_id,item_id,status,score,notes,date_added,"
                "reread_count,score_provisional,created_at,updated_at) "
                "VALUES(1,:item_id,:status,:score,NULL,'n',0,0,'n','n') RETURNING id"
            ),
            {"item_id": item_id, "status": status, "score": score},
        ).scalar_one()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")


# ---------------------------------------------------------------------------
# AC1: Job lifecycle — queue, lease, complete, retry, cancel, restart survival
# ---------------------------------------------------------------------------


class TestJobLifecycle:
    def test_enqueue_creates_queued_job(self, engine: Engine) -> None:
        repo = JobRepository(engine)
        job_id = repo.enqueue(None, "enrich_item", {"item_id": 5})
        with Session(engine) as session:
            job = session.get(JobRow, job_id)
            assert job is not None
            assert job.state == "queued"
            assert job.kind == "enrich_item"
            assert job.batch_id is None
            assert json.loads(job.payload) == {"item_id": 5}
            assert job.attempts == 0

    def test_claim_leases_one_queued_job(self, engine: Engine) -> None:
        repo = JobRepository(engine)
        job_id = repo.enqueue(None, "enrich_item", {"item_id": 5})
        now = datetime.now(UTC)
        claimed = repo.claim(now)
        assert claimed is not None
        assert claimed.id == job_id
        assert claimed.state == "running"
        assert claimed.lease_expires_at is not None
        assert claimed.heartbeat_at is not None
        # Second claim returns None when queue is empty
        assert repo.claim(now) is None

    def test_complete_sets_succeeded(self, engine: Engine) -> None:
        repo = JobRepository(engine)
        job_id = repo.enqueue(None, "enrich_item", {"item_id": 5})
        now = datetime.now(UTC)
        repo.claim(now)
        repo.complete(job_id, {"filled": ["year"]}, now)
        with Session(engine) as session:
            job = session.get(JobRow, job_id)
            assert job is not None
            assert job.state == "succeeded"
            assert job.finished_at is not None
            assert json.loads(job.progress) == {"filled": ["year"]}

    def test_fail_increments_attempts_and_requeues(self, engine: Engine) -> None:
        repo = JobRepository(engine)
        job_id = repo.enqueue(None, "enrich_item", {"item_id": 5})
        now = datetime.now(UTC)
        repo.claim(now)
        repo.fail(job_id, "provider_timeout", now, max_retries=3)
        with Session(engine) as session:
            job = session.get(JobRow, job_id)
            assert job is not None
            assert job.state == "queued"
            assert job.attempts == 1
            assert job.error == "provider_timeout"
            assert job.lease_expires_at is None

    def test_fail_exhausts_retries_to_terminal_failed(self, engine: Engine) -> None:
        repo = JobRepository(engine)
        job_id = repo.enqueue(None, "enrich_item", {"item_id": 5})
        now = datetime.now(UTC)
        for _ in range(3):  # max_retries=3, 3rd fail is terminal
            repo.claim(now)
            repo.fail(job_id, "provider_timeout", now, max_retries=3)
        with Session(engine) as session:
            job = session.get(JobRow, job_id)
            assert job is not None
            assert job.state == "failed"
            assert job.attempts == 3
            assert job.finished_at is not None

    def test_cancel_sets_cancelled_state(self, engine: Engine) -> None:
        repo = JobRepository(engine)
        job_id = repo.enqueue(None, "enrich_item", {"item_id": 5})
        repo.cancel(job_id)
        with Session(engine) as session:
            job = session.get(JobRow, job_id)
            assert job is not None
            assert job.state == "cancelled"
            assert job.finished_at is not None

    def test_cancel_batch_jobs_cancels_all_for_batch(self, engine: Engine) -> None:
        repo = JobRepository(engine)
        j1 = repo.enqueue(None, "enrich_item", {"item_id": 1})
        j2 = repo.enqueue(None, "enrich_item", {"item_id": 2})
        j3 = repo.enqueue(None, "enrich_item", {"item_id": 3})
        with engine.begin() as conn:
            for bid in ("b1", "b2"):
                conn.execute(
                    text(
                        "INSERT INTO import_batches"
                        "(id,kind,fingerprint,state,source_descriptor,preview_summary,"
                        "counters,created_at,updated_at) "
                        "VALUES(:id,'goodreads',:fp,'previewed','{}','{}','{}','n','n')"
                    ),
                    {"id": bid, "fp": f"fp-{bid}"},
                )
            conn.execute(text("UPDATE jobs SET batch_id='b1' WHERE id=:id"), {"id": j1})
            conn.execute(text("UPDATE jobs SET batch_id='b1' WHERE id=:id"), {"id": j2})
            conn.execute(text("UPDATE jobs SET batch_id='b2' WHERE id=:id"), {"id": j3})
        repo.cancel_batch_jobs("b1")
        with Session(engine) as session:
            for jid in (j1, j2):
                job = session.get(JobRow, jid)
                assert job is not None
                assert job.state == "cancelled"
            job3 = session.get(JobRow, j3)
            assert job3 is not None
            assert job3.state == "queued"

    def test_reclaim_expired_running_returns_to_queued(self, engine: Engine) -> None:
        repo = JobRepository(engine)
        job_id = repo.enqueue(None, "enrich_item", {"item_id": 5})
        now = datetime.now(UTC)
        repo.claim(now)
        future = now + timedelta(minutes=10)
        reclaimed = repo.reclaim_expired(future)
        assert len(reclaimed) == 1
        assert reclaimed[0] == job_id
        with Session(engine) as session:
            job = session.get(JobRow, job_id)
            assert job.state == "queued"
            assert job.attempts == 1
            assert job.lease_expires_at is None

    def test_restart_survival_expired_running_reclaimed_on_startup(self, tmp_path: Path) -> None:
        """AC1: Queued and running jobs survive a simulated restart."""
        configured = settings(tmp_path)
        assert configured.database_url is not None
        upgrade(configured.database_url)
        eng = create_sqlalchemy_engine(configured)
        try:
            repo = JobRepository(eng)
            job_id = repo.enqueue(None, "enrich_item", {"item_id": 5})
            now = datetime.now(UTC)
            repo.claim(now)
        finally:
            eng.dispose()
        # Simulate restart: new engine, same database file
        eng2 = create_sqlalchemy_engine(configured)
        try:
            repo2 = JobRepository(eng2)
            future = datetime.now(UTC) + timedelta(minutes=10)
            reclaimed = repo2.reclaim_expired(future)
            assert len(reclaimed) == 1
            with Session(eng2) as session:
                job = session.get(JobRow, job_id)
                assert job is not None
                assert job.state == "queued"
                assert job.attempts == 1
        finally:
            eng2.dispose()

    def test_get_job_returns_state_and_progress(self, engine: Engine) -> None:
        repo = JobRepository(engine)
        job_id = repo.enqueue(None, "enrich_item", {"item_id": 5})
        now = datetime.now(UTC)
        repo.claim(now)
        repo.complete(job_id, {"filled": ["year", "publisher"]}, now)
        info = repo.get_job(job_id)
        assert info is not None
        assert info["state"] == "succeeded"
        assert info["progress"] == {"filled": ["year", "publisher"]}
        assert info["kind"] == "enrich_item"

    def test_list_batch_jobs(self, engine: Engine) -> None:
        repo = JobRepository(engine)
        j1 = repo.enqueue(None, "enrich_item", {"item_id": 1})
        j2 = repo.enqueue(None, "enrich_cover", {"item_id": 1})
        repo.enqueue(None, "enrich_item", {"item_id": 2})
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO import_batches"
                    "(id,kind,fingerprint,state,source_descriptor,preview_summary,"
                    "counters,created_at,updated_at) "
                    "VALUES('b1','goodreads','fp','previewed','{}','{}','{}','n','n')"
                ),
            )
            conn.execute(
                text("UPDATE jobs SET batch_id='b1' WHERE id IN (:j1,:j2)"), {"j1": j1, "j2": j2}
            )
        jobs = repo.list_batch_jobs("b1")
        assert len(jobs) == 2
        assert all(j["batch_id"] == "b1" for j in jobs)


# ---------------------------------------------------------------------------
# AC2: Clock-injected rate limiting and retry caps
# ---------------------------------------------------------------------------


class TestRateLimiting:
    def test_rate_limiter_enforces_minimum_interval(self) -> None:
        limiter = RateLimiter(min_interval_seconds=0.5)
        t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert limiter.acquire(t0) is True
        assert limiter.acquire(t0) is False
        assert limiter.acquire(t0 + timedelta(seconds=0.5)) is True

    def test_rate_limiter_with_injected_clock(self) -> None:
        limiter = RateLimiter(min_interval_seconds=1.0)
        times = [
            datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 0, 0, 0, 500000, tzinfo=UTC),
            datetime(2026, 1, 1, 0, 0, 1, 0, tzinfo=UTC),
        ]
        results = [limiter.acquire(t) for t in times]
        assert results == [True, False, True]


# ---------------------------------------------------------------------------
# AC3: Safe undo — revert matching, preserve edited, shared, pre-existing
# ---------------------------------------------------------------------------


class TestUndo:
    def test_undo_reverts_matching_values(self, engine: Engine) -> None:
        """AC3: Undo reverts a field only if current value matches recorded after-value."""
        batch_id = _create_committed_batch(engine)
        item_id = _create_item(engine, "Test", year=2000)
        entry_id = _create_entry(engine, item_id, "read", 8)
        _add_create_effect(engine, batch_id, 1, "item", item_id)
        _add_create_effect(engine, batch_id, 1, "entry", entry_id)
        undo = UndoService(engine)
        result = undo.undo(batch_id)
        assert result["reverted_entries"] >= 1
        assert result["reverted_items"] >= 1
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT count(*) FROM entries")) == 0
            assert conn.scalar(text("SELECT count(*) FROM items")) == 0

    def test_undo_preserves_later_user_edits(self, engine: Engine) -> None:
        """AC3: Undo cannot remove later user edits; skips fields that changed."""
        batch_id = _create_committed_batch(engine)
        item_id = _create_item(engine, "Test", year=None)
        entry_id = _create_entry(engine, item_id, "unsorted")
        _add_create_effect(engine, batch_id, 1, "item", item_id)
        _add_create_effect(engine, batch_id, 1, "entry", entry_id)
        _add_fill_empty_effect(engine, batch_id, 1, "item", str(item_id), "year", None, 2000)
        # User later edited the year to 1950
        with engine.begin() as conn:
            conn.execute(text("UPDATE items SET year=1950 WHERE id=:id"), {"id": item_id})
        undo = UndoService(engine)
        result = undo.undo(batch_id)
        assert result["retained"] >= 1
        with engine.connect() as conn:
            # Item was modified after import — undo retains it, deletes entry only
            assert conn.scalar(text("SELECT count(*) FROM items")) == 1
            year = conn.scalar(text("SELECT year FROM items WHERE id=:id"), {"id": item_id})
            assert year == 1950

    def test_undo_preserves_shared_items(self, engine: Engine) -> None:
        """AC3: Undo cannot remove items referenced by entries from other batches."""
        batch_id = _create_committed_batch(engine)
        # Pre-existing item with a pre-existing entry (not created by this batch)
        item_id = _create_item(engine, "Pre-existing", year=2000)
        _create_entry(engine, item_id, "read", 7)
        # Batch filled year on this existing item (no create effect)
        _add_fill_empty_effect(engine, batch_id, 1, "item", str(item_id), "year", None, 2000)
        undo = UndoService(engine)
        result = undo.undo(batch_id)
        # Year should be reverted (current 2000 matches after 2000)
        assert result["reverted"] >= 1
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT count(*) FROM entries")) == 1
            assert conn.scalar(text("SELECT count(*) FROM items")) == 1
            year = conn.scalar(text("SELECT year FROM items WHERE id=:id"), {"id": item_id})
            assert year is None  # reverted to before-value (None)

    def test_undo_preserves_pre_existing_entries(self, engine: Engine) -> None:
        """AC3: Undo cannot remove pre-existing entries not created by the batch."""
        batch_id = _create_committed_batch(engine)
        item_id = _create_item(engine, "Pre-existing", year=2000)
        _create_entry(engine, item_id, "read", 9)
        # Batch only filled year on this pre-existing item
        _add_fill_empty_effect(engine, batch_id, 1, "item", str(item_id), "year", None, 2000)
        undo = UndoService(engine)
        result = undo.undo(batch_id)
        assert result["reverted_entries"] == 0
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT count(*) FROM entries")) == 1
            assert conn.scalar(text("SELECT count(*) FROM items")) == 1


# ---------------------------------------------------------------------------
# AC4: Partial retention reporting + repeated undo
# ---------------------------------------------------------------------------


class TestUndoReporting:
    def test_undo_reports_reverted_retained_and_skipped(self, engine: Engine) -> None:
        """AC4: Partial retention is reported when fields were edited after import."""
        batch_id = _create_committed_batch(engine)
        item_id = _create_item(engine, "Test", year=None)
        entry_id = _create_entry(engine, item_id, "unsorted")
        _add_create_effect(engine, batch_id, 1, "item", item_id)
        _add_create_effect(engine, batch_id, 1, "entry", entry_id)
        _add_fill_empty_effect(engine, batch_id, 1, "item", str(item_id), "year", None, 2000)
        _add_fill_empty_effect(
            engine, batch_id, 1, "item", str(item_id), "metadata.publisher", None, "Penguin"
        )
        # User edited year to 1950 after import
        with engine.begin() as conn:
            conn.execute(text("UPDATE items SET year=1950 WHERE id=:id"), {"id": item_id})
        undo = UndoService(engine)
        result = undo.undo(batch_id)
        assert "reverted" in result
        assert "retained" in result
        assert "skipped" in result
        assert result["retained"] >= 1

    def test_repeated_undo_is_harmless(self, engine: Engine) -> None:
        """AC4: Repeated undo is harmless — second call is a no-op."""
        batch_id = _create_committed_batch(engine)
        item_id = _create_item(engine, "Test")
        entry_id = _create_entry(engine, item_id, "unsorted")
        _add_create_effect(engine, batch_id, 1, "item", item_id)
        _add_create_effect(engine, batch_id, 1, "entry", entry_id)
        undo = UndoService(engine)
        undo.undo(batch_id)
        second = undo.undo(batch_id)
        assert second["reverted"] == 0
        assert second["retained"] == 0
        assert second["skipped"] >= 1

    def test_undo_expired_batch_is_rejected(self, engine: Engine) -> None:
        """Undo is available only within the 24-hour window."""
        now = datetime.now(UTC)
        expired = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO import_batches"
                    "(id,kind,fingerprint,state,source_descriptor,preview_summary,"
                    "counters,error,committed_at,undo_expires_at,created_at,updated_at) "
                    "VALUES('expired-1','goodreads','fp','committed','{}','{}','{}',"
                    "NULL,:committed,:expired,:now,:now)"
                ),
                {
                    "committed": now.isoformat().replace("+00:00", "Z"),
                    "expired": expired,
                    "now": now.isoformat().replace("+00:00", "Z"),
                },
            )
        undo = UndoService(engine)
        with pytest.raises(UndoExpiredError):
            undo.undo("expired-1")


# ---------------------------------------------------------------------------
# AC5: Late-job cancellation
# ---------------------------------------------------------------------------


class TestLateJobCancellation:
    def test_late_job_from_undone_batch_is_cancelled(self, engine: Engine) -> None:
        """AC5: Late jobs from an undone batch cannot mutate data and are marked cancelled."""
        batch_id = _create_committed_batch(engine)
        item_id = _create_item(engine, "Test")
        repo = JobRepository(engine)
        job_id = repo.enqueue(
            batch_id, "enrich_item", {"item_id": item_id, "isbn": "9780141187761"}
        )
        undo = UndoService(engine)
        undo.undo(batch_id)
        with Session(engine) as session:
            job = session.get(JobRow, job_id)
            assert job.state == "cancelled"


# ---------------------------------------------------------------------------
# AC7: Progress API
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_job_progress(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        repo = JobRepository(app.state.engine)
        job_id = repo.enqueue(None, "enrich_item", {"item_id": 5})
        now = datetime.now(UTC)
        repo.claim(now)
        repo.complete(job_id, {"filled": ["year"]}, now)
        response = await client.get(f"/api/import/jobs/{job_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == job_id
        assert body["state"] == "succeeded"
        assert body["progress"] == {"filled": ["year"]}


@pytest.mark.anyio
async def test_get_job_not_found(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.get("/api/import/jobs/nonexistent")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Undo API
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_undo_batch(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        batch_id = _create_committed_batch(app.state.engine)
        item_id = _create_item(app.state.engine, "Test")
        entry_id = _create_entry(app.state.engine, item_id, "unsorted")
        _add_create_effect(app.state.engine, batch_id, 1, "item", item_id)
        _add_create_effect(app.state.engine, batch_id, 1, "entry", entry_id)
        response = await client.delete(f"/api/import/batches/{batch_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["batch_id"] == batch_id
        assert body["state"] == "undone"
        assert "reverted" in body
        assert "retained" in body
        with app.state.engine.connect() as conn:
            assert conn.scalar(text("SELECT count(*) FROM entries")) == 0


@pytest.mark.anyio
async def test_undo_expired_batch_returns_409(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        now = datetime.now(UTC)
        expired = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        with app.state.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO import_batches"
                    "(id,kind,fingerprint,state,source_descriptor,preview_summary,"
                    "counters,error,committed_at,undo_expires_at,created_at,updated_at) "
                    "VALUES('expired-1','goodreads','fp','committed','{}','{}','{}',"
                    "NULL,:committed,:expired,:now,:now)"
                ),
                {
                    "committed": now.isoformat().replace("+00:00", "Z"),
                    "expired": expired,
                    "now": now.isoformat().replace("+00:00", "Z"),
                },
            )
        response = await client.delete("/api/import/batches/expired-1")
        assert response.status_code == 409


@pytest.mark.anyio
async def test_undo_not_found(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.delete("/api/import/batches/nonexistent")
        assert response.status_code == 404
