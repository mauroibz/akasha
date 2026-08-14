"""The content-addressed attachment store (DEC-048).

Addressing blobs by digest is not a storage detail here, it is the security
boundary: a user-supplied filename never becomes a path component, so traversal
is answered by the design rather than by a filter that has to be right every
time. These tests hold that property in place, along with the refcount that
stops one item's delete from destroying another item's file.
"""

import os
import tracemalloc
from pathlib import Path

import pytest

from book_tracker.infrastructure.attachments import (
    AttachmentError,
    AttachmentTooLarge,
    BlobWriter,
    blob_path,
    delete_blob_if_unreferenced,
    store_blob,
)

CONTENT = b"not really an epub, but bytes that must survive a round trip"
DIGEST = "e6b1f2ab7c6a49dcb96b40b9a5b4a5ad3f9d0f6b0f5bd0bb4a4bd2b7c7f0b2fa"


def test_a_blob_is_stored_under_its_own_digest(tmp_path: Path) -> None:
    stored = store_blob(CONTENT, tmp_path)

    assert stored.byte_size == len(CONTENT)
    assert len(stored.sha256) == 64
    assert blob_path(tmp_path, stored.sha256).read_bytes() == CONTENT
    # Fanned out by the first two hex characters: a single flat directory holding
    # thousands of files is slow to walk on the filesystems this ships to.
    assert blob_path(tmp_path, stored.sha256).parent.name == stored.sha256[:2]


def test_the_same_bytes_stored_twice_occupy_one_blob(tmp_path: Path) -> None:
    """Attach the same epub to three items and it is on disk once (DEC-048)."""
    first = store_blob(CONTENT, tmp_path)
    second = store_blob(CONTENT, tmp_path)

    assert first.sha256 == second.sha256
    blobs = [path for path in (tmp_path / "attachments").rglob("*") if path.is_file()]
    assert len(blobs) == 1


def test_a_filename_can_never_escape_the_store(tmp_path: Path) -> None:
    """The digest is the path, so the name has nowhere to go.

    This is the property that makes `%2e%2e` uninteresting at this layer: there is
    no code path where a caller-supplied string reaches the filesystem at all.
    """
    stored = store_blob(CONTENT, tmp_path)
    resolved = blob_path(tmp_path, stored.sha256).resolve()

    assert resolved.is_relative_to((tmp_path / "attachments").resolve())


@pytest.mark.parametrize("digest", ["../../etc/passwd", "..", "a/b", "", "zz" * 32, "abc"])
def test_a_digest_that_is_not_a_digest_is_refused(tmp_path: Path, digest: str) -> None:
    with pytest.raises(AttachmentError):
        blob_path(tmp_path, digest)


def test_a_blob_still_referenced_is_not_deleted(tmp_path: Path) -> None:
    stored = store_blob(CONTENT, tmp_path)

    delete_blob_if_unreferenced(tmp_path, stored.sha256, references=1)

    assert blob_path(tmp_path, stored.sha256).is_file()


def test_a_blob_nobody_references_is_deleted(tmp_path: Path) -> None:
    stored = store_blob(CONTENT, tmp_path)

    delete_blob_if_unreferenced(tmp_path, stored.sha256, references=0)

    assert not blob_path(tmp_path, stored.sha256).exists()


def test_deleting_a_blob_that_is_already_gone_is_not_an_error(tmp_path: Path) -> None:
    stored = store_blob(CONTENT, tmp_path)
    delete_blob_if_unreferenced(tmp_path, stored.sha256, references=0)

    delete_blob_if_unreferenced(tmp_path, stored.sha256, references=0)


def test_storing_leaves_no_temporary_file_behind_when_it_fails(tmp_path: Path) -> None:
    """A half-written blob under a digest name would be corruption that verifies."""
    with pytest.raises(AttachmentError):
        store_blob(b"", tmp_path)

    leftovers = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert leftovers == []


def test_a_blob_written_in_chunks_matches_one_written_whole(tmp_path: Path) -> None:
    """The streaming path must land on the same digest, or dedup silently stops working."""
    payload = CONTENT * 500
    whole = store_blob(payload, tmp_path / "whole")

    with BlobWriter(tmp_path / "chunked", max_bytes=len(payload)) as writer:
        for start in range(0, len(payload), 64):
            writer.write(payload[start : start + 64])
        chunked = writer.commit()

    assert chunked.sha256 == whole.sha256
    assert chunked.byte_size == len(payload)
    assert blob_path(tmp_path / "chunked", chunked.sha256).read_bytes() == payload


def test_a_writer_holds_one_chunk_not_the_whole_upload(tmp_path: Path) -> None:
    """The property the streaming change exists for, measured rather than asserted.

    Peak allocation across a 4 MiB upload written 64 KiB at a time, against the
    4 MiB the previous `await file.read(cap + 1)` held in a single string. The
    bound is deliberately loose — this is here to catch a return to buffering the
    whole file, not to pin an allocator.
    """
    chunk = os.urandom(64 * 1024)
    chunks = 64
    chunk_total = len(chunk) * chunks

    tracemalloc.start()
    try:
        before = tracemalloc.get_traced_memory()[0]
        with BlobWriter(tmp_path, max_bytes=chunk_total) as writer:
            for _ in range(chunks):
                writer.write(chunk)
            stored = writer.commit()
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()

    assert stored.byte_size == chunk_total
    assert peak - before < chunk_total // 4


def test_an_upload_past_the_cap_stops_writing_and_leaves_nothing(tmp_path: Path) -> None:
    """Refused as the bytes arrive, not after they have all been held."""
    writer = BlobWriter(tmp_path, max_bytes=100)
    writer.write(b"x" * 90)

    with pytest.raises(AttachmentTooLarge):
        writer.write(b"x" * 20)

    assert not [path for path in (tmp_path / "attachments").rglob("*") if path.is_file()]


def test_an_abandoned_upload_leaves_nothing_behind(tmp_path: Path) -> None:
    """A client that disconnects mid-upload must not cost disk."""
    with BlobWriter(tmp_path, max_bytes=1000) as writer:
        writer.write(b"half an epub")

    assert not [path for path in (tmp_path / "attachments").rglob("*") if path.is_file()]


def test_a_streamed_upload_of_bytes_already_stored_keeps_one_copy(tmp_path: Path) -> None:
    first = store_blob(CONTENT, tmp_path)

    with BlobWriter(tmp_path, max_bytes=len(CONTENT)) as writer:
        writer.write(CONTENT)
        second = writer.commit()

    assert second.sha256 == first.sha256
    blobs = [path for path in (tmp_path / "attachments").rglob("*") if path.is_file()]
    assert len(blobs) == 1


def test_a_streamed_upload_of_nothing_is_refused(tmp_path: Path) -> None:
    with pytest.raises(AttachmentError), BlobWriter(tmp_path, max_bytes=100) as writer:
        writer.commit()
