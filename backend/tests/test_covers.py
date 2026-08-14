import io
from pathlib import Path

import httpx
import pytest
from PIL import Image

from book_tracker.infrastructure.covers import CoverError, install_cover, prepare_cover


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def jpeg(size: tuple[int, int] = (1200, 800)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, "#ff00aa").save(output, "JPEG")
    return output.getvalue()


def png(size: tuple[int, int]) -> bytes:
    output = io.BytesIO()
    Image.new("P", size, 0).save(output, "PNG")
    return output.getvalue()


@pytest.mark.anyio
async def test_cover_is_bounded_resized_and_atomically_installed(tmp_path: Path) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=jpeg())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        prepared = await prepare_cover(client, "https://covers.openlibrary.org/one", tmp_path)
    target = install_cover(prepared, tmp_path, 42)
    assert target == tmp_path / "covers" / "42.jpg"
    with Image.open(target) as image:
        assert max(image.size) == 600
        assert image.format == "JPEG"
    assert not prepared.exists()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("content_type", "content"),
    [("text/html", b"not an image"), ("image/jpeg", b"x" * (10 * 1024 * 1024 + 1))],
)
async def test_cover_rejects_non_images_and_oversized_payloads(
    tmp_path: Path, content_type: str, content: bytes
) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": content_type}, content=content)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(CoverError):
            await prepare_cover(client, "https://covers.openlibrary.org/bad", tmp_path)
    assert list((tmp_path / "covers").glob("*.tmp")) == []


@pytest.mark.anyio
async def test_cover_rejects_excessive_pixels_before_loading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class HugeImage:
        size = (10_000, 10_000)
        loaded = False

        def __enter__(self) -> "HugeImage":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def load(self) -> None:
            self.loaded = True

    huge = HugeImage()
    monkeypatch.setattr(Image, "open", lambda _path: huge)

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=b"jpeg")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(CoverError, match="pixel limit"):
            await prepare_cover(client, "https://covers.openlibrary.org/huge", tmp_path)
    assert huge.loaded is False
    assert list((tmp_path / "covers").glob("*.tmp")) == []


@pytest.mark.anyio
async def test_cover_follows_only_bounded_allowlisted_https_redirects(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "https://evil.example/cover.jpg"})
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=jpeg())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(CoverError, match="allowlisted"):
            await prepare_cover(client, "https://covers.openlibrary.org/start", tmp_path)
        with pytest.raises(CoverError, match="allowlisted"):
            await prepare_cover(client, "http://covers.openlibrary.org/cover.jpg", tmp_path)


def test_cover_install_failure_removes_prepared_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = tmp_path / "covers" / "prepared.jpg.tmp"
    prepared.parent.mkdir()
    prepared.write_bytes(b"prepared")

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("book_tracker.infrastructure.covers.os.replace", fail_replace)
    with pytest.raises(CoverError, match="installed"):
        install_cover(prepared, tmp_path, 7)
    assert not prepared.exists()
    assert not (tmp_path / "covers" / "7.jpg").exists()


@pytest.mark.anyio
async def test_cover_rejects_a_provider_placeholder_banner(tmp_path: Path) -> None:
    """DEC-044 measured the shape of Google Books' "image not available" image.

    It is 575x92 — a 6.25:1 banner at a few hundred bytes — where the real covers
    measured alongside it were 575x750 and 575x887. Before this guard `prepare_cover`
    rejected only images under 10px per side, so the placeholder was installed as a
    real cover and nothing downstream could tell.
    """

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=png((575, 92)))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(CoverError, match="placeholder"):
            await prepare_cover(client, "https://covers.openlibrary.org/one", tmp_path)


@pytest.mark.anyio
async def test_cover_accepts_a_wide_but_plausible_cover(tmp_path: Path) -> None:
    """The guard is a banner detector, not a portrait rule: wraparound art is real."""

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, headers={"content-type": "image/jpeg"}, content=jpeg((1200, 800))
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        prepared = await prepare_cover(client, "https://covers.openlibrary.org/one", tmp_path)
    assert prepared.exists()
    prepared.unlink()
