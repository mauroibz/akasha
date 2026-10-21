"""Which importer a dropped file belongs to (Sprint 095, proposal §5.2).

A file dropped anywhere in the application is read for its first 64 KiB and each
connector that can recognise its own source says how sure it is. The signals are the
sources' own fingerprints: a CSV's header, a zip's member names, an XML root, an EPUB's
`mimetype`. A file nobody claims is offered to the custom list, which reads any table.
"""

import gzip
import io
import zipfile
from pathlib import Path

import httpx
import pytest

from book_tracker.config import Settings
from book_tracker.domain.importers import detect_importers
from book_tracker.main import create_app

FIXTURES = Path(__file__).parent / "fixtures"


def _zip(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def _epub() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(zipfile.ZipInfo("mimetype"), b"application/epub+zip", zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", b"<container/>")
    return buffer.getvalue()


SAMPLES = {
    "goodreads": ("goodreads_library_export.csv", (FIXTURES / "goodreads_valid.csv").read_bytes()),
    "imdb": (
        "ratings.csv",
        b"Const,Your Rating,Date Rated,Title,Original Title,URL,Title Type,IMDb Rating,"
        b"Runtime (mins),Year,Genres,Num Votes,Release Date,Directors\n"
        b"tt0111161,10,2024-01-01,The Shawshank Redemption,,,Movie,9.3,142,1994,Drama,1,,\n",
    ),
    "myanimelist": (
        "animelist.xml",
        (FIXTURES / "imports" / "myanimelist_sample.xml").read_bytes(),
    ),
    "letterboxd": (
        "letterboxd-export.zip",
        _zip(
            {
                "watched.csv": b"Date,Name,Year,Letterboxd URI\n",
                "ratings.csv": b"Date,Name,Year,Letterboxd URI,Rating\n",
            }
        ),
    ),
    "trakt": (
        "trakt-export.zip",
        _zip({"watched-movies.json": b"[]", "ratings-movies.json": b"[]"}),
    ),
    "spotify": ("my_spotify_data.zip", _zip({"Spotify Account Data/YourLibrary.json": b"{}"})),
    "epub": ("rayuela.epub", _epub()),
}


@pytest.mark.parametrize("expected", sorted(SAMPLES))
def test_each_source_is_recognised_as_its_own_connector(expected: str) -> None:
    name, data = SAMPLES[expected]
    ranked = detect_importers(data[: 64 * 1024], name)
    assert ranked, f"nothing claimed {name}"
    assert ranked[0][0] == expected, ranked


def test_a_gzipped_myanimelist_export_is_recognised() -> None:
    data = gzip.compress((FIXTURES / "imports" / "myanimelist_sample.xml").read_bytes())
    assert detect_importers(data, "animelist_1700000000_-_123.xml.gz")[0][0] == "myanimelist"


def test_an_unknown_table_falls_to_the_custom_list() -> None:
    ranked = detect_importers(b"Titulo,Autor\nRayuela,Cortazar\n", "mis-libros.csv")
    assert ranked[0][0] == "list"


def test_a_file_nothing_reads_is_claimed_by_nobody() -> None:
    assert detect_importers(b"\x89PNG\r\n\x1a\n", "cover.png") == []


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_the_detect_route_ranks_each_file(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.post(
            "/api/import/detect",
            files=[
                ("files", SAMPLES["goodreads"]),
                ("files", SAMPLES["epub"]),
                ("files", ("cover.png", b"\x89PNG\r\n\x1a\n")),
            ],
        )
    assert response.status_code == 200
    body = response.json()
    assert [file["name"] for file in body["files"]] == [
        "goodreads_library_export.csv",
        "rayuela.epub",
        "cover.png",
    ]
    assert body["files"][0]["matches"][0]["importer"] == "goodreads"
    assert body["files"][1]["matches"][0]["importer"] == "epub"
    assert body["files"][2]["matches"] == []
