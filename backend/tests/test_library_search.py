"""Library search reaches every creator, series, subject and note (Sprint 089, proposal R4).

It used to be a substring `LIKE` over the title and the *first* creator, so a co-author,
a series name, a subject or a word from your own note found nothing. An FTS5 index over
those fields now sits beside the substring match, kept current by triggers.
"""

import json
from pathlib import Path

import pytest
from sqlalchemy import text

from alembic import command
from book_tracker.application.library import LibraryService
from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.migrations import alembic_config, upgrade


@pytest.fixture
def engine(tmp_path: Path):  # type: ignore[no-untyped-def]
    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url)
    value = create_engine(configured)
    yield value
    value.dispose()


def _book(engine, title: str, creators: tuple[str, ...], **metadata: object) -> int:  # type: ignore[no-untyped-def]
    entry = DomainRepository(engine, 1).create_or_get_entry(title=title, creators=creators)
    with engine.begin() as connection:  # out of the Inbox, which the library list excludes
        connection.execute(
            text("UPDATE entries SET status='read' WHERE id=:id"), {"id": entry.entry_id}
        )
    if metadata:
        with engine.begin() as connection:
            current = json.loads(
                connection.execute(
                    text("SELECT metadata FROM items WHERE id=:id"), {"id": entry.item_id}
                ).scalar_one()
            )
            connection.execute(
                text("UPDATE items SET metadata=:m WHERE id=:id"),
                {"m": json.dumps({**current, **metadata}), "id": entry.item_id},
            )
    return entry.entry_id


def _found(engine, query: str) -> set[str]:  # type: ignore[no-untyped-def]
    page = LibraryService(engine, 1).list_entries(q=query)
    return {row["item"]["title"] for row in page["items"]}


def test_a_secondary_creator_finds_the_book(engine) -> None:  # type: ignore[no-untyped-def]
    _book(engine, "Good Omens", ("Terry Pratchett", "Neil Gaiman"))
    _book(engine, "Mort", ("Terry Pratchett",))
    assert _found(engine, "gaiman") == {"Good Omens"}


def test_a_series_and_a_subject_find_the_book(engine) -> None:  # type: ignore[no-untyped-def]
    _book(engine, "Guards! Guards!", ("Terry Pratchett",), series="Discworld", subjects=["Dragons"])
    _book(engine, "Rayuela", ("Julio Cortázar",), subjects=["Buenos Aires"])
    assert _found(engine, "discworld") == {"Guards! Guards!"}
    assert _found(engine, "dragons") == {"Guards! Guards!"}


def test_a_word_from_your_note_finds_the_entry_and_follows_an_edit(engine) -> None:  # type: ignore[no-untyped-def]
    entry_id = _book(engine, "Rayuela", ("Julio Cortázar",))
    _book(engine, "Ficciones", ("Jorge Luis Borges",))
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE entries SET notes='Leído en el tren a Rosario' WHERE id=:id"),
            {"id": entry_id},
        )
    assert _found(engine, "rosario") == {"Rayuela"}
    with engine.begin() as connection:
        connection.execute(text("UPDATE entries SET notes=NULL WHERE id=:id"), {"id": entry_id})
    assert _found(engine, "rosario") == set()


def test_accents_and_case_are_ignored_and_words_match_as_prefixes(engine) -> None:  # type: ignore[no-untyped-def]
    _book(engine, "Bestiario", ("Julio Cortázar",), subjects=["Cuentos fantásticos"])
    assert _found(engine, "FANTASTIC") == {"Bestiario"}
    assert _found(engine, "cortazar bestia") == {"Bestiario"}


def test_the_old_substring_match_on_a_title_still_works(engine) -> None:  # type: ignore[no-untyped-def]
    _book(engine, "Rayuela", ("Julio Cortázar",))
    assert _found(engine, "ayuel") == {"Rayuela"}


def test_punctuation_alone_does_not_break_the_query(engine) -> None:  # type: ignore[no-untyped-def]
    _book(engine, "Rayuela", ("Julio Cortázar",))
    # Nothing searchable left: only the substring match applies, and an empty
    # fragment matches everything, exactly as before this sprint.
    assert _found(engine, '"*') == {"Rayuela"}
    # FTS5 syntax typed by a person is text, never an error.
    assert _found(engine, '(rayuela"*:') == {"Rayuela"}


def test_another_persons_note_is_not_searchable_by_you(engine) -> None:  # type: ignore[no-untyped-def]
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id,username,is_admin,created_at,updated_at) "
                "VALUES (2,'other',0,'n','n')"
            )
        )
    theirs = DomainRepository(engine, 2).create_or_get_entry(title="Rayuela", creators=())
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE entries SET notes='secreto', status='read' WHERE id=:id"),
            {"id": theirs.entry_id},
        )
    assert _found(engine, "secreto") == set()


def test_the_index_is_built_for_existing_rows_and_the_migration_reverses(tmp_path: Path) -> None:
    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    config = alembic_config(configured.database_url)
    # Seeded at head and taken down to the revision before the index, because the
    # repository writes through the current models: a column a later revision adds
    # (0027's `progress_marks`) does not exist at 0022. The rows survive the downgrade,
    # so the upgrade still has to build the index for rows already there.
    command.upgrade(config, "head")
    engine = create_engine(configured)
    try:
        _book(engine, "Good Omens", ("Terry Pratchett", "Neil Gaiman"))
        command.downgrade(config, "0022_import_proposals")
        command.upgrade(config, "head")
        assert _found(engine, "gaiman") == {"Good Omens"}
        command.downgrade(config, "0022_import_proposals")
        with engine.connect() as connection:
            tables = connection.execute(
                text("SELECT name FROM sqlite_master WHERE name LIKE 'entry_search%'")
            ).all()
        assert tables == []
    finally:
        engine.dispose()


def test_ranked_search_puts_a_title_match_before_a_note_match(engine) -> None:  # type: ignore[no-untyped-def]
    """Sprint 094: the command bar's library half, ranked (bm25, title weighted)."""
    noted = _book(engine, "Ficciones", ("Jorge Luis Borges",))
    _book(engine, "Rayuela", ("Julio Cortázar",))
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE entries SET notes='me recordó a Rayuela' WHERE id=:id"), {"id": noted}
        )
    ranked = LibraryService(engine, 1).search_entries("rayuela")
    assert [row["item"]["title"] for row in ranked] == ["Rayuela", "Ficciones"]


def test_ranked_search_includes_the_inbox_and_finds_a_title_fragment(engine) -> None:  # type: ignore[no-untyped-def]
    inbox = DomainRepository(engine, 1).create_or_get_entry(title="Bestiario", creators=())
    ranked = LibraryService(engine, 1).search_entries("stiar")
    assert [row["id"] for row in ranked] == [inbox.entry_id]
    assert LibraryService(engine, 1).search_entries('"*') == []
