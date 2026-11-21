"""Robustness follow-ups (Sprint 129): failures that are not the provider's, kept off it."""

import sqlite3
from pathlib import Path

import pytest

from book_tracker.application.providers import search_providers
from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.domain.providers import SearchCandidate, SourceRef
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
