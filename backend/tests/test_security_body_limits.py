"""Oversized request bodies answer 413 before they are spooled (Sprint 128, F7)."""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
import starlette.formparsers

from book_tracker.app import body_limits
from book_tracker.app.body_limits import DEFAULT_MAX_BODY_BYTES, body_limit
from book_tracker.config import Settings
from book_tracker.infrastructure import diskspace
from book_tracker.main import create_app

MiB = 1024 * 1024


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def spooled(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, int]]:
    """The most bytes any multipart part was spooled to, across the request."""
    peak = {"max": 0}
    original = starlette.formparsers.SpooledTemporaryFile

    class Tracking(original):  # type: ignore[misc, valid-type]
        def write(self, data: bytes) -> int:
            written = super().write(data)
            peak["max"] = max(peak["max"], self.tell())
            return written

    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", Tracking)
    yield peak


@asynccontextmanager
async def running(tmp_path: Path, **settings: Any) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(
        Settings(data_dir=tmp_path / "data", user_agent_contact="t@example.invalid", **settings)
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://t") as client,
    ):
        yield client


async def _item(client: httpx.AsyncClient) -> int:
    created = await client.post(
        "/api/entries",
        json={"manual": {"item_type": "book", "title": "x"}, "idempotency_key": "x"},
    )
    return int(created.json()["entry"]["item_id"])


def _assert_too_large(response: httpx.Response) -> None:
    assert response.status_code == 413, response.text
    error = response.json()["error"]
    assert error["code"] == "payload_too_large"
    assert error["details"]["max_bytes"] > 0


async def _chunked(data: bytes, size: int = 64 * 1024) -> AsyncIterator[bytes]:
    for start in range(0, len(data), size):
        yield data[start : start + size]


@pytest.mark.anyio
async def test_an_oversized_unauthenticated_login_is_refused_before_it_is_read(
    tmp_path: Path,
) -> None:
    async with running(tmp_path, auth="on", setup_token="body-limit-setup-code") as client:
        setup = await client.post(
            "/api/auth/setup",
            json={
                "username": "admin",
                "password": "pw-123456789",
                "setup_code": "body-limit-setup-code",
            },
        )
        assert setup.status_code in (200, 201), setup.text
        client.cookies.clear()
        body = b'{"username":"' + b"a" * (2 * MiB) + b'","password":"x"}'
        declared = await client.post(
            "/api/auth/login", content=body, headers={"content-type": "application/json"}
        )
        _assert_too_large(declared)
        streamed = await client.post(
            "/api/auth/login", content=_chunked(body), headers={"content-type": "application/json"}
        )
        _assert_too_large(streamed)
        # An ordinary login is untouched.
        ok = await client.post(
            "/api/auth/login", json={"username": "admin", "password": "pw-123456789"}
        )
        assert ok.status_code == 200, ok.text


@pytest.mark.anyio
async def test_an_oversized_json_body_anywhere_answers_413(tmp_path: Path) -> None:
    async with running(tmp_path) as client:
        body = b'{"manual":{"item_type":"book","title":"' + b"x" * (2 * MiB) + b'"}}'
        response = await client.post(
            "/api/entries", content=body, headers={"content-type": "application/json"}
        )
    _assert_too_large(response)


@pytest.mark.anyio
async def test_an_oversized_attachment_is_refused_before_a_byte_is_spooled(
    tmp_path: Path, spooled: dict[str, int]
) -> None:
    async with running(tmp_path, attachment_max_bytes=1 * MiB) as client:
        item_id = await _item(client)
        spooled["max"] = 0
        response = await client.post(
            f"/api/items/{item_id}/attachments", files={"file": ("a.bin", b"A" * (3 * MiB))}
        )
        _assert_too_large(response)
        assert spooled["max"] == 0
        # Within the cap the route still takes it.
        fine = await client.post(
            f"/api/items/{item_id}/attachments", files={"file": ("a.bin", b"A" * 1000)}
        )
        assert fine.status_code == 201, fine.text


@pytest.mark.anyio
async def test_a_chunked_upload_is_cut_off_at_the_ceiling_while_streaming(
    tmp_path: Path, spooled: dict[str, int]
) -> None:
    async with running(tmp_path, attachment_max_bytes=1 * MiB) as client:
        item_id = await _item(client)
        built = httpx.Request("POST", "http://t/", files={"file": ("a.bin", b"A" * (6 * MiB))})
        body = built.read()
        spooled["max"] = 0
        response = await client.post(
            f"/api/items/{item_id}/attachments",
            content=_chunked(body),
            headers={"content-type": built.headers["content-type"]},
        )
    _assert_too_large(response)
    limit = 1 * MiB + body_limits.MULTIPART_OVERHEAD_BYTES
    assert spooled["max"] <= limit


@pytest.mark.anyio
async def test_an_oversized_cover_upload_answers_413(
    tmp_path: Path, spooled: dict[str, int]
) -> None:
    async with running(tmp_path) as client:
        item_id = await _item(client)
        spooled["max"] = 0
        response = await client.post(
            f"/api/items/{item_id}/cover",
            files={"cover": ("a.jpg", b"A" * (12 * MiB), "image/jpeg")},
        )
    _assert_too_large(response)
    assert spooled["max"] == 0


@pytest.mark.anyio
async def test_detect_takes_only_sniff_windows(tmp_path: Path, spooled: dict[str, int]) -> None:
    async with running(tmp_path) as client:
        heads = await client.post(
            "/api/import/detect",
            files=[("files", (f"f{index}.csv", b"Title,Author\n" * 5000)) for index in range(50)],
        )
        assert heads.status_code == 200, heads.text
        spooled["max"] = 0
        whole = await client.post(
            "/api/import/detect", files={"files": ("a.csv", b"A" * (60 * MiB))}
        )
    _assert_too_large(whole)
    assert spooled["max"] == 0


@pytest.mark.anyio
async def test_a_goodreads_upload_far_over_its_cap_is_refused_before_spooling(
    tmp_path: Path, spooled: dict[str, int]
) -> None:
    async with running(tmp_path) as client:
        spooled["max"] = 0
        response = await client.post(
            "/api/import/goodreads/preview", files={"file": ("a.csv", b"A" * (60 * MiB))}
        )
    _assert_too_large(response)
    assert spooled["max"] == 0


def test_the_ceilings_follow_each_routes_own_documented_cap() -> None:
    assert body_limit(None, "/api/auth/login").max_bytes == DEFAULT_MAX_BODY_BYTES
    assert body_limit(None, "/api/anything/else").max_bytes == DEFAULT_MAX_BODY_BYTES
    goodreads = body_limit(None, "/api/import/goodreads/preview")
    assert 5 * MiB < goodreads.max_bytes < 8 * MiB
    calibre = body_limit(None, "/api/import/calibre/preview")
    assert 8 * 1024 * MiB < calibre.max_bytes < 8 * 1024 * MiB + 64 * MiB
    assert calibre.writes_to_disk
    epub = body_limit(None, "/api/import/epub/preview")
    assert 2 * 1024 * MiB < epub.max_bytes < 2 * 1024 * MiB + 64 * MiB
    cover = body_limit(None, "/api/items/7/cover")
    assert 10 * MiB < cover.max_bytes < 11 * MiB
    # A path that only looks like an upload route one level down is not one.
    assert body_limit(None, "/api/items/7/cover/x").max_bytes == DEFAULT_MAX_BODY_BYTES


@pytest.mark.anyio
async def test_a_declared_upload_that_would_fill_the_disk_is_refused_before_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spooled: dict[str, int]
) -> None:
    async with running(tmp_path, min_free_bytes=10 * MiB) as client:
        item_id = await _item(client)
        free = 12 * MiB
        monkeypatch.setattr(diskspace, "free_bytes", lambda _path: free)
        spooled["max"] = 0
        response = await client.post(
            f"/api/items/{item_id}/attachments", files={"file": ("a.bin", b"A" * (3 * MiB))}
        )
        assert response.status_code == 507, response.text
        assert response.json()["error"]["code"] == "insufficient_disk_space"
        assert spooled["max"] == 0
