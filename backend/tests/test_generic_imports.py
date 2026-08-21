import sqlite3
from pathlib import Path

import httpx
import pytest

from book_tracker.application.imports import ImportService
from book_tracker.application.library import LibraryError
from book_tracker.config import Settings
from book_tracker.domain.importers import (
    ImportEntry,
    ImportInputSpec,
    ImportItem,
    ImportReadContext,
    ImportSnapshot,
    ImportSource,
    NormalizedImportRecord,
)
from book_tracker.domain.matching import MatchDecision
from book_tracker.main import create_app

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _calibre_library(root: Path) -> None:
    library = root / "library"
    library.mkdir(parents=True)
    connection = sqlite3.connect(library / "metadata.db")
    connection.executescript(
        """
        CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, pubdate TEXT, path TEXT, uuid TEXT);
        CREATE TABLE authors (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE books_authors_link (book INTEGER, author INTEGER);
        CREATE TABLE identifiers (book INTEGER, type TEXT, val TEXT);
        INSERT INTO books VALUES (1, 'Ficciones', '1944-01-01', '', 'uuid-1');
        INSERT INTO authors VALUES (1, 'Jorge Luis Borges');
        INSERT INTO books_authors_link VALUES (1, 1);
        INSERT INTO identifiers VALUES (1, 'isbn', '9780141187761');
        """
    )
    connection.commit()
    connection.close()


class _InvalidAlbumImporter:
    name = "invalid_album"
    label = "Invalid album"
    item_type = "album"
    input = ImportInputSpec(kind="upload", label="Fixture", field="file")
    identity_kinds = frozenset({"fixture_id"})

    def __init__(self, *, metadata: dict[str, object], values: dict[str, object]) -> None:
        self.metadata = metadata
        self.values = values

    def read(self, _source: ImportSource, _context: ImportReadContext) -> ImportSnapshot:
        return ImportSnapshot(
            fingerprint="invalid",
            filename="fixture",
            source_descriptor={},
            records=(
                NormalizedImportRecord(
                    row_number=2,
                    item=ImportItem(
                        title="Invalid record",
                        subtitle=None,
                        year=None,
                        identifiers={},
                        metadata=self.metadata,
                    ),
                    entry=ImportEntry(
                        score=None,
                        notes=None,
                        date_added=None,
                        values=self.values,
                    ),
                    shelves=(),
                    errors=(),
                    source_fields={},
                ),
            ),
        )

    def stage(self, snapshot: ImportSnapshot, _directory: Path, _data_dir: Path) -> ImportSnapshot:
        return snapshot

    def match(self, *_args: object) -> MatchDecision:
        raise AssertionError("validation must run before matching")


@pytest.mark.anyio
async def test_available_importers_are_published_from_the_registry(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.get("/api/importers")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "goodreads",
            "label": "Goodreads",
            "item_type": "book",
            "input": {
                "kind": "upload",
                "label": "Goodreads CSV",
                "field": "file",
                "accept": ".csv,text/csv",
                "placeholder": None,
                "help": None,
            },
        },
        {
            "id": "calibre",
            "label": "Calibre",
            "item_type": "book",
            "input": {
                "kind": "path",
                "label": "Calibre library path",
                "field": "library_path",
                "accept": None,
                "placeholder": "Library",
                "help": (
                    "Akasha opens this library read-only inside the configured Calibre mount. "
                    "Enter a relative folder only; covers are copied during preview."
                ),
            },
        },
    ]


@pytest.mark.anyio
async def test_generic_routes_round_trip_each_registered_book_importer(tmp_path: Path) -> None:
    calibre_root = tmp_path / "calibre"
    _calibre_library(calibre_root)
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            calibre_dir=calibre_root,
            user_agent_contact="test@example.invalid",
        )
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        goodreads = await client.post(
            "/api/import/goodreads/preview",
            files={
                "file": (
                    "library.csv",
                    (FIXTURES / "goodreads_valid.csv").read_bytes(),
                    "text/csv",
                )
            },
        )
        assert goodreads.status_code == 201
        goodreads_commit = await client.post(
            "/api/import/goodreads/commit",
            json={"batch_id": goodreads.json()["batch_id"]},
        )
        assert goodreads_commit.status_code == 200

        calibre = await client.post("/api/import/calibre/preview", json={"library_path": "library"})
        assert calibre.status_code == 201
        calibre_commit = await client.post(
            "/api/import/calibre/commit",
            json={"batch_id": calibre.json()["batch_id"]},
        )
        assert calibre_commit.status_code == 200

    assert goodreads_commit.json()["created_entries"] == 1
    assert calibre_commit.json()["unchanged_entries"] == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("metadata", "values", "message"),
    [
        (
            {"creators": [], "publisher": "A book field"},
            {},
            "metadata has no field named 'publisher'",
        ),
        (
            {"creators": []},
            {"reread_count": 2},
            "entries have no 'reread_count'",
        ),
    ],
)
async def test_normalized_records_are_validated_against_the_target_domain(
    tmp_path: Path,
    metadata: dict[str, object],
    values: dict[str, object],
    message: str,
) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        importer = _InvalidAlbumImporter(metadata=metadata, values=values)
        service = ImportService(
            app.state.engine,
            app.state.data_dir,
            app.state.calibre_dir,
            importer,  # type: ignore[arg-type]
        )
        with pytest.raises(LibraryError) as caught:
            service.preview(ImportSource(data=b"fixture", filename="fixture"))

    assert caught.value.code == "invalid_import_record"
    assert caught.value.status_code == 422
    assert message in caught.value.message
