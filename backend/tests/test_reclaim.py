"""Reclaiming attachment blobs that nothing points at any more (DEC-049).

This is the one routine in the codebase that deletes data by inference, so the
tests are weighted towards what it must *not* remove. Three properties carry the
weight: a blob any live row references survives, including one shared by two
items; a blob a backup has linked survives the live copy going away, byte for
byte; and a blob written seconds ago by an upload whose row has not been
committed yet is left where it is.

The last of those is the concurrency case the sprint file names. Two independent
protections cover it, and both are asserted here: the walk reads the filesystem
before it reads the database, so a row committed in between makes a blob look
referenced rather than orphaned, and a blob younger than the grace period is
never a candidate in the first place.
"""

import json
import os
import sqlite3
import time
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from book_tracker.backup import create_backup
from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.infrastructure.attachments import blob_path, store_blob
from book_tracker.infrastructure.models import AttachmentRow, ItemRow
from book_tracker.migrations import upgrade
from book_tracker.reclaim import main, reclaim_attachments

NOW = "2026-08-14T00:00:00+00:00"
CONTENT = b"an epub, or near enough for a test that only cares about the bytes"
OTHER = b"a different file entirely, so it lands under a different digest"


def make_data_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    for directory in ("", "covers", "imports"):
        (data_dir / directory).mkdir(parents=True, exist_ok=True)
    configured = Settings(data_dir=data_dir, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url)
    return data_dir


def engine_for(data_dir: Path):
    return create_engine(Settings(data_dir=data_dir, user_agent_contact="test@example.invalid"))


def make_item(data_dir: Path, title: str = "Rayuela") -> int:
    with Session(engine_for(data_dir)) as session:
        item = ItemRow(
            type="book",
            title=title,
            subtitle=None,
            year=1963,
            cover_path=None,
            identifiers="{}",
            metadata_json=json.dumps({"authors": ["Julio Cortázar"]}),
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(item)
        session.commit()
        return int(item.id)


def attach(data_dir: Path, item_id: int, content: bytes, filename: str = "book.epub") -> str:
    """Store a blob and record the row, the way `add_attachment` does."""
    stored = store_blob(content, data_dir)
    with Session(engine_for(data_dir)) as session:
        session.add(
            AttachmentRow(
                item_id=item_id,
                filename=filename,
                byte_size=stored.byte_size,
                sha256=stored.sha256,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.commit()
    return stored.sha256


def age(data_dir: Path, sha256: str, *, seconds: int) -> None:
    """Backdate a blob so the grace period stops shielding it."""
    target = blob_path(data_dir, sha256)
    old = time.time() - seconds
    os.utime(target, (old, old))


def test_a_blob_nothing_references_is_reclaimed(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    orphan = store_blob(CONTENT, data_dir).sha256
    age(data_dir, orphan, seconds=7200)

    report = reclaim_attachments(data_dir, apply=True)

    assert report.reclaimed == (orphan,)
    assert report.reclaimed_bytes == len(CONTENT)
    assert not blob_path(data_dir, orphan).exists()


def test_a_referenced_blob_is_kept(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    digest = attach(data_dir, make_item(data_dir), CONTENT)
    age(data_dir, digest, seconds=7200)

    report = reclaim_attachments(data_dir, apply=True)

    assert report.reclaimed == ()
    assert report.kept == 1
    assert blob_path(data_dir, digest).read_bytes() == CONTENT


def test_a_blob_two_items_share_survives_one_of_them_dropping_it(tmp_path: Path) -> None:
    """The refcount is the whole point: one item's delete must not take the other's file."""
    data_dir = make_data_dir(tmp_path)
    first = make_item(data_dir, "Rayuela")
    second = make_item(data_dir, "Bestiario")
    digest = attach(data_dir, first, CONTENT)
    assert attach(data_dir, second, CONTENT) == digest
    age(data_dir, digest, seconds=7200)

    with Session(engine_for(data_dir)) as session:
        session.query(AttachmentRow).filter(AttachmentRow.item_id == first).delete()
        session.commit()

    report = reclaim_attachments(data_dir, apply=True)

    assert report.reclaimed == ()
    assert blob_path(data_dir, digest).read_bytes() == CONTENT


def test_a_dry_run_reports_without_removing_anything(tmp_path: Path) -> None:
    """The default, because this routine infers what to delete."""
    data_dir = make_data_dir(tmp_path)
    orphan = store_blob(CONTENT, data_dir).sha256
    age(data_dir, orphan, seconds=7200)

    report = reclaim_attachments(data_dir)

    assert report.applied is False
    assert report.reclaimed == (orphan,)
    assert blob_path(data_dir, orphan).read_bytes() == CONTENT


def test_a_blob_written_seconds_ago_is_left_alone(tmp_path: Path) -> None:
    """An upload that has written its blob but not yet committed its row.

    Not backdated, so it is inside the grace period. Reclaiming it would delete a
    file that is about to be referenced, which is the failure this window exists
    to prevent.
    """
    data_dir = make_data_dir(tmp_path)
    in_flight = store_blob(CONTENT, data_dir).sha256

    report = reclaim_attachments(data_dir, apply=True)

    assert report.reclaimed == ()
    assert report.skipped_recent == (in_flight,)
    assert blob_path(data_dir, in_flight).read_bytes() == CONTENT


def test_a_blob_orphaned_by_an_item_delete_is_found(tmp_path: Path) -> None:
    """`attachments.item_id` is ON DELETE CASCADE, so the row goes and the bytes stay.

    Undo retains an item that carries an attachment (DEC-047), so this route is
    unreachable through the application today. It is reachable through anything
    that deletes an item without knowing about that guard, which is exactly why
    the sweep rather than the guard is the fix.
    """
    data_dir = make_data_dir(tmp_path)
    item_id = make_item(data_dir)
    digest = attach(data_dir, item_id, CONTENT)
    age(data_dir, digest, seconds=7200)

    with sqlite3.connect(data_dir / "books.db") as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("DELETE FROM items WHERE id = ?", (item_id,))
        assert connection.execute("SELECT count(*) FROM attachments").fetchone()[0] == 0

    report = reclaim_attachments(data_dir, apply=True)

    assert report.reclaimed == (digest,)
    assert not blob_path(data_dir, digest).exists()


def test_a_temporary_file_from_a_crashed_upload_is_reclaimed(tmp_path: Path) -> None:
    """`store_blob` writes to `upload-*.tmp` next to its target and moves it into place.

    A process killed between the write and the move leaves the temporary behind,
    and nothing has ever collected it.
    """
    data_dir = make_data_dir(tmp_path)
    stale = data_dir / "attachments" / "ab" / "upload-abcdef.tmp"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_bytes(CONTENT)
    old = time.time() - 7200
    os.utime(stale, (old, old))

    report = reclaim_attachments(data_dir, apply=True)

    assert stale.name in report.reclaimed
    assert not stale.exists()


def test_reclaiming_the_live_copy_leaves_the_backup_readable(tmp_path: Path) -> None:
    """The safety question acceptance criterion 1 asks about, answered by measurement.

    The backup hardlinks blobs out of the live store, so the backup directory
    holds its own directory entry against the same inode. Unlinking the live path
    decrements a link count; it cannot reach the bytes while the backup still
    names them.
    """
    data_dir = make_data_dir(tmp_path)
    item_id = make_item(data_dir)
    digest = attach(data_dir, item_id, CONTENT)
    backup = create_backup(
        database_path=data_dir / "books.db",
        data_dir=data_dir,
        dest=tmp_path / "backups",
        label="nightly",
    )
    kept = backup.path / "attachments" / digest[:2] / digest
    assert kept.is_file()

    with Session(engine_for(data_dir)) as session:
        session.query(AttachmentRow).delete()
        session.commit()
    age(data_dir, digest, seconds=7200)
    report = reclaim_attachments(data_dir, apply=True)

    assert report.reclaimed == (digest,)
    assert not blob_path(data_dir, digest).exists()
    assert kept.read_bytes() == CONTENT


def test_a_file_that_is_not_ours_is_left_alone_and_reported(tmp_path: Path) -> None:
    """`enforce_retention` only touches directories carrying our manifest, for the
    same reason: a routine that deletes whatever it finds eventually finds
    something that was not its to delete."""
    data_dir = make_data_dir(tmp_path)
    stranger = data_dir / "attachments" / "ab" / "notes.txt"
    stranger.parent.mkdir(parents=True, exist_ok=True)
    stranger.write_bytes(b"put here by a human")
    old = time.time() - 7200
    os.utime(stranger, (old, old))

    report = reclaim_attachments(data_dir, apply=True)

    assert report.reclaimed == ()
    assert report.unknown == ("ab/notes.txt",)
    assert stranger.read_bytes() == b"put here by a human"


def test_an_empty_store_reports_nothing_to_do(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)

    report = reclaim_attachments(data_dir)

    assert report.reclaimed == ()
    assert report.kept == 0
    assert report.unknown == ()


def test_a_row_committed_during_the_walk_keeps_its_blob(tmp_path: Path) -> None:
    """The ordering protection, isolated from the grace period.

    The filesystem is read first and the database second. A blob that was on disk
    before the walk and referenced before the query therefore reads as referenced.
    Reversing the two would report it as an orphan and delete a file the owner had
    just attached.
    """
    data_dir = make_data_dir(tmp_path)
    item_id = make_item(data_dir)
    digest = store_blob(CONTENT, data_dir).sha256
    age(data_dir, digest, seconds=7200)

    def commit_the_row() -> None:
        with Session(engine_for(data_dir)) as session:
            session.add(
                AttachmentRow(
                    item_id=item_id,
                    filename="book.epub",
                    byte_size=len(CONTENT),
                    sha256=digest,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            session.commit()

    report = reclaim_attachments(data_dir, apply=True, _after_walk=commit_the_row)

    assert report.reclaimed == ()
    assert blob_path(data_dir, digest).read_bytes() == CONTENT


@pytest.mark.parametrize("apply_it", [False, True])
def test_a_missing_store_is_not_an_error(tmp_path: Path, apply_it: bool) -> None:
    data_dir = make_data_dir(tmp_path)

    report = reclaim_attachments(data_dir, apply=apply_it)

    assert report.reclaimed == ()


def test_the_command_reports_without_removing_unless_told_to(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The operator-facing half: reading the report has to be enough to decide."""
    data_dir = make_data_dir(tmp_path)
    orphan = store_blob(CONTENT, data_dir).sha256
    age(data_dir, orphan, seconds=7200)

    assert main(["reclaim", "--data-dir", str(data_dir)]) == 0

    printed = capsys.readouterr().out
    assert "Would reclaim 1 blobs" in printed
    assert orphan in printed
    assert "--apply" in printed
    assert blob_path(data_dir, orphan).read_bytes() == CONTENT

    assert main(["reclaim", "--data-dir", str(data_dir), "--apply"]) == 0

    printed = capsys.readouterr().out
    assert "Reclaimed 1 blobs" in printed
    assert not blob_path(data_dir, orphan).exists()


def test_the_command_keeps_a_referenced_blob(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = make_data_dir(tmp_path)
    digest = attach(data_dir, make_item(data_dir), CONTENT)
    age(data_dir, digest, seconds=7200)

    assert main(["reclaim", "--data-dir", str(data_dir), "--apply"]) == 0

    assert "Kept 1 referenced blobs" in capsys.readouterr().out
    assert blob_path(data_dir, digest).read_bytes() == CONTENT
