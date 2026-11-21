"""Storage-level performance settings (Sprint 129).

Indexes for the joins the library runs on every page, `synchronous=NORMAL` under
WAL, a one-time `PRAGMA optimize`, and memoized text folding for the SQL UDFs.
"""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, event, text

from alembic import command
from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.domain import normalization
from book_tracker.migrations import alembic_config, upgrade

NEW_INDEXES = {
    "ix_entry_shelves_shelf": ("entry_shelves", ["shelf_id"]),
    "ix_entries_item": ("entries", ["item_id"]),
}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")


@pytest.fixture
def engine(settings: Settings) -> Iterator[Engine]:
    assert settings.database_url is not None
    upgrade(settings.database_url)
    value = create_engine(settings)
    yield value
    value.dispose()


def _indexes(engine: Engine) -> dict[str, tuple[str, list[str]]]:
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT name, tbl_name FROM sqlite_master WHERE type = 'index'")
        ).all()
        return {
            name: (
                table,
                [
                    column[2]
                    for column in connection.exec_driver_sql(f"PRAGMA index_info('{name}')")
                ],
            )
            for name, table in rows
        }


def test_the_joins_every_page_runs_have_their_indexes(engine: Engine) -> None:
    indexes = _indexes(engine)
    for name, shape in NEW_INDEXES.items():
        assert indexes.get(name) == shape
    with engine.connect() as connection:
        plan = " ".join(
            str(row[3])
            for row in connection.exec_driver_sql(
                "EXPLAIN QUERY PLAN SELECT entry_id FROM entry_shelves WHERE shelf_id = 1"
            )
        )
    assert "ix_entry_shelves_shelf" in plan


def test_the_index_revision_downgrades_cleanly(settings: Settings) -> None:
    assert settings.database_url is not None
    upgrade(settings.database_url)
    command.downgrade(alembic_config(settings.database_url), "0034_attachment_owners")
    engine = create_engine(settings)
    try:
        assert not set(NEW_INDEXES) & set(_indexes(engine))
    finally:
        engine.dispose()
    upgrade(settings.database_url)


def test_every_connection_writes_with_synchronous_normal_under_wal(engine: Engine) -> None:
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        # 1 is NORMAL: under WAL a power cut can lose the last commit, never corrupt.
        assert connection.exec_driver_sql("PRAGMA synchronous").scalar() == 1
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_the_engine_optimizes_once_not_per_connection(settings: Settings) -> None:
    assert settings.database_url is not None
    upgrade(settings.database_url)
    statements: list[str] = []
    engine = create_engine(settings)

    # Open each physical connection here so its statements are traced from the start.
    @event.listens_for(engine, "do_connect")
    def traced(_dialect, _record, cargs, cparams):  # type: ignore[no-untyped-def]
        connection = sqlite3.connect(*cargs, **cparams)
        connection.set_trace_callback(statements.append)
        return connection

    try:
        connections = [engine.connect() for _ in range(3)]
        for connection in connections:
            connection.close()
    finally:
        engine.dispose()
    assert sum("PRAGMA synchronous" in statement for statement in statements) == 3
    optimizes = [statement for statement in statements if "optimize" in statement.lower()]
    assert len(optimizes) == 1, statements


def test_text_folding_is_memoized_and_still_pure() -> None:
    for function in (normalization.normalize_text, normalization.insight_group):
        function.cache_clear()  # type: ignore[attr-defined]
        first = function("Fiction, General")
        assert function("Fiction, General") == first
        info = function.cache_info()  # type: ignore[attr-defined]
        assert info.hits >= 1
        assert info.maxsize is not None
    assert normalization.normalize_text("García Márquez") == "garcia marquez"
    assert normalization.insight_group("Fiction, general") == "fiction"
    assert normalization.work_key("Rayuela (Spanish Edition)") == "rayuela"
