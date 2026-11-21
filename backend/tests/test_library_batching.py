"""Entries are hydrated in batches, not one at a time (Sprint 129, performance).

A library page used to cost about seven queries per entry (the item, the domain's
item again, the open loan, identifiers, sources, shelves, formats), and the Diary
opened a session per finished entry. `_entry_dicts` loads each of those for the
whole set with `IN (...)` queries. These tests hold two things: the batched payload
is exactly what the per-entry path builds, and a page's query count does not grow
with its size.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, event, select, text
from sqlalchemy.orm import Session

import book_tracker.application.library as library_module
from book_tracker.application.library import LibraryService
from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.domain.identity import Identifier
from book_tracker.infrastructure.models import EntryRow
from book_tracker.infrastructure.repositories import DomainRepository, SourceIdentity
from book_tracker.migrations import upgrade


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    settings = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert settings.database_url is not None
    upgrade(settings.database_url)
    value = create_engine(settings)
    yield value
    value.dispose()


@contextmanager
def counted(engine: Engine) -> Iterator[list[str]]:
    statements: list[str] = []

    def record(_conn, _cursor, statement, _params, _context, _many) -> None:  # type: ignore[no-untyped-def]
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", record)


def _seed(engine: Engine, count: int) -> list[int]:
    """A mixed library: every domain, loans out and returned, shelves whose names
    sort differently by case, formats, several identifiers and sources, legacy
    `publishers` metadata, covers, progress marks and remembered-unknown fields."""
    repository = DomainRepository(engine, 1)
    library = LibraryService(engine, 1)
    types = ["book", "album", "anime", "movie", "series"]
    statuses = {
        "book": "read",
        "album": "owned",
        "anime": "completed",
        "movie": "watched",
        "series": "watching",
    }
    formats = {
        "book": ["digital", "physical"],
        "album": ["cd", "vinyl"],
        "anime": ["bluray"],
        "movie": ["dvd", "streaming"],
        "series": [],
    }
    shelves = [library.create_shelf(name)["id"] for name in ("beta", "Alpha", "gamma", "Delta")]
    ids: list[int] = []
    for index in range(count):
        item_type = types[index % len(types)]
        identifiers = []
        sources = []
        if index % 2 == 0:
            identifiers = [
                Identifier("isbn13", f"97800000{index:05d}", f"97800000{index:05d}"),
                Identifier("isbn10", f"00000{index:05d}", f"00000{index:05d}"),
            ]
        if index % 3 == 0:
            sources = [
                SourceIdentity("openlibrary", f"OL{index}M", True),
                SourceIdentity("googlebooks", f"g{index}", False),
            ]
        created = repository.create_or_get_entry(
            # Every twentieth shares a title, creator and domain: duplicate pairs.
            title=f"Title {index % 20}",
            creators=[f"Creator {index % 4}"],
            item_type=item_type,
            identifiers=identifiers,
            sources=sources,
        )
        ids.append(created.entry_id)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE entries SET status = :status, score = :score,"
                    " date_finished = :finished, progress_marks = :marks,"
                    " unknown_fields = :unknown, location = :location WHERE id = :id"
                ),
                {
                    "status": statuses[item_type] if index % 9 else "unsorted",
                    "score": None if index % 4 == 0 else 1 + index % 10,
                    "finished": f"2026-0{1 + index % 9}-1{index % 10}" if index % 5 else None,
                    "marks": '[{"at": 3}]' if index % 6 == 0 else None,
                    "unknown": '["date_finished"]' if index % 7 == 0 else None,
                    "location": "Hall" if index % 2 else None,
                    "id": created.entry_id,
                },
            )
            metadata = (
                '{"publishers": ["  ", "Anagrama"], "credit": null, "pages": 120}'
                if index % 4 == 1
                else '{"credit": "Someone & Other", "publisher": "Seix"}'
            )
            connection.execute(
                text(
                    "UPDATE items SET metadata = :metadata, cover_path = :cover,"
                    " year = :year WHERE id = :id"
                ),
                {
                    "metadata": metadata,
                    "cover": f"covers/{created.item_id}.jpg" if index % 3 else None,
                    "year": 1990 + index,
                    "id": created.item_id,
                },
            )
        if formats[item_type]:
            library.update_entry(created.entry_id, {"formats": formats[item_type][::-1]})
        library.update_entry(
            created.entry_id,
            {"shelf_ids": shelves[index % 3 : index % 3 + 1 + index % 4]},
        )
        if index % 4 == 2:
            library.lend(created.entry_id, {"person": "Ana", "lent_on": "2026-01-01"})
        if index % 4 == 3:
            library.lend(
                created.entry_id,
                {"person": "Luis", "lent_on": "2025-01-01", "returned_on": "2025-02-01"},
            )
    return ids


def test_batched_entries_equal_the_per_entry_payload(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(engine, 23)
    # A tiny chunk size runs the IN-list chunking on a small fixture.
    monkeypatch.setattr(library_module, "_IN_CHUNK", 4)
    for requires_entry in (False, True):
        library = LibraryService(engine, 1, item_access_requires_entry=requires_entry)
        with Session(engine) as session:
            entries = list(session.scalars(select(EntryRow).order_by(EntryRow.id.desc())))
            expected = [library._entry_dict(session, entry) for entry in entries]
            assert library._entry_dicts(session, entries) == expected
            # Key order too: the JSON a client reads is the same document.
            assert [list(row) for row in library._entry_dicts(session, entries)] == [
                list(row) for row in expected
            ]
            assert library._entry_dicts(session, []) == []
    assert any(row["loan"] for row in expected)
    assert any(len(row["shelves"]) > 1 for row in expected)
    assert any(len(row["item"]["identifiers"]) > 1 for row in expected)
    assert any(len(row["item"]["sources"]) > 1 for row in expected)
    assert len({row["item"]["type"] for row in expected}) == 5


def test_a_library_page_costs_the_same_queries_whatever_its_size(engine: Engine) -> None:
    _seed(engine, 30)
    library = LibraryService(engine, 1)
    counts = {}
    for limit in (2, 25):
        with counted(engine) as statements:
            page = library.list_entries(limit=limit)
        assert len(page["items"]) == limit
        counts[limit] = len(statements)
    assert counts[2] == counts[25]
    assert counts[25] <= 15


@pytest.mark.parametrize(
    "call",
    [
        lambda library: library.diary(2026),
        lambda library: library.gaps(),
        lambda library: library.timeline(),
        lambda library: library.now(),
        lambda library: library.year_review(2026),
        lambda library: library.loans(),
        lambda library: library.search_entries("title"),
        lambda library: library.duplicate_candidates(),
    ],
    ids=["diary", "gaps", "timeline", "now", "year_review", "loans", "search", "duplicates"],
)
def test_multi_entry_reads_do_not_query_per_entry(engine: Engine, call) -> None:  # type: ignore[no-untyped-def]
    _seed(engine, 30)
    library = LibraryService(engine, 1)
    with counted(engine) as statements:
        result = call(library)
    assert result
    assert len(statements) <= 15, statements


def test_the_fixture_reaches_every_batched_reader(engine: Engine) -> None:
    """The bounds above are only evidence if each call returns entries."""
    _seed(engine, 30)
    library = LibraryService(engine, 1)
    assert library.duplicate_candidates()
    assert library.loans()
    assert library.gaps()["entries"]
    assert library.timeline()["events"]
    assert any(month["entries"] for month in library.diary(2026)["months"])
    assert library.year_review(2026)["best"]
    assert library.now()
    assert library.search_entries("title")


FACET_FILTERS: list[dict[str, Any]] = [
    {},
    {"statuses": ["read", "unsorted"]},
    {"shelves": ["alpha"]},
    {"shelves": ["alpha", "beta"]},
    {"formats": ["digital"]},
    {"types": ["book", "movie"]},
    {"q": "title 1"},
    {"location": "Hall"},
    {"lent": True},
    {"missing_cover": True},
    {"exact_score": 5},
    {"shelves": ["beta"], "formats": ["cd"], "types": ["album"], "statuses": ["owned"]},
]


@pytest.mark.parametrize("filters", FACET_FILTERS, ids=lambda filters: ",".join(filters) or "none")
def test_the_total_and_facets_count_what_the_filters_list(
    engine: Engine, filters: dict[str, Any]
) -> None:
    """Each count, recomputed from the entries the same filters list (Sprint 129
    rewrote the facet queries; this pins what they mean, not how they are spelled)."""
    _seed(engine, 40)
    library = LibraryService(engine, 1)
    page = library.list_entries(limit=1, **filters)

    every = {key: value for key, value in filters.items()}
    listed = library.list_entries(limit=1000, **every)["items"]
    assert page["total"] == len(listed)

    # Statuses and types cleared, the rest kept: what clicking a tab would show.
    cleared = {k: v for k, v in filters.items() if k not in ("statuses", "types")}
    by_type: dict[str, dict[str, int]] = {}
    for entry in library.list_entries(limit=1000, statuses=[], **cleared)["items"]:
        counts = by_type.setdefault(entry["item"]["type"], {})
        counts[entry["status"]] = counts.get(entry["status"], 0) + 1
    status_counts: dict[str, int] = {}
    for counts in by_type.values():
        for status, count in counts.items():
            status_counts[status] = status_counts.get(status, 0) + count
    assert page["facets"]["status_counts_by_type"] == by_type
    assert page["facets"]["status_counts"] == status_counts

    # Formats cleared, the rest (types included) kept.
    without_formats = {k: v for k, v in filters.items() if k != "formats"}
    format_counts: dict[str, int] = {}
    for entry in library.list_entries(limit=1000, **without_formats)["items"]:
        for value in entry["formats"]:
            format_counts[value] = format_counts.get(value, 0) + 1
    assert page["facets"]["format_counts"] == format_counts
