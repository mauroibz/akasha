"""A write that would grow the disk refuses before it starts (Sprint 060).

`shutil.disk_usage` reads the filesystem the given path lives on, so this is
checked once per write attempt at the boundary that is about to spend bytes —
never assumed, never cached, because the free-space number changes underneath
the process whether or not it wrote anything itself.
"""

from __future__ import annotations

import shutil
from pathlib import Path


class InsufficientDiskSpace(OSError):
    """Raised at a write boundary when free space is below the configured minimum.

    Not a `LibraryError`: this module is infrastructure, and some callers
    (`backup.create_backup`, run from a cron entrypoint with no HTTP request in
    sight) have nothing to translate it for. `api/imports.py` and `api/library.py`
    catch it at their own boundary and republish it as a typed response, the same
    way `AttachmentTooLarge` already is.
    """

    def __init__(self, *, free_bytes: int, minimum_bytes: int) -> None:
        self.free_bytes = free_bytes
        self.minimum_bytes = minimum_bytes
        super().__init__(f"only {free_bytes} bytes free, below the minimum of {minimum_bytes}")


def free_bytes(path: Path) -> int:
    """Free space on the filesystem holding `path`, which must already exist."""
    return shutil.disk_usage(path).free


def ensure_free_space(path: Path, minimum: int) -> None:
    """Refuse before a single byte is written, rather than partway through one.

    `path` must exist — call this after `mkdir`-ing the directory a write is
    about to grow, not before, so the check reads the volume actually being
    written to.
    """
    available = free_bytes(path)
    if available < minimum:
        raise InsufficientDiskSpace(free_bytes=available, minimum_bytes=minimum)
