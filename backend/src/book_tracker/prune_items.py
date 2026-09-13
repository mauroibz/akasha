"""Prune items no entry of any user references any more (DEC-158).

Deleting an entry — the detail page's Delete, triage's Discard, undo — leaves
its item in place on purpose: the item is the shared metadata cache that makes
re-adding instant and, since 2.0, the cache two users can hold at once. But
nothing ever collected the items that lost their last entry, so the cache only
grew. This sweep closes that half of the lifecycle.

The rule is the same one `reclaim_attachments` (DEC-049) established for the
only other routines in this codebase that delete data by inference:

* **It reports rather than removes unless asked.** `apply=False` is the default
  and the CLI requires `--apply`, because the cost of reading the output is
  nothing and the cost of being wrong is someone's library row.
* **It acts only on what it can prove is unreferenced.** An item is a candidate
  when no entry of *any* user points at it and no import record still claims it
  — a batch inside its undo window can still resurrect the row, and an undo that
  finds it gone would silently do less than it promises. Covers follow the item
  row; attachment blobs go only when no other row shares the digest.
* **It never touches what it did not put there.** A file under `covers/` that is
  not a `{item_id}.jpg` we own is reported and left alone.

An item the sweep removes is cache the application can re-fetch: its provider
sources and identifiers cascade with the row (migration 0002), and re-adding it
goes through the same provider path the first add did.
"""

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from book_tracker.infrastructure.attachments import blob_path

DATABASE_NAME = "books.db"
COVERS_DIR = "covers"
_COVER = re.compile(r"^(\d+)\.jpg$")


@dataclass(frozen=True)
class PruneReport:
    """What the sweep found, and what it did about it.

    `pruned`, `reclaimed_covers` and `reclaimed_blobs` name what was removed
    when `applied`, and what would be removed when not. Everything else is here
    so a dry run is readable evidence rather than a number to trust.
    """

    applied: bool
    pruned: tuple[int, ...] = ()
    kept: int = 0
    reclaimed_covers: tuple[str, ...] = ()
    covers_reclaimed: int = 0
    failed_covers: tuple[str, ...] = ()
    blobs_reclaimed: int = 0
    blobs_kept: int = 0
    unknown: tuple[str, ...] = ()


def prune_items(
    data_dir: Path,
    *,
    database_path: Path | None = None,
    apply: bool = False,
) -> PruneReport:
    """Find items nothing references, and remove them only when asked.

    One read of the database decides the candidates, and the removals happen
    in the caller's order: the item rows first (identifiers, sources and
    attachment rows cascade), then the cover files the pruned rows addressed,
    then attachment blobs whose refcount fell to zero with them.
    """
    database = database_path or data_dir / DATABASE_NAME
    candidates, live_digests, referenced, claimed_by_import = _read_database(database)

    pruned: list[int] = []
    kept = len(referenced | claimed_by_import)
    reclaimed_covers: list[str] = []
    failed_covers: list[str] = []
    blobs_reclaimed = 0
    blobs_kept = 0

    # Attachment digests that die with this prune, counted across candidates so
    # a digest two pruned items shared is removed once, correctly.
    dying_digests: set[str] = set()
    for item_id, cover_name, digests in candidates:
        if apply:
            _delete_item_rows(database, item_id)
        pruned.append(item_id)
        if cover_name is not None:
            cover = data_dir / COVERS_DIR / cover_name
            if apply:
                try:
                    cover.unlink(missing_ok=True)
                    reclaimed_covers.append(cover_name)
                except OSError:
                    failed_covers.append(cover_name)
            else:
                reclaimed_covers.append(cover_name)
        for digest in digests:
            if digest in live_digests:
                # Another live row still holds this blob; it is not ours to take.
                blobs_kept += 1
            else:
                blobs_reclaimed += 1
                dying_digests.add(digest)

    if apply:
        for digest in sorted(dying_digests):
            blob_path(data_dir, digest).unlink(missing_ok=True)

    # Stale covers no item points at any more: the same leak in the same
    # directory, from any path that removed an item row without its file.
    unknown: list[str] = []
    stale_covers = 0
    covers = data_dir / COVERS_DIR
    if covers.is_dir():
        for path in sorted(covers.iterdir()):
            if not path.is_file():
                continue
            match = _COVER.match(path.name)
            if match is None:
                unknown.append(path.name)
                continue
            item_id = int(match.group(1))
            if item_id in referenced or item_id in claimed_by_import:
                continue
            if item_id in pruned:
                continue
            if apply:
                try:
                    path.unlink()
                except OSError:
                    failed_covers.append(path.name)
                    continue
            stale_covers += 1
            reclaimed_covers.append(path.name)

    return PruneReport(
        applied=apply,
        pruned=tuple(pruned),
        kept=kept,
        reclaimed_covers=tuple(reclaimed_covers),
        covers_reclaimed=len(reclaimed_covers),
        failed_covers=tuple(failed_covers),
        blobs_reclaimed=blobs_reclaimed,
        blobs_kept=blobs_kept,
        unknown=tuple(unknown),
    )


def _read_database(
    database: Path,
) -> tuple[
    list[tuple[int, str | None, list[str]]],
    set[str],
    set[int],
    set[int],
]:
    """Candidates with their covers and blobs, the digests live rows still hold,
    the item ids an entry references, and the ids an import record still claims.

    Read through a plain `sqlite3` connection rather than the ORM: this runs
    as a maintenance command against a data directory, and it must not depend
    on the application's settings being loadable — the same rule
    `reclaim_attachments` follows.
    """
    if not database.is_file():
        return [], set(), set(), set()
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        items = connection.execute(
            "SELECT i.id, i.cover_path, COALESCE(a.digests, '[]')"
            " FROM items i"
            " LEFT JOIN ("
            "   SELECT item_id, json_group_array(DISTINCT sha256) AS digests"
            "   FROM attachments GROUP BY item_id"
            " ) a ON a.item_id = i.id"
            " WHERE NOT EXISTS (SELECT 1 FROM entries e WHERE e.item_id = i.id)"
        ).fetchall()
        referenced = {
            int(row[0]) for row in connection.execute("SELECT DISTINCT item_id FROM entries")
        }
        # Every digest a live row still holds — the refcount a blob's removal
        # has to respect, exactly as `delete_blob_if_unreferenced` counts it.
        live_digests = {
            str(row[0])
            for row in connection.execute(
                "SELECT DISTINCT a.sha256 FROM attachments a"
                " JOIN items i ON i.id = a.item_id"
                " WHERE EXISTS (SELECT 1 FROM entries e WHERE e.item_id = i.id)"
                " OR i.id IN ("
                "   SELECT matched_item_id FROM import_records"
                "   WHERE matched_item_id IS NOT NULL"
                "   AND batch_id IN ("
                "     SELECT id FROM import_batches WHERE state <> 'undone'"
                "   )"
                " )"
            )
        }
        claimed_by_import = {
            int(row[0])
            for row in connection.execute(
                "SELECT DISTINCT matched_item_id FROM import_records"
                " WHERE matched_item_id IS NOT NULL"
                " AND batch_id IN (SELECT id FROM import_batches WHERE state <> 'undone')"
            )
        }
    finally:
        connection.close()

    candidates: list[tuple[int, str | None, list[str]]] = []
    for item_id, cover_path, digests_json in items:
        if item_id in claimed_by_import:
            continue
        cover_name = None
        if cover_path:
            prefix = f"{COVERS_DIR}/"
            if cover_path.startswith(prefix):
                candidate = cover_path[len(prefix) :]
                if _COVER.match(candidate):
                    cover_name = candidate
        candidates.append((item_id, cover_name, list(set(json.loads(digests_json)))))
    return candidates, live_digests, referenced, claimed_by_import


def _delete_item_rows(database: Path, item_id: int) -> None:
    """Remove one item by id, with plain SQL rather than the ORM.

    The identifier, source and attachment rows cascade (migrations 0002 and
    0010), so one DELETE takes the whole row set. A direct connection is safe
    here for the same reason it is safe everywhere else in this data
    directory: SQLite serializes writers, and the candidate list was read in
    one transaction before any removal began.
    """
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("DELETE FROM items WHERE id = ?", (item_id,))
        connection.commit()
    finally:
        connection.close()


class PruneError(RuntimeError):
    """The database could not be read, so nothing was pruned."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="akasha-prune", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    prune = commands.add_parser("prune", help="remove items no entry of any user references")
    prune.add_argument("--data-dir", type=Path, default=Path("/data"))
    prune.add_argument(
        "--apply",
        action="store_true",
        help="actually remove them; without this the command only reports",
    )

    args = parser.parse_args(argv)
    try:
        report = prune_items(args.data_dir, apply=args.apply)
    except sqlite3.DatabaseError as error:
        print(f"error: {args.data_dir / DATABASE_NAME}: {error}", file=sys.stderr)
        return 1

    verb = "Pruned" if report.applied else "Would prune"
    print(
        f"{verb} {len(report.pruned)} items"
        f" ({len(report.reclaimed_covers)} covers, {report.blobs_reclaimed} blobs)"
    )
    print(f"Kept {report.kept} items an entry or an import still holds")
    for item_id in report.pruned:
        print(f"  {'removed' if report.applied else 'orphan'} item {item_id}")
    for name in report.reclaimed_covers:
        print(f"  {'removed' if report.applied else 'orphan'} cover {name}")
    for name in report.failed_covers:
        print(f"  could not remove cover {name}", file=sys.stderr)
    for name in report.unknown:
        print(f"  not ours, left alone {name}")
    if not report.applied and report.pruned:
        print("Nothing was removed. Re-run with --apply to prune.")
    return 1 if report.failed_covers else 0


if __name__ == "__main__":
    raise SystemExit(main())
