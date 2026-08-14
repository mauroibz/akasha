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

ATTACHMENTS_DIR = "attachments"
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class AttachmentError(ValueError):
    """A blob could not be stored, or a digest was not a digest."""


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


def store_blob(content: bytes, data_dir: Path) -> StoredBlob:
    """Write bytes into the store and return their digest and size.

    Written to a temporary file in the destination directory and moved into place
    with `os.replace`, so a reader never sees a half-written file under a name
    that claims to be its own checksum. Storing the same bytes twice is a no-op
    beyond the move, which is what makes deduplication fall out for free.
    """
    if not content:
        raise AttachmentError("attachment is empty")
    digest = hashlib.sha256(content).hexdigest()
    target = blob_path(data_dir, digest)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        return StoredBlob(sha256=digest, byte_size=target.stat().st_size)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=target.parent, prefix="upload-", suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        os.replace(temporary, target)
        temporary = None
    except OSError as error:
        raise AttachmentError("attachment could not be stored") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return StoredBlob(sha256=digest, byte_size=len(content))


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
