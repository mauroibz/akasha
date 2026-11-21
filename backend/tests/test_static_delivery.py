"""How the shell and its files reach the browser (Sprint 129, performance follow-ups).

The single-page route used to answer every file with a bare `FileResponse`: no
`Cache-Control`, so a browser guessed, and a conditional request carrying the
file's own ETag still received the whole body again. Vite names everything under
`/assets/` after its content, so those files never change under their name and are
cached for a year; everything else at the root (the service worker, the theme
script, the manifest, the icons) keeps its name across deployments and is
revalidated. Responses are compressed when they are worth it, except a stream
that must arrive event by event and formats that are already compressed.
"""

import asyncio
import time
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

import httpx
import pytest

from book_tracker.config import Settings
from book_tracker.main import create_app

IMMUTABLE = "public, max-age=31536000, immutable"
SECURITY_HEADERS = ("x-content-type-options", "x-frame-options", "content-security-policy")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def static_root(tmp_path: Path) -> Path:
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>Akasha</title>", encoding="utf-8")
    # Big enough to be worth compressing, and compressible like real bundles.
    (static / "assets" / "index-Bw97biUb.js").write_text(
        "export const x = 1;\n" * 400, encoding="utf-8"
    )
    (static / "sw.js").write_text("self.addEventListener('fetch', () => {});", encoding="utf-8")
    (static / "theme-init.js").write_text("document.documentElement;", encoding="utf-8")
    (static / "manifest.webmanifest").write_text('{"name": "Akasha"}', encoding="utf-8")
    # A PNG signature and enough bytes to pass the compression threshold.
    (static / "favicon-512.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 4096)
    return static


def make_app(tmp_path: Path, **overrides: Any) -> Any:
    return create_app(
        Settings(
            data_dir=tmp_path / "data",
            static_dir=static_root(tmp_path),
            user_agent_contact="test@example.invalid",
            **overrides,
        )
    )


def client_for(app: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test")


def assert_security_headers(response: httpx.Response) -> None:
    for name in SECURITY_HEADERS:
        assert name in response.headers, (response.url, name)


@pytest.mark.anyio
async def test_hashed_assets_are_immutable_and_answer_a_matching_etag_with_304(
    tmp_path: Path,
) -> None:
    app = make_app(tmp_path)
    async with app.router.lifespan_context(app), client_for(app) as client:
        first = await client.get("/assets/index-Bw97biUb.js")
        assert first.status_code == 200
        assert first.headers["cache-control"] == IMMUTABLE
        etag = first.headers["etag"]
        assert_security_headers(first)

        again = await client.get("/assets/index-Bw97biUb.js", headers={"If-None-Match": etag})
        assert again.status_code == 304
        assert again.content == b""
        assert again.headers["etag"] == etag
        assert again.headers["cache-control"] == IMMUTABLE
        assert_security_headers(again)

        # A proxy that compressed the body hands back a weak validator.
        weak = await client.get("/assets/index-Bw97biUb.js", headers={"If-None-Match": f"W/{etag}"})
        assert weak.status_code == 304

        stale = await client.get(
            "/assets/index-Bw97biUb.js", headers={"If-None-Match": '"something-else"'}
        )
        assert stale.status_code == 200
        assert stale.content == first.content

        since = await client.get(
            "/assets/index-Bw97biUb.js",
            headers={"If-Modified-Since": first.headers["last-modified"]},
        )
        assert since.status_code == 304


@pytest.mark.anyio
async def test_files_that_keep_their_name_are_revalidated_not_pinned(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    async with app.router.lifespan_context(app), client_for(app) as client:
        for path in ("/sw.js", "/theme-init.js", "/manifest.webmanifest", "/favicon-512.png"):
            response = await client.get(path)
            assert response.status_code == 200, path
            assert response.headers["cache-control"] == "no-cache", path
            assert_security_headers(response)
            revalidated = await client.get(
                path, headers={"If-None-Match": response.headers["etag"]}
            )
            assert revalidated.status_code == 304, path
            assert revalidated.headers["cache-control"] == "no-cache", path

        shell = await client.get("/books/1")
        assert shell.headers["cache-control"] == "no-cache"
        assert "<title>Akasha</title>" in shell.text
        # The shell itself is never served as a file, whatever the path says.
        direct = await client.get("/index.html")
        assert direct.headers["cache-control"] == "no-cache"
        assert "etag" not in direct.headers


@pytest.mark.anyio
async def test_the_static_route_still_never_leaves_its_root(tmp_path: Path) -> None:
    (tmp_path / "secret.txt").write_text("owner private notes", encoding="utf-8")
    app = make_app(tmp_path)
    async with app.router.lifespan_context(app), client_for(app) as client:
        for path in ("/assets/../../secret.txt", "/assets/%2e%2e/%2e%2e/secret.txt"):
            response = await client.get(path)
            assert "owner private notes" not in response.text, path


@pytest.mark.anyio
async def test_bundles_and_json_are_gzipped_but_images_and_small_bodies_are_not(
    tmp_path: Path,
) -> None:
    app = make_app(tmp_path)
    gz = {"Accept-Encoding": "gzip"}
    async with app.router.lifespan_context(app), client_for(app) as client:
        bundle = await client.get("/assets/index-Bw97biUb.js", headers=gz)
        assert bundle.headers["content-encoding"] == "gzip"
        assert "accept-encoding" in bundle.headers["vary"].lower()
        # What crossed the wire, before httpx decoded it: 8,000 bytes of text.
        assert bundle.num_bytes_downloaded < 1024
        assert bundle.text.startswith("export const x = 1;")
        assert bundle.headers["cache-control"] == IMMUTABLE
        assert_security_headers(bundle)

        plain = await client.get("/assets/index-Bw97biUb.js", headers={"Accept-Encoding": ""})
        assert "content-encoding" not in plain.headers

        image = await client.get("/favicon-512.png", headers=gz)
        assert "content-encoding" not in image.headers

        small = await client.get("/sw.js", headers=gz)
        assert "content-encoding" not in small.headers
        # A small API answer stays as it was, length and all.
        probe = await client.get("/api/health/live", headers=gz)
        assert "content-encoding" not in probe.headers
        assert int(probe.headers["content-length"]) == len(probe.content)

        # The API's JSON compresses too; the boundary's own headers survive it.
        openapi = await client.get("/openapi.json", headers=gz)
        assert openapi.headers["content-encoding"] == "gzip"
        assert openapi.headers["cache-control"] == "no-store"
        assert openapi.json()["info"]["title"] == "Akasha"


Message = MutableMapping[str, Any]


@pytest.mark.anyio
async def test_the_event_stream_is_neither_compressed_nor_buffered(tmp_path: Path) -> None:
    """`/api/events` must reach the browser event by event; gzip would hold it back."""
    app = make_app(tmp_path)
    async with app.router.lifespan_context(app):
        app.state.event_stream_seconds = 1.5
        started = time.monotonic()
        messages: list[tuple[float, Message]] = []
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/events",
            "raw_path": b"/api/events",
            "root_path": "",
            "query_string": b"",
            "headers": [(b"host", b"test"), (b"accept-encoding", b"gzip, br")],
            "client": ("127.0.0.1", 1234),
            "server": ("test", 80),
        }
        request_sent = False

        async def receive() -> Message:
            nonlocal request_sent
            if not request_sent:
                request_sent = True
                return {"type": "http.request", "body": b"", "more_body": False}
            await asyncio.sleep(10)
            return {"type": "http.disconnect"}

        async def send(message: Message) -> None:
            messages.append((time.monotonic() - started, message))

        await app(scope, receive, send)

    start = next(message for _, message in messages if message["type"] == "http.response.start")
    headers = {key.decode().lower(): value.decode() for key, value in start["headers"]}
    assert headers["content-type"].startswith("text/event-stream")
    assert "content-encoding" not in headers
    bodies = [(at, message) for at, message in messages if message["type"] == "http.response.body"]
    first_at, first = next((at, message) for at, message in bodies if message.get("body"))
    # The reconnect hint arrives at once, in clear, long before the stream ends.
    assert first["body"].startswith(b"retry: 3000")
    assert first_at < 1.0
    assert bodies[-1][0] >= 1.4


@pytest.mark.anyio
async def test_the_body_limit_still_refuses_before_reading_under_compression(
    tmp_path: Path,
) -> None:
    app = make_app(tmp_path)
    async with app.router.lifespan_context(app), client_for(app) as client:
        response = await client.post(
            "/api/entries",
            content=b"{" + b" " * (2 * 1024 * 1024) + b"}",
            headers={"Content-Type": "application/json", "Accept-Encoding": "gzip"},
        )
    assert response.status_code == 413
    assert_security_headers(response)
