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
        # An allowlisted host on `http://` is upgraded, not refused: see
        # `test_an_http_cover_url_is_upgraded_rather_than_refused` below. What stays
        # refused is the host, whatever scheme it arrives on.
        with pytest.raises(CoverError, match="allowlisted"):
            await prepare_cover(client, "http://evil.example/cover.jpg", tmp_path)


@pytest.mark.anyio
async def test_an_http_cover_url_is_upgraded_rather_than_refused(tmp_path: Path) -> None:
    """The Cover Art Archive hands out `http://` URLs (DEC-052 seam 4, obs. 5).

    Loosening the scheme check would have been the easy fix and the wrong one: the
    URL is rewritten to https *before* it is validated, so nothing is ever fetched
    over http and an allowlisted host is not lost to a provider's own habit.
    """
    schemes: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        schemes.append(request.url.scheme)
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=jpeg())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        prepared = await prepare_cover(
            client, "http://coverartarchive.org/release/x/1-1200.jpg", tmp_path
        )
    assert prepared.exists()
    assert schemes == ["https"]


@pytest.mark.anyio
async def test_the_archive_org_redirect_chain_survives_the_hop_check(tmp_path: Path) -> None:
    """CAA redirects through archive.org to a numbered node, on `http://` each time.

    `validate_url` runs on every hop, and the final host — `dn710907.ca.archive.org` —
    is matched by neither `archive.org` exactly nor the old `.us.archive.org` suffix.
    Both hops answer `http://`, which is why the upgrade cannot apply only to the
    first URL.
    """
    hosts: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(f"{request.url.scheme}://{request.url.host}")
        if request.url.host == "coverartarchive.org":
            return httpx.Response(
                307, headers={"location": "http://archive.org/download/mbid-x/thumb1200.jpg"}
            )
        if request.url.host == "archive.org":
            return httpx.Response(
                302,
                headers={"location": "http://dn710907.ca.archive.org/0/items/x/thumb1200.jpg"},
            )
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=jpeg())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        prepared = await prepare_cover(
            client, "http://coverartarchive.org/release/x/1-1200.jpg", tmp_path
        )
    assert prepared.exists()
    assert hosts == [
        "https://coverartarchive.org",
        "https://archive.org",
        "https://dn710907.ca.archive.org",
    ]


@pytest.mark.anyio
async def test_a_host_that_merely_ends_in_the_allowlisted_name_is_still_refused(
    tmp_path: Path,
) -> None:
    """A subdomain rule is `.archive.org`, not `archive.org` anywhere in the name."""

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=jpeg())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        for host in ("notarchive.org", "archive.org.evil.example", "evil-archive.org"):
            with pytest.raises(CoverError, match="allowlisted"):
                await prepare_cover(client, f"https://{host}/cover.jpg", tmp_path)


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


@pytest.mark.anyio
async def test_cover_rejects_an_image_too_small_to_be_a_cover(tmp_path: Path) -> None:
    """Sprint 020's walkthrough chose a candidate and got a 60x40 image.

    Open Library serves whatever scan it holds behind a `-L.jpg` URL, and for some
    cover ids that is a thumbnail. It is a real image with a plausible 1.5 ratio, so
    neither the byte guard nor the placeholder-banner guard catches it; it just looks
    broken at the 240px the detail page paints it.

    Only the download path is tightened. `prepare_uploaded_cover` is left alone: what a
    person deliberately uploads is their business.
    """

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=jpeg((60, 40)))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(CoverError, match="too small"):
            await prepare_cover(client, "https://covers.openlibrary.org/one", tmp_path)


@pytest.mark.anyio
async def test_a_small_but_usable_cover_is_still_accepted(tmp_path: Path) -> None:
    """The bound has to clear real scans, not just the pathological one."""

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=jpeg((220, 330)))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        prepared = await prepare_cover(client, "https://covers.openlibrary.org/one", tmp_path)
    assert prepared.exists()
    prepared.unlink()


@pytest.mark.anyio
async def test_open_library_downloads_always_ask_for_no_default_placeholder(
    tmp_path: Path,
) -> None:
    """`?default=false` is the only reliable guard against Open Library's placeholder.

    DEC-044's geometry rule catches Google Books' banner because it is 6.25:1. Open
    Library's "No image available" is a portrait image of ordinary size, so no shape or
    byte heuristic separates it from a real cover — Sprint 020's walkthrough installed
    one at 325x500 and it sailed through both guards. Asking the host not to substitute
    a default turns it into a 404 instead, so the parameter is forced here rather than
    trusted to whatever URL arrived.
    """
    seen: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=jpeg((400, 600)))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        prepared = await prepare_cover(
            client, "https://covers.openlibrary.org/b/id/8231851-L.jpg", tmp_path
        )
    prepared.unlink()

    assert seen == ["https://covers.openlibrary.org/b/id/8231851-L.jpg?default=false"]


@pytest.mark.anyio
async def test_a_non_open_library_host_is_not_given_the_parameter(tmp_path: Path) -> None:
    """The parameter means something to one host; adding it everywhere is noise."""
    seen: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=jpeg((400, 600)))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        prepared = await prepare_cover(
            client, "https://books.google.com/books/content?id=abc", tmp_path
        )
    prepared.unlink()

    assert seen == ["https://books.google.com/books/content?id=abc"]
