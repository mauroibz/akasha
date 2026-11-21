"""Robustness follow-ups (Sprint 129): failures that are not the provider's, kept off it."""

import hashlib
import os
import sqlite3
from pathlib import Path

import pytest

from book_tracker.application.providers import search_providers
from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.domain.providers import SearchCandidate, SourceRef
from book_tracker.infrastructure.attachments import blob_path, store_blob
from book_tracker.infrastructure.covers import install_cover
from book_tracker.infrastructure.observed import (
    ObservedProvider,
    ProviderObservations,
    ResponseCache,
)
from book_tracker.migrations import upgrade


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
