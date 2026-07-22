"""Durable in-process job queue, leasing, retries, and clock utilities."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from book_tracker.infrastructure.models import JobRow


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


LEASE_DURATION = timedelta(minutes=5)
DEFAULT_MAX_RETRIES = 3


@dataclass(frozen=True)
class ClaimedJob:
    id: str
    batch_id: str | None
    kind: str
    payload: dict[str, Any]
    attempts: int
    state: str
    lease_expires_at: str | None
    heartbeat_at: str | None


class JobRepository:
    """DB-backed job queue with leasing, retries, and progress tracking."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def _write(self) -> Iterator[Session]:
        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            session = Session(bind=connection)
            try:
                yield session
                session.flush()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                session.close()

    def enqueue(
        self,
        batch_id: str | None,
        kind: str,
        payload: Mapping[str, Any],
        *,
        available_at: datetime | None = None,
    ) -> str:
        job_id = str(uuid.uuid4())
        now = _now()
        available = (available_at or datetime.now(UTC)).isoformat().replace("+00:00", "Z")
        with self._write() as session:
            session.add(
                JobRow(
                    id=job_id,
                    batch_id=batch_id,
                    kind=kind,
                    state="queued",
                    payload=json.dumps(dict(payload)),
                    progress="{}",
                    error=None,
                    attempts=0,
                    available_at=available,
                    heartbeat_at=None,
                    lease_expires_at=None,
                    finished_at=None,
                    created_at=now,
                    updated_at=now,
                )
            )
        return job_id

    def claim(self, now: datetime) -> ClaimedJob | None:
        """Atomically claim one queued job whose available_at has passed."""
        now_iso = now.isoformat().replace("+00:00", "Z")
        lease_iso = (now + LEASE_DURATION).isoformat().replace("+00:00", "Z")
        with self._write() as session:
            row = session.scalar(
                select(JobRow)
                .where(JobRow.state == "queued", JobRow.available_at <= now_iso)
                .order_by(JobRow.available_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if row is None:
                return None
            row.state = "running"
            row.heartbeat_at = now_iso
            row.lease_expires_at = lease_iso
            row.updated_at = now_iso
            return ClaimedJob(
                id=row.id,
                batch_id=row.batch_id,
                kind=row.kind,
                payload=json.loads(row.payload),
                attempts=row.attempts,
                state=row.state,
                lease_expires_at=row.lease_expires_at,
                heartbeat_at=row.heartbeat_at,
            )

    def heartbeat(self, job_id: str, now: datetime) -> None:
        now_iso = now.isoformat().replace("+00:00", "Z")
        lease_iso = (now + LEASE_DURATION).isoformat().replace("+00:00", "Z")
        with self._write() as session:
            row = session.get(JobRow, job_id)
            if row is not None and row.state == "running":
                row.heartbeat_at = now_iso
                row.lease_expires_at = lease_iso
                row.updated_at = now_iso

    def complete(
        self, job_id: str, progress: Mapping[str, Any], now: datetime
    ) -> None:
        now_iso = now.isoformat().replace("+00:00", "Z")
        with self._write() as session:
            row = session.get(JobRow, job_id)
            if row is None:
                raise LookupError(job_id)
            row.state = "succeeded"
            row.progress = json.dumps(dict(progress))
            row.finished_at = now_iso
            row.lease_expires_at = None
            row.updated_at = now_iso

    def fail(
        self, job_id: str, error: str, now: datetime, *, max_retries: int = DEFAULT_MAX_RETRIES
    ) -> None:
        now_iso = now.isoformat().replace("+00:00", "Z")
        with self._write() as session:
            row = session.get(JobRow, job_id)
            if row is None:
                raise LookupError(job_id)
            row.attempts += 1
            row.error = error
            row.lease_expires_at = None
            row.heartbeat_at = None
            if row.attempts >= max_retries:
                row.state = "failed"
                row.finished_at = now_iso
            else:
                row.state = "queued"
                row.available_at = now_iso
            row.updated_at = now_iso

    def cancel(self, job_id: str) -> None:
        now_iso = _now()
        with self._write() as session:
            row = session.get(JobRow, job_id)
            if row is None:
                return
            if row.state in ("succeeded", "failed", "cancelled"):
                return
            row.state = "cancelled"
            row.finished_at = now_iso
            row.lease_expires_at = None
            row.updated_at = now_iso

    def cancel_batch_jobs(self, batch_id: str) -> int:
        """Cancel all non-terminal jobs belonging to a batch."""
        now_iso = _now()
        with self._write() as session:
            rows = list(
                session.scalars(
                    select(JobRow).where(
                        JobRow.batch_id == batch_id,
                        JobRow.state.in_(("queued", "running")),
                    )
                )
            )
            for row in rows:
                row.state = "cancelled"
                row.finished_at = now_iso
                row.lease_expires_at = None
                row.updated_at = now_iso
            return len(rows)

    def reclaim_expired(self, now: datetime) -> Sequence[str]:
        """Return expired running jobs to queued with incremented attempts.

        Called at startup to recover from crashes and at each poll tick.
        """
        now_iso = now.isoformat().replace("+00:00", "Z")
        with self._write() as session:
            rows = list(
                session.scalars(
                    select(JobRow).where(
                        JobRow.state == "running",
                        JobRow.lease_expires_at.is_not(None),
                        JobRow.lease_expires_at <= now_iso,
                    )
                )
            )
            for row in rows:
                row.state = "queued"
                row.attempts += 1
                row.available_at = now_iso
                row.lease_expires_at = None
                row.heartbeat_at = None
                row.updated_at = now_iso
            return [row.id for row in rows]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with Session(self.engine) as session:
            row = session.get(JobRow, job_id)
            if row is None:
                return None
            return {
                "id": row.id,
                "batch_id": row.batch_id,
                "kind": row.kind,
                "state": row.state,
                "payload": json.loads(row.payload),
                "progress": json.loads(row.progress),
                "error": row.error,
                "attempts": row.attempts,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "finished_at": row.finished_at,
            }

    def list_batch_jobs(self, batch_id: str) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            rows = list(
                session.scalars(
                    select(JobRow)
                    .where(JobRow.batch_id == batch_id)
                    .order_by(JobRow.created_at)
                )
            )
            return [
                {
                    "id": row.id,
                    "batch_id": row.batch_id,
                    "kind": row.kind,
                    "state": row.state,
                    "progress": json.loads(row.progress),
                    "error": row.error,
                    "attempts": row.attempts,
                    "created_at": row.created_at,
                    "finished_at": row.finished_at,
                }
                for row in rows
            ]


class RateLimiter:
    """Clock-injected minimum-interval gate for provider calls."""

    def __init__(self, *, min_interval_seconds: float = 0.5) -> None:
        self.min_interval = timedelta(seconds=min_interval_seconds)
        self._last_call: datetime | None = None

    def acquire(self, now: datetime) -> bool:
        if self._last_call is None or (now - self._last_call) >= self.min_interval:
            self._last_call = now
            return True
        return False


class JobRunner:
    """Cooperative poller that claims and processes jobs in the FastAPI lifespan.

    Handlers are idempotent: replay after crash recovery does not double-apply.
    """

    def __init__(
        self,
        engine: Engine,
        handlers: Mapping[str, Any],
        *,
        rate_limiter: RateLimiter | None = None,
        poll_interval: float = 1.0,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self.engine = engine
        self.repo = JobRepository(engine)
        self.handlers = handlers
        self.rate_limiter = rate_limiter
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self._running = False

    async def tick(self, now: datetime) -> bool:
        """Process at most one job. Returns True if a job was processed."""
        claimed = self.repo.claim(now)
        if claimed is None:
            return False
        handler = self.handlers.get(claimed.kind)
        if handler is None:
            self.repo.fail(claimed.id, f"no_handler:{claimed.kind}", now)
            return True
        try:
            result = await handler.process(claimed.id, now)
            if result["state"] == "succeeded":
                self.repo.complete(claimed.id, result.get("progress", {}), now)
            elif result["state"] == "cancelled":
                self.repo.cancel(claimed.id)
            else:
                self.repo.fail(claimed.id, result.get("error", "unknown"), now)
        except Exception as exc:
            self.repo.fail(claimed.id, str(exc)[:200], now)
        return True