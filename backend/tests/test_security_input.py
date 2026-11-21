"""Untrusted input handled in bounded time and memory (Sprint 128, F14/F15/F6/F21)."""

import importlib
import io
import time
import zipfile
import zlib
from pathlib import Path

import httpx
import pytest
from PIL import Image

from book_tracker.config import Settings
from book_tracker.domain.importers import detect_importers
from book_tracker.domain.sniffing import SNIFF_BYTES, csv_header, text_of, xml_root
from book_tracker.infrastructure.covers import CoverError, prepare_cover, prepare_uploaded_cover
from book_tracker.infrastructure.providers import create_provider_client
from book_tracker.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _image(kind: str, size: tuple[int, int] = (300, 400)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "navy").save(buffer, kind)
    return buffer.getvalue()


@pytest.mark.anyio
async def test_a_cover_redirect_is_validated_hop_by_hop_not_followed_by_httpx(
    tmp_path: Path,
) -> None:
    """F15: the shared client follows redirects itself, so the cover fetch must turn
    that off or the per-hop allowlist and HTTPS checks never see a 3xx."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.host == "covers.openlibrary.org":
            location = "http://169.254.169.254/latest/meta-data/x.jpg"
            return httpx.Response(302, headers={"location": location})
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=_image("JPEG"))

    client = create_provider_client(httpx.MockTransport(handler))
    try:
        with pytest.raises(CoverError):
            await prepare_cover(client, "https://covers.openlibrary.org/b/id/1-L.jpg", tmp_path)
    finally:
        await client.aclose()
    assert all("169.254.169.254" not in url for url in seen), seen
    assert len(seen) == 1


@pytest.mark.anyio
async def test_an_allowlisted_cover_redirect_is_still_followed(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "coverartarchive.org":
            location = "http://dn1.ca.archive.org/cover.jpg"
            return httpx.Response(307, headers={"location": location})
        assert request.url.scheme == "https"
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=_image("JPEG"))

    client = create_provider_client(httpx.MockTransport(handler))
    try:
        prepared = await prepare_cover(client, "https://coverartarchive.org/release/x", tmp_path)
    finally:
        await client.aclose()
    assert prepared.exists()


@pytest.mark.parametrize("kind", ["TIFF", "BMP", "GIF", "ICO"])
def test_an_uploaded_cover_in_another_format_is_refused(tmp_path: Path, kind: str) -> None:
    """F6: only the three formats the routes accept are ever decoded, whatever the
    client claims the content type is."""
    with pytest.raises(CoverError):
        prepare_uploaded_cover(_image(kind, (64, 64)), "image/jpeg", tmp_path)
    assert list((tmp_path / "covers").iterdir()) == []


@pytest.mark.parametrize("kind", ["JPEG", "PNG", "WEBP"])
def test_an_uploaded_cover_in_an_accepted_format_is_prepared(tmp_path: Path, kind: str) -> None:
    prepared = prepare_uploaded_cover(_image(kind), "image/jpeg", tmp_path)
    assert prepared.exists()


@pytest.mark.anyio
async def test_a_tiff_cover_upload_answers_422(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="t@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://t") as client,
    ):
        created = await client.post(
            "/api/entries",
            json={"manual": {"item_type": "book", "title": "x"}, "idempotency_key": "x"},
        )
        item_id = created.json()["entry"]["item_id"]
        response = await client.post(
            f"/api/items/{item_id}/cover",
            files={"cover": ("a.jpg", _image("TIFF", (64, 64)), "image/jpeg")},
        )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "invalid_cover"


#: Generous: each case below took 2-40 s before the fix and takes milliseconds after.
BOUND_SECONDS = 1.0


def _elapsed(function, *args) -> float:  # type: ignore[no-untyped-def]
    started = time.perf_counter()
    function(*args)
    return time.perf_counter() - started


@pytest.mark.parametrize(
    "head",
    [
        b'a,"b;' * (SNIFF_BYTES // 5),
        b'"a",' * (SNIFF_BYTES // 4),
        b"<!" * (SNIFF_BYTES // 2),
    ],
    ids=["csv-mixed", "csv-quotes", "xml-bang"],
)
def test_sniffing_a_hostile_head_is_fast(head: bytes) -> None:
    assert _elapsed(detect_importers, head, "x.csv") < BOUND_SECONDS


def test_a_gzip_head_never_inflates_past_the_sniff_window() -> None:
    bomb = zlib.compressobj(9, zlib.DEFLATED, 16 + zlib.MAX_WBITS)
    compressed = bomb.compress(b"<!" * (40 * 1024 * 1024)) + bomb.flush()
    text = text_of(compressed[:SNIFF_BYTES])
    assert len(text) <= SNIFF_BYTES
    assert _elapsed(detect_importers, compressed[:SNIFF_BYTES], "x.csv") < BOUND_SECONDS


def test_csv_header_still_reads_the_delimiter_it_finds() -> None:
    assert csv_header(b"Title,Author,ISBN\nA,B,C\n") == ["Title", "Author", "ISBN"]
    assert csv_header(b"Title;Author;ISBN\nA;B;C\n") == ["Title", "Author", "ISBN"]
    assert csv_header(b"Title\tAuthor\n") == ["Title", "Author"]
    assert csv_header(b'"Title, the","Author"\n') == ["Title, the", "Author"]
    assert csv_header(b'"Title; sub";Author;Year\n') == ["Title; sub", "Author", "Year"]
    assert csv_header(b"") is None


def test_csv_header_never_raises() -> None:
    for head in (b'"unterminated, quote\n', b"a," * 70_000, b"x" * 1100 + b"\x00,y\n"):
        result = csv_header(head)
        assert result is None or isinstance(result, list)


def test_xml_root_skips_declarations_and_comments() -> None:
    assert xml_root(b'<?xml version="1.0"?><!-- c --><myanimelist>') == "myanimelist"
    assert xml_root(b"<?xml?><!DOCTYPE x><!-- <not> this --><root/>") == "root"
    assert xml_root(b"<!-- never closed <root>") is None


@pytest.mark.parametrize(
    "module",
    [
        "book_tracker.domains.series.tvmaze",
        "book_tracker.domains.anime.providers",
        "book_tracker.domains.movie.letterboxd",
    ],
)
def test_markup_stripping_is_linear_on_a_run_of_unclosed_tags(module: str) -> None:
    plain = importlib.import_module(module)._plain
    assert plain("<p>One <b>two</b></p>") == "One two"
    assert _elapsed(plain, "<" * 250_000) < BOUND_SECONDS


def test_an_epub_description_of_unclosed_tags_reads_in_linear_time(tmp_path: Path) -> None:
    from book_tracker.domains.book.epub import read_epub

    path = _epub(tmp_path, description="&lt;" * 250_000)
    assert _elapsed(read_epub, path, tmp_path / "covers", 1) < BOUND_SECONDS * 2


_CONTAINER = (
    '<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
    '<rootfiles><rootfile full-path="c.opf"/></rootfiles></container>'
)


def _epub(root: Path, *, description: str = "", opf: bytes | None = None) -> Path:
    path = root / "x.epub"
    package = (
        opf
        or (
            '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>t</dc:title>'
            f"<dc:creator>a</dc:creator><dc:description>{description}</dc:description>"
            "</metadata><manifest/></package>"
        ).encode()
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", _CONTAINER)
        archive.writestr("c.opf", package)
    return path
