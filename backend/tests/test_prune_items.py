"""Pruning items no entry of any user references any more (DEC-158).

An item with no entries is cache the application can re-fetch, and its cover
and attachments are re-fetchable or re-uploadable with it. `prune_items`
removes exactly that: the item row (whose identifiers, sources and
attachment rows cascade), its cover file, and its attachment blobs once
nothing else references them.

This routine deletes data by inference, so — like `reclaim_attachments`
(DEC-049) — it reports rather than removes unless `--apply` is passed, and
the tests are weighted towards what it must *not* remove: an item any user's
entry still holds survives, a blob another live row shares survives the
pruned item dropping it, and a file that is not ours is reported, not
touched.
"""

import json
import sqlite3
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.infrastructure.attachments import blob_path, store_blob
from book_tracker.infrastructure.models import AttachmentRow, EntryRow, ItemRow
from book_tracker.migrations import upgrade
from book_tracker.prune_items import main, prune_items

NOW = "2026-09-13T00:00:00+00:00"
CONTENT = b"an epub, or near enough for a test that only cares about the bytes"


def make_data_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    for directory in ("", "covers", "imports"):
        (data_dir / directory).mkdir(parents=True, exist_ok=True)
    configured = Settings(data_dir=data_dir, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url)
    # The second user the shared-cache test needs. Raw SQL rather than the
    # password helpers: this suite never logs in, it only needs the FK row.
    with sqlite3.connect(data_dir / "books.db") as connection:
        connection.execute(
            "INSERT INTO users (id, username, display_name, password_hash,"
            " password_salt, is_admin, created_at, updated_at)"
            " VALUES (2, 'second', 'Second', 'x', 'y', 0, :now, :now)".replace(":now", "?"),
            (NOW, NOW),
        )
    return data_dir


def engine_for(data_dir: Path):
    return create_engine(Settings(data_dir=data_dir, user_agent_contact="test@example.invalid"))


def make_item(data_dir: Path, title: str = "Rayuela", *, cover: bool = False) -> int:
    with Session(engine_for(data_dir)) as session:
        item = ItemRow(
            type="book",
            title=title,
            subtitle=None,
            year=1963,
            cover_path=None,
            identifiers="{}",
            metadata_json=json.dumps({"creators": ["Julio Cortázar"]}),
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(item)
        session.commit()
        item_id = int(item.id)
    if cover:
        # The real convention: `install_cover` addresses a cover by its item id.
        with Session(engine_for(data_dir)) as session:
            session.execute(
                text("UPDATE items SET cover_path = :path WHERE id = :id"),
                {"path": f"covers/{item_id}.jpg", "id": item_id},
            )
            session.commit()
        (data_dir / "covers" / f"{item_id}.jpg").write_bytes(b"jpeg bytes")
    return item_id


def make_entry(data_dir: Path, item_id: int, user_id: int = 1) -> int:
    with Session(engine_for(data_dir)) as session:
        entry = EntryRow(
            user_id=user_id,
            item_id=item_id,
            status="unsorted",
            score=None,
            notes=None,
            date_added=NOW,
            date_started=None,
            date_finished=None,
            reread_count=0,
            progress=None,
            score_provisional=0,
            suggested_status=None,
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(entry)
        session.commit()
        return int(entry.id)


def attach(data_dir: Path, item_id: int, content: bytes = CONTENT) -> str:
    stored = store_blob(content, data_dir)
    with Session(engine_for(data_dir)) as session:
        session.add(
            AttachmentRow(
                item_id=item_id,
                filename="book.epub",
                byte_size=stored.byte_size,
                sha256=stored.sha256,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.commit()
    return stored.sha256


def test_an_item_no_entry_references_is_pruned_with_its_cover(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    orphan = make_item(data_dir, "Orphan", cover=True)
    kept = make_item(data_dir, "Kept", cover=True)
    make_entry(data_dir, kept)

    report = prune_items(data_dir, apply=True)

    assert report.pruned == (orphan,)
    assert (data_dir / "covers" / f"{orphan}.jpg").exists() is False
    assert (data_dir / "covers" / f"{kept}.jpg").exists() is True
    with Session(engine_for(data_dir)) as session:
        assert session.get(ItemRow, orphan) is None
        assert session.get(ItemRow, kept) is not None


def test_an_item_another_user_still_holds_survives(tmp_path: Path) -> None:
    """Since 2.0 the item cache is shared: entries, not users, are the refcount."""
    data_dir = make_data_dir(tmp_path)
    shared = make_item(data_dir, "Shared")
    make_entry(data_dir, shared, user_id=2)

    report = prune_items(data_dir, apply=True)

    assert report.pruned == ()
    assert report.kept == 1
    with Session(engine_for(data_dir)) as session:
        assert session.get(ItemRow, shared) is not None


def test_a_dry_run_reports_without_removing_anything(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    orphan = make_item(data_dir, "Orphan", cover=True)

    report = prune_items(data_dir, apply=False)

    assert report.pruned == (orphan,)
    assert report.applied is False
    with Session(engine_for(data_dir)) as session:
        assert session.get(ItemRow, orphan) is not None
    assert (data_dir / "covers" / f"{orphan}.jpg").exists() is True


def test_attachment_blobs_go_with_the_item_unless_shared(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    orphan = make_item(data_dir, "Orphan")
    sharer = make_item(data_dir, "Sharer")
    make_entry(data_dir, sharer)
    digest = attach(data_dir, orphan)
    assert attach(data_dir, sharer) == digest

    report = prune_items(data_dir, apply=True)

    assert report.pruned == (orphan,)
    assert report.blobs_reclaimed == 0
    assert report.blobs_kept == 1
    assert blob_path(data_dir, digest).read_bytes() == CONTENT


def test_a_pruned_items_attachment_blob_is_removed(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    orphan = make_item(data_dir, "Orphan")
    digest = attach(data_dir, orphan)

    report = prune_items(data_dir, apply=True)

    assert report.pruned == (orphan,)
    assert report.blobs_reclaimed == 1
    assert blob_path(data_dir, digest).exists() is False


def test_identifiers_and_sources_cascade_with_the_item(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    orphan = make_item(data_dir, "Orphan")
    with Session(engine_for(data_dir)) as session:
        session.execute(
            text(
                "INSERT INTO item_identifiers (item_id, kind, normalized_value, value,"
                " created_at, updated_at)"
                " VALUES (:item, 'isbn13', '9788437604572', '9788437604572', :now, :now)"
            ),
            {"item": orphan, "now": NOW},
        )
        session.execute(
            text(
                "INSERT INTO item_sources (source, source_id, item_id, is_primary,"
                " created_at, updated_at)"
                " VALUES ('openlibrary', 'OL1M', :item, 1, :now, :now)"
            ),
            {"item": orphan, "now": NOW},
        )
        session.commit()

    report = prune_items(data_dir, apply=True)

    assert report.pruned == (orphan,)
    with Session(engine_for(data_dir)) as session:
        identifiers = session.execute(
            text("SELECT COUNT(*) FROM item_identifiers WHERE item_id = :item"),
            {"item": orphan},
        ).scalar_one()
        sources = session.execute(
            text("SELECT COUNT(*) FROM item_sources WHERE item_id = :item"),
            {"item": orphan},
        ).scalar_one()
        assert identifiers == 0
        assert sources == 0


def test_a_cover_file_left_behind_by_a_missing_row_is_reported(
    tmp_path: Path,
) -> None:
    """The sweep also collects covers no item points at, because that is the
    same leak in the same directory: an undo that deleted its item rows once
    left the jpg behind."""
    data_dir = make_data_dir(tmp_path)
    (data_dir / "covers" / "9999.jpg").write_bytes(b"stale jpeg")

    report = prune_items(data_dir, apply=True)

    assert report.covers_reclaimed == 1
    assert (data_dir / "covers" / "9999.jpg").exists() is False


def test_a_file_that_is_not_ours_is_left_alone_and_reported(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    (data_dir / "covers" / "notes.txt").write_text("the owner put this here")

    report = prune_items(data_dir, apply=True)

    assert report.unknown == ("notes.txt",)
    assert (data_dir / "covers" / "notes.txt").read_text() == "the owner put this here"


def test_an_empty_library_reports_nothing_to_do(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    make_item(data_dir, "Kept")
    make_entry(data_dir, 1)

    report = prune_items(data_dir, apply=True)

    assert report.pruned == ()
    assert report.kept == 1
    assert report.covers_reclaimed == 0


def test_the_cli_reports_without_apply_and_exits_zero(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    make_item(data_dir, "Orphan")

    exit_code = main(["prune", "--data-dir", str(data_dir)])

    assert exit_code == 0
    with Session(engine_for(data_dir)) as session:
        assert session.scalar(text("SELECT COUNT(*) FROM items WHERE title = 'Orphan'")) == 1


def test_the_cli_applies_with_the_flag(tmp_path: Path, capsys) -> None:
    data_dir = make_data_dir(tmp_path)
    make_item(data_dir, "Orphan")

    exit_code = main(["prune", "--data-dir", str(data_dir), "--apply"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Would reclaim" not in captured.out
    assert "Reclaimed" in captured.out or "Pruned" in captured.out
    with Session(engine_for(data_dir)) as session:
        assert session.scalar(text("SELECT COUNT(*) FROM items WHERE title = 'Orphan'")) == 0


def test_a_prune_never_touches_items_with_pending_import_records(
    tmp_path: Path,
) -> None:
    """An item a not-yet-undone import matched is still inside an undo window.

    Undo replays the batch's effects; if the item row were gone it would count
    the row `skipped` and the undo would silently do less than it promises.
    Only items no import record claims are candidates."""
    data_dir = make_data_dir(tmp_path)
    orphan = make_item(data_dir, "Orphan")
    with Session(engine_for(data_dir)) as session:
        session.execute(
            text(
                "INSERT INTO import_batches (id, user_id, kind, fingerprint, state,"
                " source_descriptor, preview_summary, counters, created_at, updated_at)"
                " VALUES ('b1', 1, 'goodreads', 'f1', 'committed', '{}', '{}', '{}',"
                " :now, :now)"
            ),
            {"now": NOW},
        )
        session.execute(
            text(
                "INSERT INTO import_records (batch_id, user_id, row_number,"
                " normalized_payload, conflicts, validation_errors, matched_item_id,"
                " created_at, updated_at)"
                " VALUES ('b1', 1, 1, '{}', '[]', '[]', :item, :now, :now)"
            ),
            {"item": orphan, "now": NOW},
        )
        session.commit()

    report = prune_items(data_dir, apply=True)

    assert report.pruned == ()
    assert report.kept == 1


def test_the_report_names_a_cover_that_could_not_be_removed(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    orphan = make_item(data_dir, "Orphan", cover=True)
    cover = data_dir / "covers" / f"{orphan}.jpg"
    cover.chmod(0o444)
    target = cover.parent
    target.chmod(0o555)

    try:
        report = prune_items(data_dir, apply=True)
    finally:
        target.chmod(0o755)
        cover.chmod(0o644)

    assert report.failed_covers == (f"{orphan}.jpg",)
