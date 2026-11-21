"""Untrusted input handled in bounded time and memory (Sprint 128, F14/F15/F6/F21)."""

import importlib
import time
import zipfile
import zlib
from pathlib import Path

import pytest

from book_tracker.domain.importers import detect_importers
from book_tracker.domain.sniffing import SNIFF_BYTES, csv_header, text_of, xml_root

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
