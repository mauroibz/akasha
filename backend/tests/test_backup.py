"""The backup has to be restorable, so every test here reads something back.

A backup routine that reports success is worthless evidence; DEC-025 applies to
operations too. Each test either restores real values or proves that a damaged
artifact is refused.
"""

import json
import os
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from book_tracker.backup import (
    BackupError,
    create_backup,
    enforce_retention,
    restore_backup,
    verify_backup,
)
from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.infrastructure.attachments import blob_path, store_blob
from book_tracker.infrastructure.models import (
    EntryRow,
    EntryShelfRow,
    ItemRow,
    ShelfRow,
)
from book_tracker.migrations import upgrade

NOW = "2026-08-13T00:00:00+00:00"
COVER_BYTES = b"\xff\xd8\xff\xe0 not really a jpeg, but bytes that must survive"


def populated_data_dir(tmp_path: Path) -> Path:
    """A data directory holding what the owner would actually lose.

    A score, a note, a shelf and a cover: the things no provider can re-fetch.
    """
    data_dir = tmp_path / "data"
    for directory in ("", "covers", "imports"):
        (data_dir / directory).mkdir(parents=True, exist_ok=True)
    configured = Settings(data_dir=data_dir, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url)
    engine = create_engine(configured)
    with Session(engine) as session:
        item = ItemRow(
            type="book",
            title="Rayuela",
            subtitle=None,
            year=1963,
            cover_path="covers/1.jpg",
            identifiers="{}",
            metadata_json=json.dumps({"authors": ["Julio Cortázar"]}),
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(item)
        session.flush()
        entry = EntryRow(
            user_id=1,
            item_id=item.id,
            status="read",
            score=9,
            notes="The chapter order is the whole point.",
            date_added=NOW,
            date_started=None,
            date_finished=None,
            reread_count=0,
            score_provisional=0,
            suggested_status=None,
            created_at=NOW,
            updated_at=NOW,
        )
        shelf = ShelfRow(
            user_id=1, name="Argentina", slug="argentina", created_at=NOW, updated_at=NOW
        )
        session.add_all([entry, shelf])
        session.flush()
        session.add(EntryShelfRow(entry_id=entry.id, shelf_id=shelf.id))
        session.commit()
    engine.dispose()
    (data_dir / "covers" / "1.jpg").write_bytes(COVER_BYTES)
    (data_dir / "imports" / "batch-1").mkdir()
    (data_dir / "imports" / "batch-1" / "audit.json").write_text('{"rows": 1}', encoding="utf-8")
    return data_dir


def test_backup_copies_a_consistent_database_and_passes_integrity_check(tmp_path: Path) -> None:
    data_dir = populated_data_dir(tmp_path)

    result = create_backup(
        database_path=data_dir / "books.db",
        data_dir=data_dir,
        dest=tmp_path / "backups",
        label="nightly",
    )

    assert result.path.parent == tmp_path / "backups"
    assert (result.path / "books.db").is_file()
    assert (result.path / "covers.tar.gz").is_file()
    assert (result.path / "imports.tar.gz").is_file()
    # A live WAL database copied file-by-file can be torn; the online backup API
    # cannot be, and the copy carries no sidecar files at all.
    assert not list(result.path.glob("*.db-wal"))
    assert not list(result.path.glob("*.db-shm"))
    assert result.manifest["counts"] == {
        "items": 1,
        "entries": 1,
        "shelves": 1,
        "covers": 1,
        "attachments": 0,
    }
    assert result.manifest["alembic_revision"] == "0010_attachments"
    verify_backup(result.path)


def test_backup_taken_while_the_database_is_being_written_is_still_consistent(
    tmp_path: Path,
) -> None:
    """The nightly backup runs against a live instance, so an open writer is the normal case."""
    data_dir = populated_data_dir(tmp_path)
    writer = sqlite3.connect(data_dir / "books.db")
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute(
        "INSERT INTO shelves (user_id, name, slug, created_at, updated_at) VALUES (1,?,?,?,?)",
        ("Pendientes", "pendientes", NOW, NOW),
    )
    writer.commit()

    result = create_backup(
        database_path=data_dir / "books.db",
        data_dir=data_dir,
        dest=tmp_path / "backups",
        label="nightly",
    )
    writer.close()

    verify_backup(result.path)
    assert result.manifest["counts"]["shelves"] == 2


def test_verify_rejects_a_mutated_file(tmp_path: Path) -> None:
    data_dir = populated_data_dir(tmp_path)
    result = create_backup(
        database_path=data_dir / "books.db",
        data_dir=data_dir,
        dest=tmp_path / "backups",
        label="nightly",
    )

    (result.path / "covers.tar.gz").write_bytes(b"tampered")

    with pytest.raises(BackupError, match="checksum"):
        verify_backup(result.path)


def test_verify_rejects_a_corrupt_database(tmp_path: Path) -> None:
    data_dir = populated_data_dir(tmp_path)
    result = create_backup(
        database_path=data_dir / "books.db",
        data_dir=data_dir,
        dest=tmp_path / "backups",
        label="nightly",
    )
    database = result.path / "books.db"
    payload = bytearray(database.read_bytes())
    payload[4096:4200] = b"\x00" * 104
    database.write_bytes(bytes(payload))
    # Re-checksum so the corruption has to be caught by integrity_check itself
    # rather than by the checksum that would otherwise shadow it.
    _rewrite_checksums(result.path)

    with pytest.raises(BackupError, match="integrity"):
        verify_backup(result.path)


def _rewrite_checksums(path: Path) -> None:
    import hashlib

    lines = []
    for line in (path / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        name = line.split("  ", 1)[1]
        digest = hashlib.sha256((path / name).read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}")
    (path / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_restore_brings_back_scores_notes_shelves_and_covers(tmp_path: Path) -> None:
    data_dir = populated_data_dir(tmp_path)
    result = create_backup(
        database_path=data_dir / "books.db",
        data_dir=data_dir,
        dest=tmp_path / "backups",
        label="nightly",
    )

    restored = tmp_path / "restored"
    restore_backup(result.path, into=restored)

    database = sqlite3.connect(restored / "books.db")
    score, notes = database.execute("SELECT score, notes FROM entries").fetchone()
    (title,) = database.execute("SELECT title FROM items").fetchone()
    shelves = [
        row[0]
        for row in database.execute(
            "SELECT s.name FROM shelves s JOIN entry_shelves es ON es.shelf_id = s.id"
        )
    ]
    database.close()

    assert (score, notes) == (9, "The chapter order is the whole point.")
    assert title == "Rayuela"
    assert shelves == ["Argentina"]
    assert (restored / "covers" / "1.jpg").read_bytes() == COVER_BYTES
    assert (restored / "imports" / "batch-1" / "audit.json").read_text(encoding="utf-8") == (
        '{"rows": 1}'
    )


def test_restore_refuses_a_non_empty_target(tmp_path: Path) -> None:
    data_dir = populated_data_dir(tmp_path)
    result = create_backup(
        database_path=data_dir / "books.db",
        data_dir=data_dir,
        dest=tmp_path / "backups",
        label="nightly",
    )
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "books.db").write_bytes(b"someone is already living here")

    with pytest.raises(BackupError, match="not empty"):
        restore_backup(result.path, into=occupied)

    assert (occupied / "books.db").read_bytes() == b"someone is already living here"


def test_retention_keeps_the_newest_and_deletes_only_its_own_label(tmp_path: Path) -> None:
    dest = tmp_path / "backups"
    dest.mkdir()
    created = [_fake_backup(dest, "nightly", day) for day in range(9)]
    survivor = _fake_backup(dest, "pre-migration-0007", 0)
    unrelated = dest / "operator-notes"
    unrelated.mkdir()

    deleted = enforce_retention(dest, keep=7, label="nightly")

    assert sorted(deleted) == sorted(created[:2])
    assert all(path.is_dir() for path in created[2:])
    assert not any(path.exists() for path in created[:2])
    # A pre-migration backup is the rollback point for an upgrade; nightly
    # retention must never be what removes it.
    assert survivor.is_dir()
    assert unrelated.is_dir()


def _fake_backup(dest: Path, label: str, day: int) -> Path:
    created_at = datetime(2026, 8, 1, tzinfo=UTC) + timedelta(days=day)
    path = dest / f"{label}-{created_at.strftime('%Y%m%dT%H%M%SZ')}"
    path.mkdir()
    (path / "manifest.json").write_text(
        json.dumps(
            {
                "kind": "akasha-backup",
                "version": 1,
                "label": label,
                "created_at": created_at.isoformat(),
            }
        ),
        encoding="utf-8",
    )
    return path


def test_retention_ignores_directories_it_did_not_write(tmp_path: Path) -> None:
    dest = tmp_path / "backups"
    dest.mkdir()
    for name in ("holiday-photos", "books.db"):
        (dest / name).mkdir()

    assert enforce_retention(dest, keep=0, label="nightly") == []
    assert sorted(p.name for p in dest.iterdir()) == ["books.db", "holiday-photos"]


def test_the_backup_cli_does_not_need_the_application_configured(tmp_path: Path) -> None:
    """A restore happens on a bare machine, often before anything is configured.

    Importing the package used to build the FastAPI app, whose Settings refuse to
    construct in production without USER_AGENT_CONTACT, so `akasha-backup restore`
    died on a validation error about a metadata provider.
    """
    data_dir = populated_data_dir(tmp_path)
    result = create_backup(
        database_path=data_dir / "books.db",
        data_dir=data_dir,
        dest=tmp_path / "backups",
        label="nightly",
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"USER_AGENT_CONTACT", "GOOGLE_BOOKS_API_KEY"}
    } | {"BOOK_TRACKER_ENVIRONMENT": "production"}

    completed = subprocess.run(
        [sys.executable, "-m", "book_tracker.backup", "verify", str(result.path)],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "verified" in completed.stdout
    # runpy re-executes a module that the package already imported, which used to
    # print a RuntimeWarning into every nightly log.
    assert "RuntimeWarning" not in completed.stderr


def attached(data_dir: Path, content: bytes) -> str:
    """Put a blob in the live store the way the application would (DEC-048)."""
    stored = store_blob(content, data_dir)
    return stored.sha256


def test_a_backup_carries_the_attachment_blobs(tmp_path: Path) -> None:
    data_dir = populated_data_dir(tmp_path)
    digest = attached(data_dir, b"an epub, or near enough")

    result = create_backup(
        database_path=data_dir / "books.db",
        data_dir=data_dir,
        dest=tmp_path / "backups",
        now=datetime.fromisoformat(NOW),
    )

    assert digest in [entry["sha256"] for entry in result.manifest["attachments"]]
    restore_backup(result.path, into=tmp_path / "restored")
    assert (tmp_path / "restored" / "attachments" / digest[:2] / digest).read_bytes() == (
        b"an epub, or near enough"
    )


def test_a_second_backup_shares_blobs_rather_than_copying_them(tmp_path: Path) -> None:
    """Strategy E, the reason DEC-047 recommended it: the seventh copy is free."""
    data_dir = populated_data_dir(tmp_path)
    digest = attached(data_dir, b"x" * 200_000)
    dest = tmp_path / "backups"

    first = create_backup(
        database_path=data_dir / "books.db",
        data_dir=data_dir,
        dest=dest,
        now=datetime.fromisoformat(NOW),
    )
    second = create_backup(
        database_path=data_dir / "books.db",
        data_dir=data_dir,
        dest=dest,
        now=datetime.fromisoformat(NOW) + timedelta(days=1),
    )

    one = (first.path / "attachments" / digest[:2] / digest).stat()
    two = (second.path / "attachments" / digest[:2] / digest).stat()
    assert (one.st_dev, one.st_ino) == (two.st_dev, two.st_ino), "blobs should be hardlinked"


def test_deleting_an_attachment_leaves_the_backup_able_to_restore_it(tmp_path: Path) -> None:
    """The point of a backup: what the owner deleted is still recoverable."""
    data_dir = populated_data_dir(tmp_path)
    digest = attached(data_dir, b"deleted later, restored anyway")

    result = create_backup(
        database_path=data_dir / "books.db",
        data_dir=data_dir,
        dest=tmp_path / "backups",
        now=datetime.fromisoformat(NOW),
    )
    blob_path(data_dir, digest).unlink()

    restore_backup(result.path, into=tmp_path / "restored")
    assert (tmp_path / "restored" / "attachments" / digest[:2] / digest).is_file()


def test_retention_deleting_one_backup_does_not_take_a_shared_blob(tmp_path: Path) -> None:
    """Hardlinks make this work, but only if nothing walks and deletes by content."""
    data_dir = populated_data_dir(tmp_path)
    digest = attached(data_dir, b"shared across two nights")
    dest = tmp_path / "backups"
    create_backup(
        database_path=data_dir / "books.db",
        data_dir=data_dir,
        dest=dest,
        now=datetime.fromisoformat(NOW),
    )
    keeper = create_backup(
        database_path=data_dir / "books.db",
        data_dir=data_dir,
        dest=dest,
        now=datetime.fromisoformat(NOW) + timedelta(days=1),
    )

    enforce_retention(dest, keep=1, label="nightly")

    assert (keeper.path / "attachments" / digest[:2] / digest).is_file()
    verify_backup(keeper.path)


def test_verify_notices_an_attachment_that_went_missing(tmp_path: Path) -> None:
    data_dir = populated_data_dir(tmp_path)
    digest = attached(data_dir, b"here now, gone shortly")
    result = create_backup(
        database_path=data_dir / "books.db",
        data_dir=data_dir,
        dest=tmp_path / "backups",
        now=datetime.fromisoformat(NOW),
    )

    (result.path / "attachments" / digest[:2] / digest).unlink()

    with pytest.raises(BackupError):
        verify_backup(result.path)


def test_a_library_with_no_attachments_still_backs_up_and_restores(tmp_path: Path) -> None:
    data_dir = populated_data_dir(tmp_path)

    result = create_backup(
        database_path=data_dir / "books.db",
        data_dir=data_dir,
        dest=tmp_path / "backups",
        now=datetime.fromisoformat(NOW),
    )
    restore_backup(result.path, into=tmp_path / "restored")

    assert result.manifest["attachments"] == []
    assert (tmp_path / "restored" / "books.db").is_file()
