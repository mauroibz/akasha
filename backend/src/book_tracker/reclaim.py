"""Reclaim attachment blobs that no row points at any more (DEC-049).

`delete_attachment` refcounts its own blob, but three routes produce a file
nothing references and nothing can find: `attachments.item_id` is
`ON DELETE CASCADE`, so deleting an item drops the rows and leaves the bytes;
`store_blob` writes before the row is inserted on purpose, so a crash between
them leaves an orphan; and an item outlives the entry that introduced it. At
2.5 MB a file that is a materially different problem from the 39 KB orphaned
cover the product spec once waved through.

**This is the only routine in the codebase that deletes data by inference**, so
it is built the way `enforce_retention` is built: it acts on what it can prove is
ours and reports everything else rather than tidying it. Three rules follow.

*It reads the filesystem before it reads the database.* An upload writes its blob
and then commits its row, so a walk that lists blobs first and asks about
references second can only ever be too generous: a row committed in between makes
the blob read as referenced. Doing it the other way round -- reading references
first, walking second -- reports a file that was attached seconds ago as an
orphan and deletes it. The order is the protection, not an implementation detail.

*A blob younger than the grace period is never a candidate.* That covers the same
window from the other side, for the upload whose row is still in flight when both
reads happen. An hour is far longer than any upload this application accepts and
costs nothing but a delayed reclaim.

*It reports rather than deletes unless asked.* `apply=False` is the default and
the CLI requires `--apply`, because the cost of running this and reading the
output is nothing and the cost of being wrong is an epub.

A blob a backup has linked is safe regardless: the backup holds its own directory
entry against the same inode (DEC-048), so unlinking the live path decrements a
link count rather than reaching the bytes.
"""

import argparse
import re
import sqlite3
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from shutil import rmtree

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from book_tracker.infrastructure.attachments import ATTACHMENTS_DIR
from book_tracker.infrastructure.models import ImportBatchRow

DATABASE_NAME = "books.db"
GRACE_SECONDS = 3600
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_TEMPORARY = re.compile(r"^upload-.*\.tmp$")


@dataclass(frozen=True)
class ReclaimReport:
    """What the sweep found, and what it did about it.

    `reclaimed` names what was removed when `applied`, and what would be removed
    when not. Everything else is here so a dry run is readable evidence rather
    than a number to trust.
    """

    applied: bool
    reclaimed: tuple[str, ...] = ()
    reclaimed_bytes: int = 0
    kept: int = 0
    kept_bytes: int = 0
    skipped_recent: tuple[str, ...] = ()
    unknown: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()


@dataclass
class _Candidate:
    path: Path
    name: str
    byte_size: int
    digest: str | None
    recent: bool
    unknown: bool = field(default=False)


def reclaim_attachments(
    data_dir: Path,
    *,
    database_path: Path | None = None,
    apply: bool = False,
    grace_seconds: int = GRACE_SECONDS,
    _after_walk: Callable[[], None] | None = None,
) -> ReclaimReport:
    """Find blobs nothing references, and remove them only when asked.

    `_after_walk` exists for the test that pins the read ordering; it is the only
    way to commit a row in the window between the two reads deterministically.
    """
    store = data_dir / ATTACHMENTS_DIR
    candidates = _walk(store, grace_seconds=grace_seconds)
    if _after_walk is not None:
        _after_walk()
    referenced = _referenced_digests(database_path or data_dir / DATABASE_NAME)

    reclaimed: list[str] = []
    reclaimed_bytes = 0
    kept = 0
    kept_bytes = 0
    skipped: list[str] = []
    unknown: list[str] = []
    failed: list[str] = []

    for candidate in sorted(candidates, key=lambda found: found.name):
        if candidate.unknown:
            unknown.append(candidate.path.relative_to(store).as_posix())
            continue
        if candidate.digest is not None and candidate.digest in referenced:
            kept += 1
            kept_bytes += candidate.byte_size
            continue
        if candidate.recent:
            skipped.append(candidate.name)
            continue
        if apply:
            try:
                candidate.path.unlink(missing_ok=True)
            except OSError:
                failed.append(candidate.name)
                continue
        reclaimed.append(candidate.name)
        reclaimed_bytes += candidate.byte_size

    return ReclaimReport(
        applied=apply,
        reclaimed=tuple(reclaimed),
        reclaimed_bytes=reclaimed_bytes,
        kept=kept,
        kept_bytes=kept_bytes,
        skipped_recent=tuple(skipped),
        unknown=tuple(unknown),
        failed=tuple(failed),
    )


def _walk(store: Path, *, grace_seconds: int) -> list[_Candidate]:
    """Every file under the store, classified but not judged.

    A name is either a digest we wrote, a temporary a crashed upload left behind,
    or something we did not put there and will not touch.
    """
    if not store.is_dir():
        return []
    cutoff = time.time() - grace_seconds
    found: list[_Candidate] = []
    for path in sorted(store.rglob("*")):
        if not path.is_file():
            continue
        stat = path.stat()
        digest = path.name if _DIGEST.match(path.name) else None
        found.append(
            _Candidate(
                path=path,
                name=path.name,
                byte_size=stat.st_size,
                digest=digest,
                recent=stat.st_mtime > cutoff,
                unknown=digest is None and not _TEMPORARY.match(path.name),
            )
        )
    return found


def _referenced_digests(database_path: Path) -> set[str]:
    """Every digest a live row points at.

    Read through a plain `sqlite3` connection rather than the ORM: this runs as a
    maintenance command against a data directory, and it must not depend on the
    application's settings being loadable.
    """
    if not database_path.is_file():
        return set()
    connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    try:
        rows = connection.execute("SELECT DISTINCT sha256 FROM attachments").fetchall()
    except sqlite3.DatabaseError as error:
        raise ReclaimError(f"{database_path}: attachments could not be read: {error}") from error
    finally:
        connection.close()
    return {str(row[0]) for row in rows}


class ReclaimError(RuntimeError):
    """The store or the database could not be read, so nothing was reclaimed."""


@dataclass(frozen=True)
class ImportBatchReclaimReport:
    """Which committed batches' staging directories were removed."""

    reclaimed: tuple[str, ...] = ()


def reclaim_import_batches(
    engine: Engine, data_dir: Path, *, now: datetime | None = None
) -> ImportBatchReclaimReport:
    """Remove a committed batch's staging directory once its undo window has passed.

    Unlike `reclaim_attachments`, this is not deletion by inference. `application/undo.py`
    never reads `data_dir / "imports" / batch_id` — it works entirely from the database
    ledger and the attachments store — and nothing else in this codebase reads a batch's
    staging directory after `ImportService.commit` has already moved its staged covers
    into `covers/`. A committed batch past its undo window therefore has nothing left that
    depends on this directory, which is what makes automatic removal safe here where it
    would not be for an attachment blob. Runs on every `JobRunner` idle tick, alongside
    `JobRepository.reclaim_expired` — no `--apply` gate, for the same reason.

    An uncommitted (still-`previewed`) batch that is simply abandoned is not covered: its
    `undo_expires_at` is never set, so it never becomes a candidate here. That is a
    narrower, separate leak from the one this sprint's acceptance criteria describe.
    """
    now_iso = (now or datetime.now(UTC)).isoformat().replace("+00:00", "Z")
    reclaimed: list[str] = []
    with Session(engine) as session:
        expired = session.scalars(
            select(ImportBatchRow).where(
                ImportBatchRow.state == "committed",
                ImportBatchRow.undo_expires_at.is_not(None),
                ImportBatchRow.undo_expires_at <= now_iso,
            )
        ).all()
        for batch in expired:
            staging = data_dir / "imports" / batch.id
            if staging.is_dir():
                rmtree(staging)
                reclaimed.append(batch.id)
    return ImportBatchReclaimReport(reclaimed=tuple(reclaimed))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="akasha-attachments", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    sweep = commands.add_parser("reclaim", help="remove attachment blobs nothing references")
    sweep.add_argument("--data-dir", type=Path, default=Path("/data"))
    sweep.add_argument(
        "--apply",
        action="store_true",
        help="actually remove them; without this the command only reports",
    )
    sweep.add_argument(
        "--grace-seconds",
        type=int,
        default=GRACE_SECONDS,
        help="leave blobs written more recently than this alone (default 3600)",
    )

    args = parser.parse_args(argv)
    try:
        report = reclaim_attachments(
            args.data_dir, apply=args.apply, grace_seconds=args.grace_seconds
        )
    except ReclaimError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    verb = "Reclaimed" if report.applied else "Would reclaim"
    print(f"{verb} {len(report.reclaimed)} blobs ({_megabytes(report.reclaimed_bytes)})")
    print(f"Kept {report.kept} referenced blobs ({_megabytes(report.kept_bytes)})")
    for name in report.reclaimed:
        print(f"  {'removed' if report.applied else 'orphan'} {name}")
    for name in report.skipped_recent:
        print(f"  recent, left alone {name}")
    for name in report.unknown:
        print(f"  not ours, left alone {name}")
    for name in report.failed:
        print(f"  could not remove {name}", file=sys.stderr)
    if not report.applied and report.reclaimed:
        print("Nothing was removed. Re-run with --apply to reclaim.")
    return 1 if report.failed else 0


def _megabytes(value: int) -> str:
    return f"{value / (1024 * 1024):.1f} MB"


if __name__ == "__main__":
    raise SystemExit(main())
