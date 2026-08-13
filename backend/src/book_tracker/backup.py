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
"""

import argparse
import hashlib
import json
import sqlite3
import sys
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from shutil import rmtree
from typing import Any

MANIFEST_NAME = "manifest.json"
CHECKSUM_NAME = "checksums.sha256"
DATABASE_NAME = "books.db"
MANIFEST_KIND = "akasha-backup"
MANIFEST_VERSION = 1
ARCHIVED_DIRECTORIES = ("covers", "imports")
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
) -> BackupResult:
    """Write one self-contained backup directory and return where it landed."""
    if not database_path.is_file():
        raise BackupError(f"No database to back up at {database_path}")
    stamp = (now or datetime.now(UTC)).astimezone(UTC)
    path = dest / f"{label}-{stamp.strftime('%Y%m%dT%H%M%SZ')}"
    if path.exists():
        raise BackupError(f"A backup already exists at {path}")
    path.mkdir(parents=True)
    try:
        counts = _copy_database(database_path, path / DATABASE_NAME)
        for directory in ARCHIVED_DIRECTORIES:
            _archive(data_dir / directory, path / f"{directory}.tar.gz")
        counts["covers"] = sum(1 for entry in (data_dir / "covers").glob("*") if entry.is_file())
        archived = [DATABASE_NAME, *(f"{name}.tar.gz" for name in ARCHIVED_DIRECTORIES)]
        manifest: dict[str, Any] = {
            "kind": MANIFEST_KIND,
            "version": MANIFEST_VERSION,
            "label": label,
            "created_at": stamp.isoformat(),
            "alembic_revision": _revision(path / DATABASE_NAME),
            "counts": counts,
            "files": archived,
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
    _check_integrity(path / DATABASE_NAME)
    return manifest


def restore_backup(path: Path, *, into: Path) -> dict[str, Any]:
    """Restore a verified backup into an empty directory."""
    manifest = verify_backup(path)
    if into.exists() and any(into.iterdir()):
        raise BackupError(f"{into} is not empty; restore into an empty directory")
    into.mkdir(parents=True, exist_ok=True)
    (into / DATABASE_NAME).write_bytes((path / DATABASE_NAME).read_bytes())
    for directory in ARCHIVED_DIRECTORIES:
        target = into / directory
        target.mkdir(exist_ok=True)
        with tarfile.open(path / f"{directory}.tar.gz", "r:gz") as archive:
            # `data` refuses absolute paths, `..` and special files, so a tampered
            # archive cannot write outside the directory being restored.
            archive.extractall(target, filter="data")
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


def _archive(source: Path, target: Path) -> None:
    """Walk explicitly and add one entry at a time.

    `TarFile.add` recurses by default, which combined with `rglob` writes every
    nested file twice. Sorting the walk also makes the archive byte-stable, so a
    checksum only changes when the contents do.
    """
    with tarfile.open(target, "w:gz") as archive:
        if source.is_dir():
            for entry in sorted(source.rglob("*")):
                archive.add(entry, arcname=str(entry.relative_to(source)), recursive=False)


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

    check = commands.add_parser("verify", help="re-check checksums and database integrity")
    check.add_argument("path", type=Path)

    restore = commands.add_parser("restore", help="restore into an empty directory")
    restore.add_argument("path", type=Path)
    restore.add_argument("--into", type=Path, required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            result = create_backup(
                database_path=args.data_dir / DATABASE_NAME,
                data_dir=args.data_dir,
                dest=args.dest,
                label=args.label,
            )
            print(f"Backup written to {result.path}")
            print(json.dumps(result.manifest["counts"], sort_keys=True))
            if args.keep > 0:
                for removed in enforce_retention(args.dest, keep=args.keep, label=args.label):
                    print(f"Retention removed {removed}")
        elif args.command == "verify":
            manifest = verify_backup(args.path)
            print(f"{args.path} verified: revision {manifest.get('alembic_revision')}")
        else:
            restore_backup(args.path, into=args.into)
            print(f"Restored {args.path} into {args.into}")
    except BackupError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
