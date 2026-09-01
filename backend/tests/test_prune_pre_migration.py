"""Sprint 060, deliverable 3: an explicit, never-automatic prune for pre-migration
backups.

DEC-039's guarantee is that a `pre-migration` backup survives until an operator
decides otherwise — nightly retention is scoped by label precisely so that it never
touches one (`test_backup.py` already proves that). This file proves the new prune
command upholds the same guarantee from the other side: it deletes only backups an
operator names, and refuses the two DEC-039 must protect even when named.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from book_tracker.backup import (
    enforce_retention,
    list_pre_migration_backups,
    main,
    prune_pre_migration,
)


def _fake_pre_migration_backup(dest: Path, *, day: int, revision: str) -> Path:
    created_at = datetime(2026, 8, 1, tzinfo=UTC) + timedelta(days=day)
    path = dest / f"pre-migration-{created_at.strftime('%Y%m%dT%H%M%SZ')}"
    path.mkdir(parents=True)
    (path / "manifest.json").write_text(
        json.dumps(
            {
                "kind": "akasha-backup",
                "version": 1,
                "label": "pre-migration",
                "created_at": created_at.isoformat(),
                "alembic_revision": revision,
            }
        ),
        encoding="utf-8",
    )
    (path / "books.db").write_bytes(b"stand-in bytes, only the manifest matters here")
    return path


def test_listing_names_revision_age_and_size_without_deleting_anything(tmp_path: Path) -> None:
    dest = tmp_path / "backups"
    old = _fake_pre_migration_backup(dest, day=0, revision="0007")
    new = _fake_pre_migration_backup(dest, day=5, revision="0009")

    backups = list_pre_migration_backups(dest)

    assert [backup.name for backup in backups] == [new.name, old.name]  # newest first
    assert backups[0].revision == "0009"
    assert backups[0].bytes > 0
    assert old.is_dir() and new.is_dir()


def test_no_names_given_deletes_nothing(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    dest = tmp_path / "backups"
    backup = _fake_pre_migration_backup(dest, day=0, revision="0007")

    assert main(["prune-pre-migration", "--dest", str(dest), "--data-dir", str(tmp_path)]) == 0

    assert backup.is_dir()
    assert "nothing deleted" in capsys.readouterr().out


def test_a_named_backup_is_refused_without_apply(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    dest = tmp_path / "backups"
    # Two backups, so the older one is not also "newest".
    _fake_pre_migration_backup(dest, day=5, revision="0009")
    old = _fake_pre_migration_backup(dest, day=0, revision="0007")

    report = prune_pre_migration(dest, [old.name], apply=False, current_revision="0009")

    assert report.applied is False
    assert report.deleted == (old.name,)
    assert old.is_dir()  # a dry run never touches the filesystem


def test_applying_actually_deletes_the_named_backup(tmp_path: Path) -> None:
    dest = tmp_path / "backups"
    _fake_pre_migration_backup(dest, day=5, revision="0009")
    old = _fake_pre_migration_backup(dest, day=0, revision="0007")

    report = prune_pre_migration(dest, [old.name], apply=True, current_revision="0009")

    assert report.deleted == (old.name,)
    assert not old.exists()


def test_the_newest_backup_is_refused_even_when_named(tmp_path: Path) -> None:
    dest = tmp_path / "backups"
    newest = _fake_pre_migration_backup(dest, day=5, revision="0009")
    _fake_pre_migration_backup(dest, day=0, revision="0007")

    report = prune_pre_migration(dest, [newest.name], apply=True, current_revision=None)

    assert report.deleted == ()
    assert report.kept == ((newest.name, "newest pre-migration backup"),)
    assert newest.is_dir()


def test_the_current_schema_revision_is_refused_even_when_named(tmp_path: Path) -> None:
    dest = tmp_path / "backups"
    _fake_pre_migration_backup(dest, day=5, revision="0009")
    matches_current = _fake_pre_migration_backup(dest, day=0, revision="0007")

    report = prune_pre_migration(dest, [matches_current.name], apply=True, current_revision="0007")

    assert report.deleted == ()
    assert report.kept == ((matches_current.name, "matches the current schema revision (0007)"),)
    assert matches_current.is_dir()


def test_an_unknown_name_is_reported_and_nothing_else_is_touched(tmp_path: Path) -> None:
    dest = tmp_path / "backups"
    kept = _fake_pre_migration_backup(dest, day=0, revision="0007")

    report = prune_pre_migration(dest, ["not-a-real-backup"], apply=True, current_revision=None)

    assert report.not_found == ("not-a-real-backup",)
    assert report.deleted == ()
    assert kept.is_dir()


def test_nightly_retention_with_a_full_pre_migration_set_removes_none_of_them(
    tmp_path: Path,
) -> None:
    """AC6, restated against a realistic set rather than the single backup
    test_backup.py already covers."""
    dest = tmp_path / "backups"
    pre_migrations = [
        _fake_pre_migration_backup(dest, day=day, revision=f"000{day}") for day in range(5)
    ]

    deleted = enforce_retention(dest, keep=0, label="nightly")

    assert deleted == []
    assert all(backup.is_dir() for backup in pre_migrations)


def test_the_cli_reachable_only_by_explicit_invocation_never_from_create(
    tmp_path: Path, capsys
) -> None:  # type: ignore[no-untyped-def]
    """AC5's "reachable from no automatic path": `create_backup`'s own retention
    call in `main()`'s "create" command is always label="nightly" (test_backup.py
    covers the function directly); this is the CLI-level companion proving the
    prune subcommand itself does nothing unless invoked with names and --apply."""
    dest = tmp_path / "backups"
    backup = _fake_pre_migration_backup(dest, day=0, revision="0007")

    assert main(["prune-pre-migration", "--dest", str(dest), "--data-dir", str(tmp_path)]) == 0
    printed = capsys.readouterr().out
    assert backup.name in printed
    assert backup.is_dir()
