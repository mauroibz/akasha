"""What you are in the middle of, and what you finished (Sprint 098, proposal §7).

*Now* is every entry whose status its domain declares `in_progress` (a book being
read, a series or anime being watched), across every domain, most recently touched
first. The *Diary* is what you finished in a year, read from `date_finished`.
"""

from pathlib import Path

import pytest
from sqlalchemy import text

from book_tracker.application.library import LibraryService
from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.domain.registry import DOMAINS
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.migrations import upgrade


@pytest.fixture
def engine(tmp_path: Path):  # type: ignore[no-untyped-def]
    settings = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert settings.database_url is not None
    upgrade(settings.database_url)
    value = create_engine(settings)
    yield value
    value.dispose()


def _entry(engine, title: str, item_type: str, status: str, **values: object) -> int:  # type: ignore[no-untyped-def]
    created = DomainRepository(engine, 1).create_or_get_entry(title=title, item_type=item_type)
    assignments = ", ".join(["status=:status", *(f"{key}=:{key}" for key in values)])
    with engine.begin() as connection:
        connection.execute(
            text(f"UPDATE entries SET {assignments} WHERE id=:id"),
            {"status": status, "id": created.entry_id, **values},
        )
    return created.entry_id


def test_only_declared_in_progress_statuses_are_now(engine) -> None:  # type: ignore[no-untyped-def]
    declared = {
        (domain.item_type, status.value)
        for domain in DOMAINS.values()
        for status in domain.statuses
        if status.in_progress
    }
    assert ("book", "reading") in declared and ("anime", "watching") in declared
    reading = _entry(engine, "Rayuela", "book", "reading", updated_at="2026-10-01T00:00:00Z")
    watching = _entry(engine, "Frieren", "anime", "watching", updated_at="2026-10-05T00:00:00Z")
    _entry(engine, "Ficciones", "book", "read")
    _entry(engine, "Up", "movie", "watched")
    now = LibraryService(engine, 1).now()
    assert [row["id"] for row in now] == [watching, reading]


def test_the_diary_counts_a_year_by_month_and_domain(engine) -> None:  # type: ignore[no-untyped-def]
    _entry(engine, "Rayuela", "book", "read", date_finished="2026-03-02")
    _entry(engine, "Ficciones", "book", "read", date_finished="2026-03-20")
    _entry(engine, "Up", "movie", "watched", date_finished="2026-03-05")
    _entry(engine, "Kind of Blue", "album", "owned", date_finished="2026-07-01")
    _entry(engine, "Old", "book", "read", date_finished="2025-12-31")
    _entry(engine, "Undated", "book", "read")
    diary = LibraryService(engine, 1).diary(2026)
    assert diary["year"] == 2026
    assert diary["years"] == [2026, 2025]
    months = {month["month"]: month for month in diary["months"]}
    assert list(months) == ["2026-07", "2026-03"]
    assert months["2026-03"]["counts"] == {"book": 2, "movie": 1}
    assert [row["item"]["title"] for row in months["2026-03"]["entries"]] == [
        "Ficciones",
        "Up",
        "Rayuela",
    ]
