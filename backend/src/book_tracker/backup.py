"""Online SQLite backup with checksums, retention and a verified restore.

Three rules shape this module.

A live SQLite database in WAL mode must never be copied file-by-file: the copy
can land mid-transaction and the `-wal` sidecar it needs may not be captured
with it. The database here goes through `sqlite3.Connection.backup`, which is
the online backup API and is safe against a concurrent writer.

The backup that matters is the one that restores. `verify_backup` recomputes
every checksum and re-runs `PRAGMA integrity_check` on the copy, and
`restore_backup` verifies before it writes anything.

Retention is scoped to a label. Nightly backups expire; the backup taken
immediately before a migration is the rollback point for that upgrade, and
nightly housekeeping must never be what deletes it.

Attachments are shared, not copied. DEC-047 measured the naive alternative --
tarring them into every nightly backup -- at 67.9x the current backup, against
10.5x for hardlinking them out of the content-addressed store. A blob named for
its own digest can never change, so a link is always safe; where BACKUP_DIR is
on another filesystem the link falls back to a copy and the cost degrades to
what the tar would have been. gzip is not used on them at all: DEC-047 measured
its ratio on an epub corpus at 1.0003, so it produced a larger file than the
input while costing 20.4s per backup against 2.0s without it.
"""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tarfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from shutil import rmtree
from typing import Any

from book_tracker.infrastructure.diskspace import InsufficientDiskSpace, ensure_free_space

MANIFEST_NAME = "manifest.json"
CHECKSUM_NAME = "checksums.sha256"
DATABASE_NAME = "books.db"
MANIFEST_KIND = "akasha-backup"
MANIFEST_VERSION = 2
#: Version-1 compatibility only (Sprint 060, DEC-124): a v1 backup tarred both of
#: these; a v2 one shares covers by hardlink/copy and does not archive imports at
#: all. `restore_backup` still reads this to extract an old backup correctly.
ARCHIVED_DIRECTORIES = ("covers", "imports")
ATTACHMENTS_DIR = "attachments"
_CHUNK = 1024 * 1024


class BackupError(RuntimeError):
    """A backup could not be created, verified or restored."""


@dataclass(frozen=True)
class BackupResult:
    path: Path
    manifest: dict[str, Any]


def create_backup(
    *,
    database_path: Path,
    data_dir: Path,
    dest: Path,
    label: str = "nightly",
    now: datetime | None = None,
    min_free_bytes: int | None = None,
) -> BackupResult:
    """Write one self-contained backup directory and return where it landed."""
    if not database_path.is_file():
        raise BackupError(f"No database to back up at {database_path}")
    if min_free_bytes is not None:
        dest.mkdir(parents=True, exist_ok=True)
        ensure_free_space(dest, min_free_bytes)
    stamp = (now or datetime.now(UTC)).astimezone(UTC)
    path = dest / f"{label}-{stamp.strftime('%Y%m%dT%H%M%SZ')}"
    if path.exists():
        raise BackupError(f"A backup already exists at {path}")
    path.mkdir(parents=True)
    try:
        counts = _copy_database(database_path, path / DATABASE_NAME)
        covers = _share_covers(data_dir, path)
        counts["covers"] = len(covers)
        attachments = _share_attachments(data_dir, path, dest)
        counts["attachments"] = len(attachments)
        # /data/imports is deliberately not archived (DEC-124): it holds derived,
        # short-lived staging for a batch that is either committed -- where the
        # durable result is already in the database and in `covers` -- or
        # abandoned, in which case there is nothing worth restoring anyway.
        archived = [DATABASE_NAME]
        manifest: dict[str, Any] = {
            "kind": MANIFEST_KIND,
            "version": MANIFEST_VERSION,
            "label": label,
            "created_at": stamp.isoformat(),
            "alembic_revision": _revision(path / DATABASE_NAME),
            "counts": counts,
            "files": archived,
            "attachments": attachments,
            "covers": covers,
        }
        (path / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        _write_checksums(path, [*archived, MANIFEST_NAME])
        verify_backup(path)
    except BaseException:
        rmtree(path, ignore_errors=True)
        raise
    return BackupResult(path=path, manifest=manifest)


def verify_backup(path: Path) -> dict[str, Any]:
    """Recompute every checksum and re-check the database. Raises on any mismatch."""
    manifest = read_manifest(path)
    if manifest is None:
        raise BackupError(f"{path} does not look like an Akasha backup")
    recorded = _read_checksums(path)
    if not recorded:
        raise BackupError(f"{path} has no {CHECKSUM_NAME}")
    for name, expected in recorded.items():
        candidate = path / name
        if not candidate.is_file():
            raise BackupError(f"{path}: {name} is missing")
        actual = _digest(candidate)
        if actual != expected:
            raise BackupError(f"{path}: {name} failed its checksum")
    for entry in manifest.get("attachments", []):
        digest = str(entry.get("sha256", ""))
        blob = path / ATTACHMENTS_DIR / digest[:2] / digest
        if not blob.is_file():
            raise BackupError(f"{path}: attachment {digest} is missing")
        if blob.stat().st_size != int(entry.get("bytes", -1)):
            raise BackupError(f"{path}: attachment {digest} is the wrong size")
    # Absent from a version-1 manifest, so this is a no-op restoring one — the
    # version's own covers.tar.gz already has its checksum verified above.
    for entry in manifest.get("covers", []):
        name = str(entry.get("name", ""))
        cover = path / "covers" / name
        if not cover.is_file():
            raise BackupError(f"{path}: cover {name} is missing")
        if cover.stat().st_size != int(entry.get("bytes", -1)):
            raise BackupError(f"{path}: cover {name} is the wrong size")
    _check_integrity(path / DATABASE_NAME)
    return manifest


def restore_backup(path: Path, *, into: Path) -> dict[str, Any]:
    """Restore a verified backup into an empty directory.

    Version 1 backups (Sprint 060 and earlier) archived `covers/` and `imports/`
    as tarballs; version 2 shares covers by hardlink or plain copy and does not
    archive `imports/` at all (DEC-124). Both restore correctly — this is the
    read side of that format change, and it is what the old-version fixture in
    `tests/fixtures/backup-v1/` proves against a real backup rather than a
    hand-edited manifest.
    """
    manifest = verify_backup(path)
    if into.exists() and any(into.iterdir()):
        raise BackupError(f"{into} is not empty; restore into an empty directory")
    into.mkdir(parents=True, exist_ok=True)
    (into / DATABASE_NAME).write_bytes((path / DATABASE_NAME).read_bytes())
    if manifest.get("version", 1) == 1:
        for directory in ARCHIVED_DIRECTORIES:
            target = into / directory
            target.mkdir(exist_ok=True)
            with tarfile.open(path / f"{directory}.tar.gz", "r:gz") as archive:
                # `data` refuses absolute paths, `..` and special files, so a
                # tampered archive cannot write outside the directory being restored.
                archive.extractall(target, filter="data")
    else:
        (into / "imports").mkdir(exist_ok=True)
        source = path / "covers"
        if source.is_dir():
            for cover in sorted(source.iterdir()):
                if cover.is_file():
                    destination = into / "covers" / cover.name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(cover.read_bytes())
    source = path / ATTACHMENTS_DIR
    if source.is_dir():
        for blob in sorted(source.rglob("*")):
            if blob.is_file():
                destination = into / ATTACHMENTS_DIR / blob.relative_to(source)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(blob.read_bytes())
    return manifest


def enforce_retention(dest: Path, *, keep: int, label: str) -> list[Path]:
    """Delete the oldest backups carrying `label` beyond `keep`. Returns what went."""
    if keep < 0:
        raise BackupError("keep must not be negative")
    if not dest.is_dir():
        return []
    owned = []
    for candidate in dest.iterdir():
        manifest = read_manifest(candidate) if candidate.is_dir() else None
        if manifest is not None and manifest.get("label") == label:
            owned.append((str(manifest.get("created_at", "")), candidate))
    owned.sort()
    doomed = [path for _, path in owned[: max(len(owned) - keep, 0)]]
    for path in doomed:
        rmtree(path)
    return doomed


@dataclass(frozen=True)
class PreMigrationBackup:
    """One `pre-migration` backup, with what an operator needs to decide about it."""

    name: str
    path: Path
    revision: str | None
    created_at: str
    bytes: int


@dataclass(frozen=True)
class PrunePreMigrationReport:
    """What the prune did or would do. `kept` and `not_found` explain a refusal —
    reading the report has to be enough to know why a name did not go, the same as
    `reclaim.py`'s report is enough to know why a blob was not."""

    applied: bool
    deleted: tuple[str, ...] = ()
    kept: tuple[tuple[str, str], ...] = ()  # (name, reason)
    not_found: tuple[str, ...] = ()


def _directory_bytes(path: Path) -> int:
    return sum(entry.stat().st_size for entry in path.rglob("*") if entry.is_file())


def list_pre_migration_backups(
    dest: Path, *, now: datetime | None = None
) -> list[PreMigrationBackup]:
    """Every `pre-migration` backup under `dest`, newest first."""
    if not dest.is_dir():
        return []
    found: list[PreMigrationBackup] = []
    for candidate in dest.iterdir():
        manifest = read_manifest(candidate) if candidate.is_dir() else None
        if manifest is None or manifest.get("label") != "pre-migration":
            continue
        found.append(
            PreMigrationBackup(
                name=candidate.name,
                path=candidate,
                revision=manifest.get("alembic_revision"),
                created_at=str(manifest.get("created_at", "")),
                bytes=_directory_bytes(candidate),
            )
        )
    return sorted(found, key=lambda backup: backup.created_at, reverse=True)


def prune_pre_migration(
    dest: Path,
    names: Sequence[str],
    *,
    apply: bool = False,
    current_revision: str | None = None,
) -> PrunePreMigrationReport:
    """Delete named `pre-migration` backups, refusing the two DEC-039 must protect.

    Never called from `create_backup`, `enforce_retention` or startup -- this is the
    one place in the codebase that may delete a migration rollback point, and it only
    ever acts on backups an operator named, never a schedule or a threshold.
    """
    backups = list_pre_migration_backups(dest)
    if not backups:
        return PrunePreMigrationReport(applied=apply)
    by_name = {backup.name: backup for backup in backups}
    newest_name = backups[0].name  # list_pre_migration_backups sorts newest first

    deleted: list[str] = []
    kept: list[tuple[str, str]] = []
    not_found: list[str] = []
    for name in names:
        backup = by_name.get(name)
        if backup is None:
            not_found.append(name)
            continue
        if name == newest_name:
            kept.append((name, "newest pre-migration backup"))
            continue
        if current_revision is not None and backup.revision == current_revision:
            kept.append((name, f"matches the current schema revision ({current_revision})"))
            continue
        if apply:
            rmtree(backup.path)
        deleted.append(name)
    return PrunePreMigrationReport(
        applied=apply, deleted=tuple(deleted), kept=tuple(kept), not_found=tuple(not_found)
    )


def read_manifest(path: Path) -> dict[str, Any] | None:
    """The manifest is what marks a directory as ours; anything else is left alone."""
    try:
        decoded = json.loads((path / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(decoded, dict) or decoded.get("kind") != MANIFEST_KIND:
        return None
    return decoded


def _copy_database(source_path: Path, target_path: Path) -> dict[str, int]:
    source = sqlite3.connect(source_path)
    target = sqlite3.connect(target_path)
    try:
        source.backup(target)
        # The copy inherits WAL from the source. Switching it to a rollback
        # journal leaves exactly one file on disk, so the artifact cannot be
        # restored while silently missing a sidecar.
        target.execute("PRAGMA journal_mode=DELETE")
        target.commit()
        counts = {
            table: int(target.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
            for table in ("items", "entries", "shelves")
        }
    except sqlite3.DatabaseError as error:
        raise BackupError(f"Could not copy the database: {error}") from error
    finally:
        target.close()
        source.close()
    return counts


def _share_covers(data_dir: Path, backup_path: Path) -> list[dict[str, Any]]:
    """Hardlink each cover from the live store; copy fresh bytes if that fails.

    Extends DEC-047's attachment-sharing trick to covers (Sprint 060), with one
    deliberate difference: **no sibling-backup fallback tier**. `_share_attachments`
    falls back to linking from a sibling backup when linking from the live store
    fails (`EXDEV` — /data and /backups on separate filesystems, which DEC-040
    recommends), and that is safe there only because an attachment is
    content-addressed: the same digest guarantees the same bytes in every backup
    that has ever linked it. A cover has no such guarantee — `install_cover` and
    `prepare_uploaded_cover`/`prepare_cover` replace it in place by digest-less
    filename (`covers/<item_id>.jpg`), so a sibling backup's copy could be stale
    if the cover changed since that backup ran. Reading fresh from the live store
    (or copying it when a link is not possible) is what keeps this backup's covers
    correct regardless of what any sibling holds; the cost is that the
    cross-filesystem deployment shares nothing between backups for covers
    specifically, which is no worse than every backup before this sprint archived
    a fresh tarball of all of them regardless.
    """
    source = data_dir / "covers"
    recorded: list[dict[str, Any]] = []
    if not source.is_dir():
        return recorded
    for cover in sorted(source.iterdir()):
        if not cover.is_file():
            continue
        target = backup_path / "covers" / cover.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not _link_from(cover, target):
            target.write_bytes(cover.read_bytes())
        recorded.append({"name": cover.name, "bytes": target.stat().st_size})
    return recorded


def _share_attachments(data_dir: Path, backup_path: Path, dest: Path) -> list[dict[str, Any]]:
    """Hardlink every blob in the live store into this backup, twice-fallback.

    A blob named for its own digest can never change, so sharing an inode is
    always safe, and sharing is the difference DEC-047 measured between 10.5x the
    current backup and 67.9x.

    Two sources are tried, and the second one is not an optimisation -- it is what
    makes this work at all in the deployment we actually ship. The container
    mounts `/data` and `/backups` as separate volumes, so linking from the live
    store fails `EXDEV` every single time, and the first version of this silently
    wrote a full copy on every nightly run. Sprint 021's walkthrough caught it;
    no test could, because they all run inside one filesystem.

    So: link from the live store when they share a filesystem, otherwise link
    from a sibling backup that already carries the blob -- backups are always on
    one filesystem with each other -- and only copy when neither is possible,
    which is a genuinely cold first backup on a separate disk.

    Not compressed and not tarred, because a tar shares nothing with the tar
    written the night before, which is exactly what makes the naive design cost
    seven copies.
    """
    source = data_dir / ATTACHMENTS_DIR
    recorded: list[dict[str, Any]] = []
    if not source.is_dir():
        return recorded
    siblings = _existing_backups(dest, exclude=backup_path)
    for blob in sorted(source.rglob("*")):
        if not blob.is_file():
            continue
        relative = blob.relative_to(source)
        target = backup_path / ATTACHMENTS_DIR / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not _link_from(blob, target):
            for sibling in siblings:
                candidate = sibling / ATTACHMENTS_DIR / relative
                if candidate.is_file() and _link_from(candidate, target):
                    break
            else:
                target.write_bytes(blob.read_bytes())
        recorded.append({"sha256": blob.name, "bytes": target.stat().st_size})
    return recorded


def _link_from(source: Path, target: Path) -> bool:
    try:
        os.link(source, target)
    except OSError:
        return False
    return True


def _existing_backups(dest: Path, *, exclude: Path) -> list[Path]:
    """Our own backups under `dest`, newest first.

    Only directories carrying an Akasha manifest, for the same reason retention
    only deletes those: `dest` is an operator-supplied path and may hold anything.
    """
    if not dest.is_dir():
        return []
    found: list[tuple[str, Path]] = []
    for candidate in dest.iterdir():
        if candidate == exclude or not candidate.is_dir():
            continue
        manifest = read_manifest(candidate)
        if manifest is not None:
            found.append((str(manifest.get("created_at", "")), candidate))
    return [path for _, path in sorted(found, reverse=True)]


def _revision(database_path: Path) -> str | None:
    connection = sqlite3.connect(database_path)
    try:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    except sqlite3.DatabaseError:
        return None
    finally:
        connection.close()
    return str(row[0]) if row else None


def _check_integrity(database_path: Path) -> None:
    connection = sqlite3.connect(database_path)
    try:
        rows = connection.execute("PRAGMA integrity_check").fetchall()
    except sqlite3.DatabaseError as error:
        raise BackupError(f"{database_path} failed its integrity check: {error}") from error
    finally:
        connection.close()
    reported = [str(row[0]) for row in rows]
    if reported != ["ok"]:
        raise BackupError(f"{database_path} failed its integrity check: {'; '.join(reported)}")


def _megabytes(value: int) -> str:
    return f"{value / (1024 * 1024):.1f} MB"


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _write_checksums(path: Path, names: list[str]) -> None:
    lines = [f"{_digest(path / name)}  {name}" for name in names]
    (path / CHECKSUM_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_checksums(path: Path) -> dict[str, str]:
    try:
        raw = (path / CHECKSUM_NAME).read_text(encoding="utf-8")
    except OSError:
        return {}
    recorded = {}
    for line in raw.splitlines():
        if "  " in line:
            digest, name = line.split("  ", 1)
            recorded[name] = digest
    return recorded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m book_tracker.backup", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="take a backup from a running instance")
    create.add_argument("--data-dir", type=Path, default=Path("/data"))
    create.add_argument("--dest", type=Path, default=Path("/backups"))
    create.add_argument("--label", default="nightly")
    create.add_argument("--keep", type=int, default=7, help="0 disables retention")
    create.add_argument(
        "--min-free-bytes",
        type=int,
        default=500 * 1024 * 1024,
        help="refuse to start a backup below this much free space on --dest (0 disables the check)",
    )

    check = commands.add_parser("verify", help="re-check checksums and database integrity")
    check.add_argument("path", type=Path)

    restore = commands.add_parser("restore", help="restore into an empty directory")
    restore.add_argument("path", type=Path)
    restore.add_argument("--into", type=Path, required=True)

    prune = commands.add_parser(
        "prune-pre-migration",
        help="list, or delete named, pre-migration backups (DEC-039: never automatic)",
    )
    prune.add_argument("--dest", type=Path, default=Path("/backups"))
    prune.add_argument("--data-dir", type=Path, default=Path("/data"))
    prune.add_argument(
        "names", nargs="*", help="backup directory names to delete; omit to only list"
    )
    prune.add_argument(
        "--apply", action="store_true", help="actually delete; without this, only report"
    )

    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            result = create_backup(
                database_path=args.data_dir / DATABASE_NAME,
                data_dir=args.data_dir,
                dest=args.dest,
                label=args.label,
                min_free_bytes=args.min_free_bytes or None,
            )
            print(f"Backup written to {result.path}")
            print(json.dumps(result.manifest["counts"], sort_keys=True))
            if args.keep > 0:
                for removed in enforce_retention(args.dest, keep=args.keep, label=args.label):
                    print(f"Retention removed {removed}")
        elif args.command == "verify":
            manifest = verify_backup(args.path)
            print(f"{args.path} verified: revision {manifest.get('alembic_revision')}")
        elif args.command == "restore":
            restore_backup(args.path, into=args.into)
            print(f"Restored {args.path} into {args.into}")
        else:
            backups = list_pre_migration_backups(args.dest)
            if not backups:
                print(f"No pre-migration backups under {args.dest}")
                return 0
            current_revision = _revision(args.data_dir / DATABASE_NAME)
            print(f"{'name':<32}{'revision':<16}{'created_at':<26}{'size'}")
            for backup in backups:
                flags = []
                if backup is backups[0]:
                    flags.append("newest")
                if current_revision is not None and backup.revision == current_revision:
                    flags.append("current revision")
                suffix = f"  ({', '.join(flags)})" if flags else ""
                print(
                    f"{backup.name:<32}{backup.revision or '?':<16}{backup.created_at:<26}"
                    f"{_megabytes(backup.bytes)}{suffix}"
                )
            if not args.names:
                print("\nNo names given: nothing deleted. Name backups above to prune them.")
                return 0
            report = prune_pre_migration(
                args.dest, args.names, apply=args.apply, current_revision=current_revision
            )
            print()
            verb = "Deleted" if report.applied else "Would delete"
            for name in report.deleted:
                print(f"{verb}: {name}")
            for name, reason in report.kept:
                print(f"Refused (kept): {name} — {reason}")
            for name in report.not_found:
                print(f"Not found, skipped: {name}", file=sys.stderr)
            if not report.applied and report.deleted:
                print("\nNothing was deleted. Re-run with --apply to prune.")
    except (BackupError, InsufficientDiskSpace) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
