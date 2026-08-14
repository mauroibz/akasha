"""Uploading, listing, downloading and deleting attached files (DEC-048).

The download assertions carry most of the weight. Every byte this application
served before now went through the cover pipeline and came back out as a
re-encoded JPEG, so an attachment is the first user-controlled content type to
reach a browser — and it is served from the same origin as the SPA. An uploaded
HTML or SVG opened inline could script the application against its own API, so
`Content-Disposition: attachment`, `nosniff` and a fixed
`application/octet-stream` are load-bearing rather than decorative.
"""

from pathlib import Path

import httpx
import pytest

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
