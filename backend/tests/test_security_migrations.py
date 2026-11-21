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

import json
import shutil
import sqlite3
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.operations import Operations

import book_tracker.app.lifespan as lifespan
from book_tracker.app.lifespan import back_up_before_migrating
from book_tracker.backup import read_manifest, restore_backup
from book_tracker.config import Settings
from book_tracker.migrations import upgrade

BEFORE_OWNERS = "0033_unknown_fields"
TWO_BEFORE_OWNERS = "0032_shelf_suggestion_dismissals"


@pytest.fixture(autouse=True)
def distinct_backup_names(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Backups are named by the second; a test taking two in one gets two names."""
    original = lifespan.create_backup
    clock = [datetime.now(UTC)]

    def create_backup(**kwargs: object) -> object:
        clock[0] += timedelta(seconds=1)
        return original(**kwargs, now=clock[0])  # type: ignore[arg-type]

    monkeypatch.setattr(lifespan, "create_backup", create_backup)
    yield


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


def test_a_start_with_nothing_pending_does_not_need_the_write_lock(tmp_path: Path) -> None:
    """Every start runs the upgrade; at head it only reads, so a writer elsewhere
    (a backup, the CLI) must not stall it."""
    configured = _settings(tmp_path)
    upgrade(_url(configured))
    holder = sqlite3.connect(configured.data_dir / "books.db", isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    try:
        started = time.monotonic()
        upgrade(_url(configured))
        assert time.monotonic() - started < 2.0
    finally:
        holder.execute("ROLLBACK")
        holder.close()


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


# --- pre-migration backup reuse -------------------------------------------------


def _pre_migration_backups(configured: Settings) -> list[Path]:
    assert configured.backup_dir is not None
    return sorted(configured.backup_dir.glob("pre-migration-*"))


def _add_shelves(database: Path, count: int) -> None:
    connection = sqlite3.connect(database)
    for index in range(count):
        connection.execute(
            "INSERT INTO shelves (user_id, name, slug, created_at, updated_at) "
            "VALUES (1, ?, ?, 'n', 'n')",
            (f"shelf {index}", f"shelf-{index}"),
        )
    connection.commit()
    connection.close()


def _shelves(database: Path) -> int:
    connection = sqlite3.connect(database)
    try:
        return int(connection.execute("SELECT count(*) FROM shelves").fetchone()[0])
    finally:
        connection.close()


def test_a_library_changed_since_the_last_attempt_gets_a_fresh_rollback_point(
    tmp_path: Path,
) -> None:
    """Failed upgrade, restore, weeks on the old image, then the upgrade again: the
    backup from the first attempt no longer holds the library and must not be the
    only rollback point."""
    configured = _settings(tmp_path)
    database = configured.data_dir / "books.db"
    upgrade(_url(configured), BEFORE_OWNERS)
    back_up_before_migrating(configured)
    [first] = _pre_migration_backups(configured)

    _add_shelves(database, 50)
    live = _shelves(database)
    back_up_before_migrating(configured)

    backups = _pre_migration_backups(configured)
    assert len(backups) == 2
    newest = max(backups, key=lambda path: str((read_manifest(path) or {})["created_at"]))
    assert newest != first
    assert _shelves(newest / "books.db") == live


def test_a_real_failed_attempt_still_reuses_the_first_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The restart loop: back up, fail, restart. The failed attempt touched the file
    but changed nothing in it, so the first copy is still the rollback point."""
    configured = _settings(tmp_path)
    database = configured.data_dir / "books.db"
    upgrade(_url(configured), BEFORE_OWNERS)
    _add_shelves(database, 3)

    def disk_full(self: Operations, *args: object, **kwargs: object) -> None:
        raise DiskFull("database or disk is full")

    for _ in range(3):
        back_up_before_migrating(configured)
        with monkeypatch.context() as patch:
            patch.setattr(Operations, "execute", disk_full)
            with pytest.raises(DiskFull):
                upgrade(_url(configured))

    assert len(_pre_migration_backups(configured)) == 1


def test_restoring_the_rollback_point_and_retrying_reuses_it(tmp_path: Path) -> None:
    configured = _settings(tmp_path)
    database = configured.data_dir / "books.db"
    upgrade(_url(configured), BEFORE_OWNERS)
    _add_shelves(database, 2)
    back_up_before_migrating(configured)
    [first] = _pre_migration_backups(configured)

    # The runbook's rollback: restore the copy and put its database back in place.
    restored = tmp_path / "restored"
    restore_backup(first, into=restored)
    for suffix in ("-wal", "-shm"):
        Path(f"{database}{suffix}").unlink(missing_ok=True)
    shutil.copyfile(restored / "books.db", database)
    back_up_before_migrating(configured)

    assert _pre_migration_backups(configured) == [first]


def test_a_backup_from_before_the_digest_is_not_trusted(tmp_path: Path) -> None:
    """A manifest written by an older image says nothing about what it holds."""

    configured = _settings(tmp_path)
    upgrade(_url(configured), BEFORE_OWNERS)
    back_up_before_migrating(configured)
    [first] = _pre_migration_backups(configured)
    manifest_path = first / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.pop("database_digest", None)
    manifest_path.write_text(json.dumps(manifest))

    back_up_before_migrating(configured)

    assert len(_pre_migration_backups(configured)) == 2
