"""Content-addressed storage for attached files (DEC-048).

A blob lives at `attachments/{sha256[:2]}/{sha256}` and the name the owner
uploaded is held in the database, never on disk. That single choice does four
jobs at once, which is why it was preferred to the obvious
`attachments/{item_id}/{filename}` layout:

- the same file attached to several items is stored once;
- **a user-supplied name never becomes a path component**, so traversal is
  answered by the design instead of by a filter that has to be right every time;
- integrity is free, because the path is the digest;
- a blob that can never change makes the backup's hardlink sharing correct by
  definition rather than by an assumption about immutability.

Deletion is refcounted by the caller, which knows how many rows point at a
digest. This module does not read the database.
"""

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import IO

ATTACHMENTS_DIR = "attachments"
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class AttachmentError(ValueError):
    """A blob could not be stored, or a digest was not a digest."""


class AttachmentTooLarge(AttachmentError):
    """More bytes arrived than the cap allows, and the rest were not read."""


@dataclass(frozen=True)
class StoredBlob:
    sha256: str
    byte_size: int


def blob_path(data_dir: Path, sha256: str) -> Path:
    """Where a digest lives. Rejects anything that is not one.

    The guard is what makes the rest of the module safe to hand a value that came
    off the wire: a path is only ever built from 64 hex characters, so no caller
    can steer it out of the store.
    """
    if not _DIGEST.match(sha256):
        raise AttachmentError("not a sha256 digest")
    return data_dir / ATTACHMENTS_DIR / sha256[:2] / sha256


class BlobWriter:
    """Hash and write an upload a chunk at a time, then move it under its digest.

    Content addressing means the destination is not known until the last byte has
    been hashed, so the bytes land in a temporary beside the store and are moved
    into place at commit. Nothing here ever holds more than one chunk, which is
    the whole point: the alternative read a 25 MiB upload into a 25 MiB string on
    a machine where a cover is 39 KB.

    `os.replace` does the move, so a reader never sees a half-written file under
    a name that claims to be its own checksum. Storing bytes that are already
    there costs nothing beyond dropping the temporary, which is what makes
    deduplication fall out for free.

    The cap is enforced as the bytes arrive rather than after, so an oversized
    upload stops at the first chunk past the limit instead of being buffered in
    full and then refused.
    """

    def __init__(self, data_dir: Path, *, max_bytes: int) -> None:
        self._data_dir = data_dir
        self._max_bytes = max_bytes
        self._hash = hashlib.sha256()
        self._written = 0
        root = data_dir / ATTACHMENTS_DIR
        try:
            root.mkdir(parents=True, exist_ok=True)
            # noqa SIM115: the handle deliberately outlives this call — chunks
            # arrive one await at a time. `BlobWriter` is itself the context
            # manager, and `abort` closes and unlinks on every exit path.
            handle = tempfile.NamedTemporaryFile(  # noqa: SIM115
                dir=root, prefix="upload-", suffix=".tmp", delete=False
            )
        except OSError as error:
            raise AttachmentError("attachment could not be stored") from error
        self._handle: IO[bytes] | None = handle
        # In the store root rather than the digest's own directory, because which
        # directory that is cannot be known yet. `reclaim` recognises the name at
        # any depth, so one left behind by a crash is still collectable.
        self._temporary: Path | None = Path(handle.name)

    def write(self, chunk: bytes) -> None:
        if self._handle is None:
            raise AttachmentError("attachment is no longer being written")
        self._written += len(chunk)
        if self._written > self._max_bytes:
            self.abort()
            raise AttachmentTooLarge(f"attachments are limited to {self._max_bytes} bytes")
        self._hash.update(chunk)
        try:
            self._handle.write(chunk)
        except OSError as error:
            self.abort()
            raise AttachmentError("attachment could not be stored") from error

    def commit(self) -> StoredBlob:
        if self._handle is None or self._temporary is None:
            raise AttachmentError("attachment could not be stored")
        self._handle.close()
        self._handle = None
        if self._written == 0:
            self.abort()
            raise AttachmentError("attachment is empty")
        digest = self._hash.hexdigest()
        target = blob_path(self._data_dir, digest)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_file():
                # These bytes are already stored. Keep the copy that is there and
                # let the temporary go: identical content is one blob (DEC-048).
                self.abort()
                return StoredBlob(sha256=digest, byte_size=target.stat().st_size)
            os.replace(self._temporary, target)
        except OSError as error:
            self.abort()
            raise AttachmentError("attachment could not be stored") from error
        self._temporary = None
        return StoredBlob(sha256=digest, byte_size=self._written)

    def abort(self) -> None:
        """Drop a partial upload. Safe to call twice, and after a commit."""
        if self._handle is not None:
            self._handle.close()
            self._handle = None
        if self._temporary is not None:
            self._temporary.unlink(missing_ok=True)
            self._temporary = None

    def __enter__(self) -> "BlobWriter":
        return self

    def __exit__(self, *_: object) -> None:
        self.abort()


def store_blob(content: bytes, data_dir: Path) -> StoredBlob:
    """Store bytes already in hand. The streaming path is `BlobWriter`."""
    if not content:
        raise AttachmentError("attachment is empty")
    with BlobWriter(data_dir, max_bytes=len(content)) as writer:
        writer.write(content)
        return writer.commit()


def delete_blob_if_unreferenced(data_dir: Path, sha256: str, *, references: int) -> bool:
    """Remove a blob only when nothing points at it any more.

    The refcount is the caller's to supply, because it is a database question.
    Getting this wrong in the other direction is the interesting failure: two
    items attached the same epub, and deleting one of them must not take the
    other's file with it.
    """
    if references > 0:
        return False
    target = blob_path(data_dir, sha256)
    try:
        target.unlink(missing_ok=True)
    except OSError as error:
        raise AttachmentError("attachment could not be deleted") from error
    return True
