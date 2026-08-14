#!/usr/bin/env python3
"""Measure what attaching files to items would cost, chiefly against backups.

Sprint 021, Phase A. The gate this feeds asks whether attachments are affordable,
and DEC-040 makes that a backup question before it is anything else:
`ARCHIVED_DIRECTORIES = ("covers", "imports")` tars everything into every backup,
seven nightly deep. A cover measured **38.8 KB** (DEC-044). An epub is 1-5 MB. The
naive extension of today's design therefore multiplies the nightly corpus by
roughly two orders of magnitude, and the owner's disk pays for it.

**This script does not pick a strategy.** It costs seven of them side by side so
the owner chooses between numbers rather than between opinions, which is the whole
point of a gate. What each strategy *loses* is reported next to what it saves,
because F and G buy their savings with a weaker recovery promise and that trade
must be visible rather than buried.

Two measurements are easy to get quietly wrong and are pinned by
`backend/tests/test_attachment_cost.py`:

- Disk accounting counts **unique inodes**, so a hardlinked file is counted once.
  Summing `st_size` would report strategy E's naive cost as if it were its clever
  one, which is the exact mistake the strategy exists to avoid.
- The generated corpus is **incompressible**, because a real epub is a ZIP. A
  compressible stand-in would make every `tar.gz` number optimistic.

The real `create_backup` / `restore_backup` are called rather than reimplemented,
so the existing path is exercised as it actually ships. The attachment payload is
added alongside, which is what a Phase B implementation would do; strategy A is
byte-equivalent to appending `"attachments"` to `ARCHIVED_DIRECTORIES`, since it
tars the same files with the same settings.

Run from `backend/` so the package resolves:

    cd backend && UV_CACHE_DIR=/tmp/akasha-uv-cache \\
      uv run python ../scripts/assess_attachment_cost.py --counts 100,300

Nothing here touches the real database, the real data directory, or the network.
Every cell builds a throwaway library under a temporary directory and deletes it
once measured, so peak disk is about two backups of the largest cell.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import time
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

BACKEND_SRC = Path(__file__).resolve().parents[1] / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from book_tracker.backup import create_backup, restore_backup  # noqa: E402

# Deliberately *not* "attachments". Strategy E shipped (DEC-048), so the real
# `create_backup` now shares blobs out of `data/attachments` by itself. This script
# has to keep modelling all seven strategies against each other to stay useful on a
# revisit, so it keeps its corpus and its payload under names the shipped backup
# ignores. What it measures is therefore still a clean comparison of hypotheticals.
CORPUS_DIR = "assess-corpus"
PAYLOAD_DIR = "assess-payload"
ATTACHMENT_MANIFEST = "assess-attachments.json"
ATTACHMENT_ARCHIVE = "assess-attachments.tar.gz"
# 25 MB admits an epub, a PDF scan and a comic issue while refusing an audiobook or a
# video rip, which are the things that turn this feature into a media server. Used by
# strategy B; the real value is Phase B's to set once the owner has chosen a strategy.
DEFAULT_CAP_BYTES = 25 * 1024 * 1024


@dataclass(frozen=True)
class Strategy:
    """One way to store attachments and carry them through the backup window.

    `retained_copies` is how many copies of the attachment corpus survive inside a
    seven-night retention window. It is the strategy's definition, not a measurement;
    everything multiplied by it *is* measured.
    """

    key: str
    name: str
    payload: str  # "tar" | "loose" | "link" | "none"
    retained_copies: int
    cap_bytes: int | None
    loses: str


STRATEGIES: list[Strategy] = [
    Strategy(
        key="A",
        name="In the tar, every nightly backup (status quo extended)",
        payload="tar",
        retained_copies=7,
        cap_bytes=None,
        loses="nothing — this is the full-fidelity baseline everything else is measured against",
    ),
    Strategy(
        key="B",
        name="Size cap only",
        payload="tar",
        retained_copies=7,
        cap_bytes=DEFAULT_CAP_BYTES,
        loses="files over the cap cannot be attached at all; the total is still unbounded",
    ),
    Strategy(
        key="C",
        name="Separate backup label, its own shallower retention",
        payload="tar",
        retained_copies=2,
        cap_bytes=DEFAULT_CAP_BYTES,
        loses="an attachment deleted more than two nights ago is gone for good",
    ),
    Strategy(
        key="D",
        name="Own cadence — attachments backed up weekly, not nightly",
        payload="tar",
        retained_copies=1,
        cap_bytes=DEFAULT_CAP_BYTES,
        loses="up to a week of newly attached files, though originals are usually still upstream",
    ),
    Strategy(
        key="E",
        name="Loose content-addressed store, deduplicated across backups",
        payload="link",
        retained_copies=7,
        cap_bytes=DEFAULT_CAP_BYTES,
        loses="nothing in fidelity; needs one filesystem, so it degrades to full copies on a NAS",
    ),
    Strategy(
        key="F",
        name="Excluded from the backup; manifest records names and checksums",
        payload="none",
        retained_copies=0,
        cap_bytes=DEFAULT_CAP_BYTES,
        loses="the attachment bytes themselves — a restore names them but cannot bring them back",
    ),
    Strategy(
        key="G",
        name="Calibre reference — no copy is ever made",
        payload="none",
        retained_copies=0,
        cap_bytes=None,
        loses="everything not already in Calibre, and every file if the Calibre library moves",
    ),
]


@dataclass(frozen=True)
class Measurement:
    strategy_key: str
    strategy_name: str
    count: int
    size_bytes: int
    first_backup_path: Path
    raw_attachment_bytes: int
    base_bytes: int
    attachment_bytes: int
    first_backup_bytes: int
    incremental_bytes: int
    dedup_factor: float
    attachment_copies: float
    attachment_window_bytes: int
    window_bytes: int
    compression_ratio: float
    backup_seconds: float
    restore_seconds: float
    loses: str

    def as_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["first_backup_path"] = str(self.first_backup_path)
        return payload


@dataclass(frozen=True)
class RestoreOutcome:
    database_path: Path
    attachments_dir: Path
    missing: list[str] = field(default_factory=list)


def disk_usage(path: Path) -> int:
    """Bytes on disk under `path`, counting each inode exactly once.

    Hardlinks are the mechanism strategy E uses to stop the seventh nightly copy of
    an unchanging corpus from costing anything, so an accounting that summed
    `st_size` per directory entry would report the saving as if it had not happened.
    """
    seen: set[tuple[int, int]] = set()
    total = 0
    for entry in path.rglob("*"):
        if not entry.is_file() or entry.is_symlink():
            continue
        stat = entry.stat()
        key = (stat.st_dev, stat.st_ino)
        if key in seen:
            continue
        seen.add(key)
        total += stat.st_size
    return total


def make_corpus(directory: Path, *, count: int, size_bytes: int, seed: int = 0) -> list[Path]:
    """Write `count` epub-shaped files of about `size_bytes` each.

    A real epub is a ZIP whose entries are already deflated, so it does not compress
    again. These are ZIP containers holding *stored* random bytes, which reproduces
    that property exactly. Using compressible filler here would quietly halve every
    `tar.gz` figure this script reports.
    """
    directory.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    written = []
    for index in range(count):
        target = directory / f"{index:05d}.epub"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr("OEBPS/content.bin", rng.randbytes(max(size_bytes - 256, 1)))
        written.append(target)
    return written


def admitted_by_cap(sizes: list[int], *, cap: int) -> list[int]:
    """Which files a size cap lets in. The boundary is inclusive.

    Stated as its own function because Phase B inherits the rule, and an off-by-one
    at the boundary is the classic way a cap becomes untestable folklore.
    """
    return [size for size in sizes if size <= cap]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _attachment_inventory(source: Path, *, cap: int | None) -> list[dict[str, Any]]:
    """Name, size and checksum for every attachment a strategy would admit."""
    inventory = []
    for entry in sorted(source.rglob("*")):
        if not entry.is_file():
            continue
        size = entry.stat().st_size
        if cap is not None and size > cap:
            continue
        inventory.append(
            {"name": str(entry.relative_to(source)), "bytes": size, "sha256": _sha256(entry)}
        )
    return inventory


def _write_attachment_payload(
    strategy: Strategy, source: Path, backup_path: Path, previous: Path | None
) -> None:
    """Add this strategy's attachment payload to a backup that already exists.

    Every strategy writes the manifest, including the two that carry no bytes. That
    is deliberate and is the recommendation this script makes regardless of which
    strategy wins: a restore that hands back fewer files than the operator expected
    must be able to say which ones, or the gap is discovered the day it matters.
    """
    inventory = _attachment_inventory(source, cap=strategy.cap_bytes)
    (backup_path / ATTACHMENT_MANIFEST).write_text(
        json.dumps({"payload": strategy.payload, "files": inventory}, indent=2) + "\n",
        encoding="utf-8",
    )
    admitted = {item["name"] for item in inventory}
    if strategy.payload == "none":
        return
    if strategy.payload == "tar":
        # Mirrors `backup._archive`: an explicit sorted walk with `recursive=False`,
        # so the archive is byte-stable and nothing is added twice.
        with tarfile.open(backup_path / ATTACHMENT_ARCHIVE, "w:gz") as archive:
            for entry in sorted(source.rglob("*")):
                name = str(entry.relative_to(source))
                if entry.is_file() and name in admitted:
                    archive.add(entry, arcname=name, recursive=False)
        return
    target = backup_path / PAYLOAD_DIR
    target.mkdir(parents=True, exist_ok=True)
    for entry in sorted(source.rglob("*")):
        name = str(entry.relative_to(source))
        if not entry.is_file() or name not in admitted:
            continue
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        earlier = previous / PAYLOAD_DIR / name if previous is not None else None
        if (
            strategy.payload == "link"
            and earlier is not None
            and earlier.is_file()
            and earlier.stat().st_size == entry.stat().st_size
        ):
            # Content-addressed in effect: the bytes did not change, so the new
            # backup points at the copy the previous one already paid for.
            try:
                os.link(earlier, destination)
                continue
            except OSError:
                # Different filesystem — DEC-040 explicitly allows BACKUP_DIR on a
                # NAS share, where this degrades to a full copy rather than failing.
                pass
        shutil.copy2(entry, destination)


def _payload_bytes(strategy: Strategy, backup_path: Path) -> int:
    if strategy.payload == "tar":
        archive = backup_path / ATTACHMENT_ARCHIVE
        return archive.stat().st_size if archive.is_file() else 0
    loose = backup_path / PAYLOAD_DIR
    return disk_usage(loose) if loose.is_dir() else 0


def measure_strategy(
    strategy: Strategy, *, data_dir: Path, dest: Path, keep: int = 7
) -> Measurement:
    """Take two real backups under this strategy and report what they cost.

    Two, not seven. The second one is what makes the window number a measurement
    rather than an assumption: for a full-copy strategy it reproduces the first, and
    for a deduplicating one it reveals how little a repeat actually costs. The window
    is then `base x keep + attachments x copies`, where every factor but `keep` and
    `retained_copies` came off the disk.
    """
    dest.mkdir(parents=True, exist_ok=True)
    source = data_dir / CORPUS_DIR
    raw_attachment_bytes = disk_usage(source) if source.is_dir() else 0

    started = time.perf_counter()
    first = create_backup(
        database_path=data_dir / "books.db", data_dir=data_dir, dest=dest, label="nightly"
    )
    _write_attachment_payload(strategy, source, first.path, previous=None)
    backup_seconds = time.perf_counter() - started

    first_backup_bytes = disk_usage(first.path)
    attachment_bytes = _payload_bytes(strategy, first.path)
    base_bytes = first_backup_bytes - attachment_bytes

    before_second = disk_usage(dest)
    second = create_backup(
        database_path=data_dir / "books.db",
        data_dir=data_dir,
        dest=dest,
        label="nightly-second",
    )
    _write_attachment_payload(strategy, source, second.path, previous=first.path)
    incremental_bytes = disk_usage(dest) - before_second
    second_attachment_bytes = max(incremental_bytes - base_bytes, 0)

    dedup_factor = (second_attachment_bytes / attachment_bytes) if attachment_bytes else 0.0
    copies = 1 + (strategy.retained_copies - 1) * dedup_factor if strategy.retained_copies else 0.0
    attachment_window_bytes = round(attachment_bytes * copies)

    into = dest.parent / f"restore-probe-{strategy.key}"
    shutil.rmtree(into, ignore_errors=True)
    started = time.perf_counter()
    restore_strategy(strategy, first.path, into=into)
    restore_seconds = time.perf_counter() - started
    shutil.rmtree(into, ignore_errors=True)
    shutil.rmtree(second.path, ignore_errors=True)

    return Measurement(
        strategy_key=strategy.key,
        strategy_name=strategy.name,
        count=len(list(source.glob("*"))) if source.is_dir() else 0,
        size_bytes=raw_attachment_bytes // max(len(list(source.glob("*"))), 1)
        if source.is_dir()
        else 0,
        first_backup_path=first.path,
        raw_attachment_bytes=raw_attachment_bytes,
        base_bytes=base_bytes,
        attachment_bytes=attachment_bytes,
        first_backup_bytes=first_backup_bytes,
        incremental_bytes=incremental_bytes,
        dedup_factor=dedup_factor,
        attachment_copies=copies,
        attachment_window_bytes=attachment_window_bytes,
        window_bytes=base_bytes * keep + attachment_window_bytes,
        compression_ratio=(attachment_bytes / raw_attachment_bytes)
        if raw_attachment_bytes
        else 0.0,
        backup_seconds=backup_seconds,
        restore_seconds=restore_seconds,
        loses=strategy.loses,
    )


def restore_strategy(strategy: Strategy, backup_path: Path, *, into: Path) -> RestoreOutcome:
    """Restore a backup and report which attachments did not come back with it."""
    restore_backup(backup_path, into=into)
    attachments = into / PAYLOAD_DIR
    attachments.mkdir(parents=True, exist_ok=True)
    try:
        manifest = json.loads((backup_path / ATTACHMENT_MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return RestoreOutcome(database_path=into / "books.db", attachments_dir=attachments)

    expected = [str(item["name"]) for item in manifest.get("files", [])]
    if strategy.payload == "tar":
        archive_path = backup_path / ATTACHMENT_ARCHIVE
        if archive_path.is_file():
            with tarfile.open(archive_path, "r:gz") as archive:
                archive.extractall(attachments, filter="data")
    elif strategy.payload in {"loose", "link"}:
        stored = backup_path / PAYLOAD_DIR
        if stored.is_dir():
            for entry in sorted(stored.rglob("*")):
                if entry.is_file():
                    destination = attachments / entry.relative_to(stored)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(entry, destination)

    missing = [name for name in expected if not (attachments / name).is_file()]
    return RestoreOutcome(
        database_path=into / "books.db", attachments_dir=attachments, missing=missing
    )


def _throwaway_library(root: Path, *, count: int, size_bytes: int) -> Path:
    """The smallest database that makes a backup realistic, plus a corpus.

    A schema is not created through Alembic here: the assessment is about bytes and
    wall time, and `create_backup` only needs a valid SQLite file with rows in it.
    """
    data_dir = root / "data"
    for directory in ("", "covers", "imports"):
        (data_dir / directory).mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(data_dir / "books.db")
    try:
        connection.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, title TEXT)")
        connection.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY, score INTEGER)")
        connection.execute("CREATE TABLE shelves (id INTEGER PRIMARY KEY, name TEXT)")
        connection.executemany(
            "INSERT INTO items (title) VALUES (?)", [(f"Book {i}",) for i in range(count or 1)]
        )
        connection.commit()
    finally:
        connection.close()
    # A cover per book at the 38.8 KB mean DEC-044 measured, so the baseline the
    # attachment numbers are compared against is the real one.
    for index in range(count or 1):
        (data_dir / "covers" / f"{index}.jpg").write_bytes(random.Random(index).randbytes(38_800))
    make_corpus(data_dir / CORPUS_DIR, count=count, size_bytes=size_bytes, seed=99)
    return data_dir


def _human(value: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--counts",
        default="100,300",
        help="attachment counts to measure, comma separated (default 100,300)",
    )
    parser.add_argument(
        "--size-mb", type=float, default=2.5, help="mean attachment size in MB (default 2.5)"
    )
    parser.add_argument("--keep", type=int, default=7, help="nightly retention depth (DEC-040)")
    parser.add_argument("--json", type=Path, default=None, help="write full results here")
    args = parser.parse_args(argv)

    counts = [int(value) for value in args.counts.split(",") if value.strip()]
    size_bytes = int(args.size_mb * 1024 * 1024)
    results: list[dict[str, Any]] = []

    for count in counts:
        print(f"\n{'=' * 96}")
        print(f"{count} attachments x {args.size_mb} MB, {args.keep}-night retention window")
        print("=" * 96)
        header = f"{'':2} {'strategy':52} {'per backup':>12} {'7-night window':>15}"
        print(header)
        print("-" * 96)
        with tempfile.TemporaryDirectory(prefix="akasha-attachment-cost-") as raw_root:
            root = Path(raw_root)
            data_dir = _throwaway_library(root, count=count, size_bytes=size_bytes)
            for strategy in STRATEGIES:
                dest = root / f"backups-{strategy.key}"
                measured = measure_strategy(strategy, data_dir=data_dir, dest=dest, keep=args.keep)
                results.append(measured.as_json())
                print(
                    f"{strategy.key:2} {strategy.name[:52]:52}"
                    f"{_human(measured.first_backup_bytes):>12}"
                    f"{_human(measured.window_bytes):>15}"
                )
                shutil.rmtree(dest, ignore_errors=True)
            print("-" * 96)
            for strategy in STRATEGIES:
                print(f"{strategy.key:2} loses: {strategy.loses}")

    print(f"\n{'=' * 96}")
    print("Detail")
    print("=" * 96)
    for row in results:
        print(
            f"{row['strategy_key']}  n={row['count']:<5} "
            f"raw {_human(row['raw_attachment_bytes']):>10}  "
            f"stored {_human(row['attachment_bytes']):>10}  "
            f"gzip ratio {row['compression_ratio']:.3f}  "
            f"copies {row['attachment_copies']:.2f}  "
            f"backup {row['backup_seconds']:.2f}s  restore {row['restore_seconds']:.2f}s"
        )

    if args.json:
        args.json.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
