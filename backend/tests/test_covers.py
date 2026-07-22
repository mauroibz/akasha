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


@pytest.mark.anyio
async def test_cover_is_bounded_resized_and_atomically_installed(tmp_path: Path) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=jpeg())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        prepared = await prepare_cover(client, "https://covers.example/one", tmp_path)
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
            await prepare_cover(client, "https://covers.example/bad", tmp_path)
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
            await prepare_cover(client, "https://covers.example/huge", tmp_path)
    assert huge.loaded is False
    assert list((tmp_path / "covers").glob("*.tmp")) == []


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
