"""Uploading, listing, downloading and deleting attached files (DEC-048).

The download assertions carry most of the weight. Every byte this application
served before now went through the cover pipeline and came back out as a
re-encoded JPEG, so an attachment is the first user-controlled content type to
reach a browser — and it is served from the same origin as the SPA. An uploaded
HTML or SVG opened inline could script the application against its own API, so
`Content-Disposition: attachment`, `nosniff` and a fixed
`application/octet-stream` are load-bearing rather than decorative.
"""

import hashlib
import os
from pathlib import Path

import httpx
import pytest

from book_tracker.api.library import UPLOAD_CHUNK_BYTES
from book_tracker.config import Settings
from book_tracker.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def make_item(client: httpx.AsyncClient, title: str = "Rayuela") -> int:
    created = await client.post(
        "/api/entries", json={"manual": {"title": title}, "idempotency_key": title}
    )
    assert created.status_code in {200, 201}, created.text
    return int(created.json()["entry"]["item_id"])


def app_for(tmp_path: Path, **overrides: object) -> object:
    return create_app(
        Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid", **overrides)
    )


@pytest.mark.anyio
async def test_an_uploaded_file_is_listed_with_its_name_and_size(tmp_path: Path) -> None:
    app = app_for(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        item_id = await make_item(client)

        uploaded = await client.post(
            f"/api/items/{item_id}/attachments",
            files={"file": ("Rayuela.epub", b"epub bytes here", "application/epub+zip")},
        )
        assert uploaded.status_code == 201, uploaded.text

        listed = await client.get(f"/api/items/{item_id}/attachments")
        assert listed.status_code == 200
        rows = listed.json()["attachments"]
        assert len(rows) == 1
        assert rows[0]["filename"] == "Rayuela.epub"
        assert rows[0]["byte_size"] == len(b"epub bytes here")


@pytest.mark.anyio
async def test_a_download_is_forced_to_save_rather_than_render(tmp_path: Path) -> None:
    """The stored-XSS guard: an uploaded page must never execute on our origin."""
    app = app_for(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        item_id = await make_item(client)
        payload = b"<html><script>fetch('/api/entries',{method:'DELETE'})</script></html>"
        uploaded = await client.post(
            f"/api/items/{item_id}/attachments",
            files={"file": ("evil.html", payload, "text/html")},
        )
        attachment_id = uploaded.json()["id"]

        got = await client.get(f"/api/items/{item_id}/attachments/{attachment_id}")

        assert got.status_code == 200
        assert got.content == payload
        assert got.headers["content-type"] == "application/octet-stream"
        assert got.headers["x-content-type-options"] == "nosniff"
        assert got.headers["content-disposition"].startswith("attachment;")
        assert "evil.html" in got.headers["content-disposition"]


@pytest.mark.anyio
async def test_an_attachment_is_not_reachable_through_another_item(tmp_path: Path) -> None:
    app = app_for(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        mine = await make_item(client, "Mine")
        yours = await make_item(client, "Yours")
        uploaded = await client.post(
            f"/api/items/{mine}/attachments",
            files={"file": ("secret.epub", b"secret bytes", "application/epub+zip")},
        )
        attachment_id = uploaded.json()["id"]

        got = await client.get(f"/api/items/{yours}/attachments/{attachment_id}")

        assert got.status_code == 404


@pytest.mark.anyio
@pytest.mark.parametrize("hostile", ["%2e%2e%2f%2e%2e%2fetc%2fpasswd", "..%2fbooks.db", "%2e%2e"])
async def test_a_traversal_attempt_in_the_path_finds_nothing(tmp_path: Path, hostile: str) -> None:
    """Encoded, because httpx normalizes a literal `/../x` to `/x` before sending.

    The obvious test proves the client normalizes and nothing about the server —
    a repeat offender recorded in `docs/agent/HANDOFF.md`.
    """
    app = app_for(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        item_id = await make_item(client)

        got = await client.get(f"/api/items/{item_id}/attachments/{hostile}")

        assert got.status_code in {404, 422}
        assert b"SQLite" not in got.content


@pytest.mark.anyio
async def test_a_filename_that_is_a_path_is_stored_as_a_name_not_a_path(
    tmp_path: Path,
) -> None:
    """The upload's own traversal case: the name is metadata, the digest is the path."""
    app = app_for(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        item_id = await make_item(client)

        uploaded = await client.post(
            f"/api/items/{item_id}/attachments",
            files={"file": ("../../../etc/passwd", b"payload", "application/octet-stream")},
        )

        assert uploaded.status_code == 201
        assert not (tmp_path.parent / "etc").exists()
        blobs = [path for path in (tmp_path / "attachments").rglob("*") if path.is_file()]
        assert len(blobs) == 1
        assert blobs[0].name == blobs[0].parent.parent.joinpath(blobs[0].name).name
        assert len(blobs[0].name) == 64


@pytest.mark.anyio
async def test_an_upload_over_the_cap_is_refused_and_stores_nothing(tmp_path: Path) -> None:
    app = app_for(tmp_path, attachment_max_bytes=1024)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        item_id = await make_item(client)

        refused = await client.post(
            f"/api/items/{item_id}/attachments",
            files={"file": ("big.epub", b"x" * 1025, "application/epub+zip")},
        )

        assert refused.status_code == 413
        assert refused.json()["error"]["code"] == "attachment_too_large"
        assert not any((tmp_path / "attachments").rglob("*"))


@pytest.mark.anyio
async def test_a_file_exactly_at_the_cap_is_accepted(tmp_path: Path) -> None:
    """The boundary is inclusive, and it is the boundary that gets mis-implemented."""
    app = app_for(tmp_path, attachment_max_bytes=1024)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        item_id = await make_item(client)

        accepted = await client.post(
            f"/api/items/{item_id}/attachments",
            files={"file": ("exact.epub", b"x" * 1024, "application/epub+zip")},
        )

        assert accepted.status_code == 201


@pytest.mark.anyio
async def test_an_empty_upload_is_refused(tmp_path: Path) -> None:
    app = app_for(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        item_id = await make_item(client)

        refused = await client.post(
            f"/api/items/{item_id}/attachments",
            files={"file": ("empty.epub", b"", "application/epub+zip")},
        )

        assert refused.status_code == 422


@pytest.mark.anyio
async def test_deleting_one_item_s_copy_leaves_another_item_s_file_alone(
    tmp_path: Path,
) -> None:
    """Deduplication must not turn one delete into someone else's data loss."""
    app = app_for(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        mine = await make_item(client, "Mine")
        yours = await make_item(client, "Yours")
        shared = b"the very same epub"
        first = await client.post(
            f"/api/items/{mine}/attachments",
            files={"file": ("a.epub", shared, "application/epub+zip")},
        )
        second = await client.post(
            f"/api/items/{yours}/attachments",
            files={"file": ("b.epub", shared, "application/epub+zip")},
        )
        blobs = [path for path in (tmp_path / "attachments").rglob("*") if path.is_file()]
        assert len(blobs) == 1, "identical bytes should occupy one blob"

        removed = await client.delete(f"/api/items/{mine}/attachments/{first.json()['id']}")
        assert removed.status_code == 204

        still_there = await client.get(f"/api/items/{yours}/attachments/{second.json()['id']}")
        assert still_there.status_code == 200
        assert still_there.content == shared


@pytest.mark.anyio
async def test_the_last_reference_going_away_takes_the_blob_with_it(tmp_path: Path) -> None:
    app = app_for(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        item_id = await make_item(client)
        uploaded = await client.post(
            f"/api/items/{item_id}/attachments",
            files={"file": ("only.epub", b"only copy", "application/epub+zip")},
        )

        removed = await client.delete(f"/api/items/{item_id}/attachments/{uploaded.json()['id']}")

        assert removed.status_code == 204
        assert not [path for path in (tmp_path / "attachments").rglob("*") if path.is_file()]


@pytest.mark.anyio
async def test_attachments_for_a_missing_item_are_a_404_not_an_empty_list(
    tmp_path: Path,
) -> None:
    app = app_for(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        listed = await client.get("/api/items/98765/attachments")

        assert listed.status_code == 404


@pytest.mark.anyio
async def test_renaming_changes_the_name_without_touching_the_bytes(tmp_path: Path) -> None:
    """The filename is metadata, so a rename is one database write and no file IO."""
    app = app_for(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        item_id = await make_item(client)
        uploaded = await client.post(
            f"/api/items/{item_id}/attachments",
            files={"file": ("untitled.epub", b"epub bytes here", "application/epub+zip")},
        )
        attachment_id = uploaded.json()["id"]
        digest = uploaded.json()["sha256"]
        blob = next(path for path in (tmp_path / "attachments").rglob("*") if path.is_file())
        before = blob.stat().st_ino

        renamed = await client.patch(
            f"/api/items/{item_id}/attachments/{attachment_id}",
            json={"filename": "Rayuela — Julio Cortázar.epub"},
        )

        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["filename"] == "Rayuela — Julio Cortázar.epub"
        # Row identity and digest are untouched, which is what keeps every backup
        # that already links this blob correct.
        assert renamed.json()["id"] == attachment_id
        assert renamed.json()["sha256"] == digest
        assert blob.stat().st_ino == before
        assert blob.read_bytes() == b"epub bytes here"

        listed = await client.get(f"/api/items/{item_id}/attachments")
        assert listed.json()["attachments"][0]["filename"] == "Rayuela — Julio Cortázar.epub"


@pytest.mark.anyio
async def test_a_renamed_file_downloads_under_its_new_name(tmp_path: Path) -> None:
    app = app_for(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        item_id = await make_item(client)
        uploaded = await client.post(
            f"/api/items/{item_id}/attachments",
            files={"file": ("untitled.epub", b"epub bytes here", "application/epub+zip")},
        )
        attachment_id = uploaded.json()["id"]

        await client.patch(
            f"/api/items/{item_id}/attachments/{attachment_id}",
            json={"filename": "Bestiario.epub"},
        )
        got = await client.get(f"/api/items/{item_id}/attachments/{attachment_id}")

        assert "Bestiario.epub" in got.headers["content-disposition"]
        assert "untitled.epub" not in got.headers["content-disposition"]


@pytest.mark.anyio
async def test_a_rename_invalidates_what_a_browser_already_cached(tmp_path: Path) -> None:
    """The wrinkle DEC-049 found: `immutable` for a year against a mutable name.

    The blob never changes but the response does, so the validator covers both.
    An unchanged file still costs nothing to re-check — 304, no body — and a
    renamed one can no longer match, so the browser refetches and saves under the
    name the owner just chose instead of the one from a year ago.
    """
    app = app_for(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        item_id = await make_item(client)
        uploaded = await client.post(
            f"/api/items/{item_id}/attachments",
            files={"file": ("untitled.epub", b"epub bytes here", "application/epub+zip")},
        )
        attachment_id = uploaded.json()["id"]
        url = f"/api/items/{item_id}/attachments/{attachment_id}"

        first = await client.get(url)
        etag = first.headers["etag"]
        assert "immutable" not in first.headers["cache-control"]

        unchanged = await client.get(url, headers={"If-None-Match": etag})
        assert unchanged.status_code == 304
        assert unchanged.content == b""

        await client.patch(url, json={"filename": "Bestiario.epub"})
        after = await client.get(url, headers={"If-None-Match": etag})

        assert after.status_code == 200
        assert after.content == b"epub bytes here"
        assert "Bestiario.epub" in after.headers["content-disposition"]
        assert after.headers["etag"] != etag


@pytest.mark.anyio
@pytest.mark.parametrize("hostile", ["../../books.db", "/etc/passwd", "a/b.epub"])
async def test_a_rename_to_a_path_keeps_only_the_name(tmp_path: Path, hostile: str) -> None:
    """Same rule as upload. Nothing here reaches the filesystem, but the name is
    echoed into a `Content-Disposition`, so it is normalized at the door."""
    app = app_for(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        item_id = await make_item(client)
        uploaded = await client.post(
            f"/api/items/{item_id}/attachments",
            files={"file": ("book.epub", b"epub bytes here", "application/epub+zip")},
        )

        renamed = await client.patch(
            f"/api/items/{item_id}/attachments/{uploaded.json()['id']}",
            json={"filename": hostile},
        )

        assert renamed.status_code == 200, renamed.text
        assert "/" not in renamed.json()["filename"]
        assert renamed.json()["filename"] in {"books.db", "passwd", "b.epub"}


@pytest.mark.anyio
@pytest.mark.parametrize("empty", ["", "   ", "/", "..", "."])
async def test_a_rename_to_nothing_is_refused(tmp_path: Path, empty: str) -> None:
    """A file with no name is worse than the name it had."""
    app = app_for(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        item_id = await make_item(client)
        uploaded = await client.post(
            f"/api/items/{item_id}/attachments",
            files={"file": ("book.epub", b"epub bytes here", "application/epub+zip")},
        )
        attachment_id = uploaded.json()["id"]

        renamed = await client.patch(
            f"/api/items/{item_id}/attachments/{attachment_id}", json={"filename": empty}
        )

        assert renamed.status_code == 422
        listed = await client.get(f"/api/items/{item_id}/attachments")
        assert listed.json()["attachments"][0]["filename"] == "book.epub"


@pytest.mark.anyio
async def test_a_rename_through_another_item_is_a_404(tmp_path: Path) -> None:
    app = app_for(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        mine = await make_item(client, "Mine")
        yours = await make_item(client, "Yours")
        uploaded = await client.post(
            f"/api/items/{mine}/attachments",
            files={"file": ("secret.epub", b"secret bytes", "application/epub+zip")},
        )

        renamed = await client.patch(
            f"/api/items/{yours}/attachments/{uploaded.json()['id']}",
            json={"filename": "mine-now.epub"},
        )

        assert renamed.status_code == 404


@pytest.mark.anyio
async def test_a_file_larger_than_the_buffer_round_trips_byte_identical(
    tmp_path: Path,
) -> None:
    """Several chunks in and several out, with nothing lost at the seams.

    Incompressible and not a repeating pattern on purpose: a payload of one
    repeated byte hides an off-by-one at a chunk boundary, because the wrong
    bytes still compare equal.
    """
    payload = os.urandom(int(UPLOAD_CHUNK_BYTES * 2.5))
    app = app_for(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        item_id = await make_item(client)

        uploaded = await client.post(
            f"/api/items/{item_id}/attachments",
            files={"file": ("big.epub", payload, "application/epub+zip")},
        )
        assert uploaded.status_code == 201, uploaded.text
        assert uploaded.json()["byte_size"] == len(payload)
        assert uploaded.json()["sha256"] == hashlib.sha256(payload).hexdigest()

        got = await client.get(f"/api/items/{item_id}/attachments/{uploaded.json()['id']}")

        assert got.status_code == 200
        assert got.content == payload
        assert int(got.headers["content-length"]) == len(payload)
        # The headers that make an opaque download safe survived the move to a
        # streamed response; FileResponse fills in only what it was not given.
        assert got.headers["content-type"] == "application/octet-stream"
        assert got.headers["x-content-type-options"] == "nosniff"
        assert "big.epub" in got.headers["content-disposition"]


@pytest.mark.anyio
async def test_an_upload_to_a_missing_item_is_refused_before_it_is_read(
    tmp_path: Path,
) -> None:
    """The 404 costs nothing: no blob is written and no temporary is left."""
    app = app_for(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        uploaded = await client.post(
            "/api/items/98765/attachments",
            files={"file": ("orphan.epub", b"bytes", "application/epub+zip")},
        )

        assert uploaded.status_code == 404
        assert not [path for path in (tmp_path / "attachments").rglob("*") if path.is_file()]
