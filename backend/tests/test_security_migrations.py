"""A failed upgrade leaves the library exactly where it was (Sprint 129).

pysqlite emits no `BEGIN` before DDL, so before Sprint 129 every CREATE, DROP and
ALTER a migration ran committed on its own while the DML around it rolled back.
0034 failing after it had created `_attachments_owned` left the database at 0033
with that table in it, and every restart then failed on "table already exists":
`restart: unless-stopped` turned one disk-full moment into a restart loop that no
retry could leave. The whole upgrade now runs in one real transaction.

The pre-migration backup is reused across such a loop only while it still holds
what the live database holds; a library that changed since (restored and used for
weeks on the old image) gets a fresh rollback point.
"""

import sqlite3
from pathlib import Path

import pytest
from alembic.operations import Operations

from book_tracker.config import Settings
from book_tracker.migrations import upgrade

BEFORE_OWNERS = "0033_unknown_fields"
TWO_BEFORE_OWNERS = "0032_shelf_suggestion_dismissals"


class DiskFull(sqlite3.OperationalError):
    pass


def _settings(tmp_path: Path) -> Settings:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        data_dir=data_dir,
        backup_dir=tmp_path / "backups",
        user_agent_contact="test@example.invalid",
    )


def _url(configured: Settings) -> str:
    assert configured.database_url is not None
    return configured.database_url


def _schema(database: Path) -> list[tuple[str, str, str | None]]:
    connection = sqlite3.connect(database)
    try:
        return connection.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall()
    finally:
        connection.close()


def _revision(database: Path) -> str:
    connection = sqlite3.connect(database)
    try:
        return str(connection.execute("SELECT version_num FROM alembic_version").fetchone()[0])
    finally:
        connection.close()


def _seed_attachment(database: Path) -> None:
    connection = sqlite3.connect(database)
    connection.execute(
        "INSERT INTO attachments (item_id, filename, byte_size, sha256, created_at, updated_at) "
        "VALUES (1, 'notes.pdf', 3, 'abc', 'n', 'n')"
    )
    connection.commit()
    connection.close()


def _attachment_rows(database: Path) -> list[tuple[object, ...]]:
    connection = sqlite3.connect(database)
    try:
        return connection.execute("SELECT item_id, filename, sha256 FROM attachments").fetchall()
    finally:
        connection.close()


def test_0034_failing_after_its_create_table_leaves_0033_and_a_retry_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = _settings(tmp_path)
    database = configured.data_dir / "books.db"
    upgrade(_url(configured), BEFORE_OWNERS)
    _seed_attachment(database)
    before = _schema(database)

    def disk_full(self: Operations, *args: object, **kwargs: object) -> None:
        raise DiskFull("database or disk is full")

    with monkeypatch.context() as patch:
        patch.setattr(Operations, "execute", disk_full)
        with pytest.raises(DiskFull):
            upgrade(_url(configured))

    assert _revision(database) == BEFORE_OWNERS
    assert _schema(database) == before
    assert "_attachments_owned" not in {name for _, name, _ in _schema(database)}

    upgrade(_url(configured))
    connection = sqlite3.connect(database)
    columns = [row[1] for row in connection.execute("PRAGMA table_info(attachments)")]
    connection.close()
    assert "user_id" in columns
    assert _attachment_rows(database) == [(1, "notes.pdf", "abc")]


def test_a_failure_after_the_table_swap_restores_the_old_table_and_its_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DROP TABLE, ALTER TABLE RENAME and an INSERT…SELECT all undone together."""
    configured = _settings(tmp_path)
    database = configured.data_dir / "books.db"
    upgrade(_url(configured), BEFORE_OWNERS)
    _seed_attachment(database)
    before = _schema(database)

    original = Operations.create_index

    def fail_on_the_second_index(self: Operations, name: str, *args: object, **kw: object) -> None:
        if name == "ix_attachments_sha256":
            raise DiskFull("database or disk is full")
        original(self, name, *args, **kw)  # type: ignore[arg-type]

    with monkeypatch.context() as patch:
        patch.setattr(Operations, "create_index", fail_on_the_second_index)
        with pytest.raises(DiskFull):
            upgrade(_url(configured))

    assert _revision(database) == BEFORE_OWNERS
    assert _schema(database) == before
    assert _attachment_rows(database) == [(1, "notes.pdf", "abc")]


def test_a_multi_revision_upgrade_is_one_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pre-migration backup is the rollback point, so a failure returns to it whole."""
    configured = _settings(tmp_path)
    database = configured.data_dir / "books.db"
    upgrade(_url(configured), TWO_BEFORE_OWNERS)
    before = _schema(database)

    def disk_full(self: Operations, *args: object, **kwargs: object) -> None:
        raise DiskFull("database or disk is full")

    with monkeypatch.context() as patch:
        patch.setattr(Operations, "execute", disk_full)
        with pytest.raises(DiskFull):
            upgrade(_url(configured))

    assert _revision(database) == TWO_BEFORE_OWNERS
    assert _schema(database) == before


def test_migrations_still_run_with_foreign_keys_off(tmp_path: Path) -> None:
    """DEC-092: the rebuilds in 0014-0016 drop parent tables; with the pragma on,
    that DROP would cascade children away. Inside a transaction SQLite ignores a
    change to the pragma, so it must already be off when the transaction begins."""
    configured = _settings(tmp_path)
    upgrade(_url(configured))
    connection = sqlite3.connect(configured.data_dir / "books.db")
    try:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()
