"""Robustness follow-ups (Sprint 129): failures that are not the provider's, kept off it."""

import asyncio
import hashlib
import os
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import Engine, text

from book_tracker.application.imports import (
    ImportService,
    resume_interrupted_installs,
    resume_staged_install,
)
from book_tracker.application.providers import search_providers
from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.domain.providers import SearchCandidate, SourceRef
from book_tracker.infrastructure.attachments import blob_path, store_blob
from book_tracker.infrastructure.covers import install_cover
from book_tracker.infrastructure.jobs import JobRepository, JobRunner
from book_tracker.infrastructure.observed import (
    ObservedProvider,
    ProviderObservations,
    ResponseCache,
)
from book_tracker.migrations import upgrade
from book_tracker.reclaim import reclaim_import_batches, unconsumed_stage_files


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _Answering:
    name = "openlibrary"
    item_type = "book"

    def __init__(self) -> None:
        self.searches = 0

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        self.searches += 1
        return [
            SearchCandidate(
                source="openlibrary",
                source_id="OL1W",
                source_refs=(SourceRef("openlibrary", "OL1W"),),
                title="Dune",
                subtitle=None,
                creators=("Frank Herbert",),
                year=1965,
                cover_url=None,
                identifiers={},
                language=None,
                metadata={},
            )
        ]


@pytest.mark.anyio
async def test_a_locked_database_does_not_turn_a_provider_answer_into_a_failure(
    tmp_path: Path,
) -> None:
    # A long import commit holds SQLite's write lock past busy_timeout. The provider
    # answered (its quota is spent): the answer is returned, and the provider is
    # not counted as failing — the cache is a convenience, not part of the call.
    settings = Settings(
        data_dir=tmp_path,
        database_url=f"sqlite:///{tmp_path / 'books.db'}",
        sqlite_busy_timeout_ms=50,
    )
    upgrade(settings.database_url)
    engine = create_engine(settings)
    inner = _Answering()
    observations = ProviderObservations()
    provider = ObservedProvider(inner, observations, cache=ResponseCache(engine))

    holder = sqlite3.connect(tmp_path / "books.db", isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    try:
        found = await search_providers("dune herbert", [provider])
    finally:
        holder.rollback()
        holder.close()
    assert [candidate.title for candidate in found] == ["Dune"]
    assert inner.searches == 1
    assert observations.state("openlibrary") == "working"
    assert observations.totals()["openlibrary"][1] == 0


def _record_fsyncs(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Every path `os.fsync` is called on, resolved from its descriptor."""
    synced: list[Path] = []
    real = os.fsync

    def recording(fd: int) -> None:
        synced.append(Path(os.readlink(f"/proc/self/fd/{fd}")))
        real(fd)

    monkeypatch.setattr(os, "fsync", recording)
    return synced


def test_an_attachment_blob_and_its_directory_reach_the_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    synced = _record_fsyncs(monkeypatch)
    stored = store_blob(b"epub bytes", tmp_path)
    target = blob_path(tmp_path, stored.sha256)
    # The bytes before the rename, and the directory after it: on power loss the
    # row the database commits next never outlives a zero-length blob.
    assert any(path.parent == tmp_path / "attachments" for path in synced)
    assert target.parent in synced


@pytest.mark.parametrize("damaged", [b"", b"X" * len(b"epub bytes")])
def test_a_damaged_blob_is_repaired_when_the_same_bytes_arrive_again(
    tmp_path: Path, damaged: bytes
) -> None:
    # A blob left empty (power loss before the data reached the disk) or rotten
    # under its digest must not be "deduplicated" forever: the store keeps the
    # bytes the digest names.
    digest = hashlib.sha256(b"epub bytes").hexdigest()
    target = blob_path(tmp_path, digest)
    target.parent.mkdir(parents=True)
    target.write_bytes(damaged)

    stored = store_blob(b"epub bytes", tmp_path)

    assert stored.sha256 == digest
    assert stored.byte_size == len(b"epub bytes")
    assert target.read_bytes() == b"epub bytes"
    assert [path.name for path in (tmp_path / "attachments").rglob("*.tmp")] == []


def test_an_installed_cover_and_its_directory_reach_the_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = tmp_path / "covers" / "upload-1.jpg.tmp"
    prepared.parent.mkdir(parents=True)
    prepared.write_bytes(b"jpeg bytes")
    synced = _record_fsyncs(monkeypatch)

    target = install_cover(prepared, tmp_path, 7)

    assert target.read_bytes() == b"jpeg bytes"
    assert prepared in synced
    assert tmp_path / "covers" in synced


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url)
    value = create_engine(configured)
    yield value
    value.dispose()


def test_a_cancelled_job_stays_cancelled_when_its_handler_finishes(engine: Engine) -> None:
    # Undo cancels a batch's jobs while one is running; the handler that was already
    # in flight finishing must not resurrect it as succeeded, failed or queued.
    repo = JobRepository(engine)
    now = datetime.now(UTC)
    finishing = [
        lambda job_id: repo.complete(job_id, {"filled": ["year"]}, now),
        lambda job_id: repo.fail(job_id, "provider down", now),
        lambda job_id: repo.defer(job_id, now + timedelta(days=1), reason="quota"),
    ]
    for finish in finishing:
        job_id = repo.enqueue(None, "enrich_item", {"item_id": 5})
        assert repo.claim(datetime.now(UTC)) is not None
        repo.cancel(job_id)
        finish(job_id)
        job = repo.get_job(job_id)
        assert job is not None
        assert job["state"] == "cancelled"
        assert job["attempts"] == 0


def test_a_job_whose_lease_keeps_expiring_is_dead_lettered(engine: Engine) -> None:
    # A job that kills the process every time it runs (its lease expires, it is
    # reclaimed, claimed, and kills it again) must stop after max_retries.
    repo = JobRepository(engine)
    job_id = repo.enqueue(None, "enrich_item", {"item_id": 5})
    now = datetime.now(UTC)
    for attempt in range(1, 4):
        assert repo.claim(now) is not None
        now += timedelta(minutes=10)
        assert repo.reclaim_expired(now, max_retries=3) == [job_id]
        job = repo.get_job(job_id)
        assert job is not None
        assert job["attempts"] == attempt
    assert job["state"] == "failed"
    assert job["error_code"] == "lease_expired"
    assert job["finished_at"] is not None
    assert repo.claim(now) is None


def _expire_undo_window(engine: Engine, batch_id: str) -> None:
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE import_batches SET undo_expires_at = :past WHERE id = :id"),
            {"past": past, "id": batch_id},
        )


async def _commit_killed_before_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client: httpx.AsyncClient
) -> str:
    """A Calibre export (a cover and an ebook) committed by a process that died
    the moment the database work landed: no staged file was installed."""
    from test_calibre_import import _export_files, build_calibre_export

    parts = build_calibre_export(tmp_path / "export")
    preview = await client.post("/api/import/calibre/preview", files=_export_files(parts))
    assert preview.status_code == 201, preview.text
    batch_id = str(preview.json()["batch_id"])
    with monkeypatch.context() as killed:
        killed.setattr(ImportService, "install_staged", lambda *_args, **_kwargs: None)
        committed = await client.post("/api/import/calibre/commit", json={"batch_id": batch_id})
    assert committed.status_code == 200, committed.text
    return batch_id


def _files_of(engine: Engine) -> tuple[str | None, list[str]]:
    with engine.connect() as connection:
        cover = connection.scalar(text("SELECT cover_path FROM items"))
        names = list(connection.scalars(text("SELECT filename FROM attachments")))
    return cover, names


@pytest.mark.anyio
async def test_a_commit_killed_before_its_files_were_installed_resumes_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_calibre_import import _no_mount_app

    app: Any = _no_mount_app(tmp_path)
    data_dir = tmp_path / "data"
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        app.state.job_runner.stop()
        engine = app.state.engine
        batch_id = await _commit_killed_before_install(tmp_path, monkeypatch, client)
        assert _files_of(engine) == (None, [])
        assert unconsumed_stage_files(engine, data_dir, batch_id)

        # What the next start does: the committed batch's staged files are installed.
        assert resume_interrupted_installs(engine, data_dir) == (batch_id,)
        cover, names = _files_of(engine)
        assert cover is not None and (data_dir / cover).is_file()
        assert names == ["Mistborn.epub"]
        assert unconsumed_stage_files(engine, data_dir, batch_id) == []
        # Idempotent: nothing left to resume, nothing installed twice.
        assert resume_interrupted_installs(engine, data_dir) == ()
        assert _files_of(engine)[1] == ["Mistborn.epub"]

        _expire_undo_window(engine, batch_id)
        assert reclaim_import_batches(engine, data_dir).reclaimed == (batch_id,)


@pytest.mark.anyio
async def test_the_job_runner_resumes_an_interrupted_install_when_it_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_calibre_import import _no_mount_app

    app: Any = _no_mount_app(tmp_path)
    data_dir = tmp_path / "data"
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        app.state.job_runner.stop()
        engine = app.state.engine
        await _commit_killed_before_install(tmp_path, monkeypatch, client)

        # The next process's runner: the first thing it does is finish the install.
        runner = JobRunner(engine, {}, poll_interval=0.01, data_dir=data_dir)
        worker = asyncio.create_task(runner.run_forever())
        for _ in range(500):
            if _files_of(engine)[1]:
                break
            await asyncio.sleep(0.01)
        runner.stop()
        await worker
        assert _files_of(engine)[1] == ["Mistborn.epub"]


@pytest.mark.anyio
async def test_a_batch_folder_holding_uninstalled_files_is_never_reclaimed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_calibre_import import _no_mount_app

    app: Any = _no_mount_app(tmp_path)
    data_dir = tmp_path / "data"
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        app.state.job_runner.stop()
        engine = app.state.engine
        batch_id = await _commit_killed_before_install(tmp_path, monkeypatch, client)
        _expire_undo_window(engine, batch_id)
        staging = data_dir / "imports" / batch_id

        def broken(_batch_id: str) -> None:
            raise OSError("disk unavailable")

        report = reclaim_import_batches(engine, data_dir, resume=broken)
        assert report.reclaimed == ()
        assert report.kept == (batch_id,)
        assert staging.is_dir()

        # With an install that works, the sweep finishes the commit, then collects.
        report = reclaim_import_batches(
            engine, data_dir, resume=lambda batch: resume_staged_install(engine, data_dir, batch)
        )
        assert report.reclaimed == (batch_id,)
        assert _files_of(engine)[1] == ["Mistborn.epub"]
        assert not staging.exists()


@pytest.mark.anyio
async def test_a_kept_batch_is_retried_and_logged_at_most_once_an_hour(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The runner sweeps every idle second; a batch whose install keeps failing
    must not be retried (and logged) every second with it."""
    from test_calibre_import import _no_mount_app

    app: Any = _no_mount_app(tmp_path)
    data_dir = tmp_path / "data"
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        app.state.job_runner.stop()
        engine = app.state.engine
        batch_id = await _commit_killed_before_install(tmp_path, monkeypatch, client)
        _expire_undo_window(engine, batch_id)
        attempts: list[str] = []

        def broken(batch: str) -> None:
            attempts.append(batch)
            raise OSError("disk unavailable")

        retries: dict[str, float] = {}
        clock = [1000.0]
        for _ in range(5):
            report = reclaim_import_batches(
                engine, data_dir, resume=broken, retries=retries, clock=lambda: clock[0]
            )
            assert report.kept == (batch_id,)
            clock[0] += 1
        assert attempts == [batch_id]
        clock[0] += 3600
        reclaim_import_batches(
            engine, data_dir, resume=broken, retries=retries, clock=lambda: clock[0]
        )
        assert attempts == [batch_id, batch_id]
        kept_lines = [r for r in caplog.records if "import staging kept" in r.getMessage()]
        assert len(kept_lines) == 2
