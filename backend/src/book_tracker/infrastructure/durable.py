"""Files that reach the disk before the row that names them (Sprint 129).

A blob is written to a temporary, moved into place with `os.replace`, and then the
database commits the row that points at it — and SQLite fsyncs that commit. Without
an fsync of our own, ext4 can lose power with the row durable and the blob
zero-length. So the bytes are synced before the rename, and the directory after it,
so the rename itself survives too.
"""

import os
from pathlib import Path


def fsync_file(path: Path) -> None:
    """Flush a written file's bytes to the disk."""
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def fsync_directory(path: Path) -> None:
    """Flush a directory's entries, so a rename into it survives power loss.

    Best effort: a platform that cannot open a directory (Windows) has nothing to
    sync this way, and the move has already happened.
    """
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)
