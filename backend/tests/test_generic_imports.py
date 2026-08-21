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
    published = response.json()
    assert [row["id"] for row in published] == ["goodreads", "calibre"]

    goodreads, calibre = published
    assert goodreads["input"]["kind"] == "upload"
    assert goodreads["input"]["accept"] == ".csv,text/csv"
    assert goodreads["input"]["browsable"] is False
    assert calibre["input"]["kind"] == "path"
    assert calibre["input"]["browsable"] is True

    # The screen renders what the connector declares, so what it declares has to
    # arrive intact: ordered steps, an empty state and an https help address.
    for row in published:
        spec = row["input"]
        assert spec["guide"] and all(step.strip() for step in spec["guide"])
        assert spec["empty_state"]
        assert spec["help_url"].startswith("https://")
    assert any("review/import" in step for step in goodreads["input"]["guide"])
    assert any("provisional" in step.lower() for step in goodreads["input"]["guide"])
    assert any("read-only" in step for step in calibre["input"]["guide"])


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


def _browsable_calibre_tree(root: Path) -> None:
    """A mount with two libraries, a decoy folder and a file beside them."""
    _calibre_library(root / "Fiction")
    _calibre_library(root / "Comics")
    (root / "Fiction" / "Notes").mkdir()
    (root / "loose.txt").write_text("not a folder")


@pytest.mark.anyio
async def test_browsing_lists_folder_names_and_nothing_else(tmp_path: Path) -> None:
    """The picker exists so nobody types a path blind; it publishes names only."""
    calibre_root = tmp_path / "calibre"
    calibre_root.mkdir()
    _browsable_calibre_tree(calibre_root)
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
        top = await client.get("/api/import/calibre/browse")
        inside = await client.get("/api/import/calibre/browse", params={"path": "Fiction"})
        nested = await client.get("/api/import/calibre/browse", params={"path": "Fiction/library"})

    assert top.status_code == 200
    assert top.json() == {
        "path": "",
        "parent": None,
        "directories": ["Comics", "Fiction"],
        "importable": False,
    }
    # The loose file is absent, and so is every absolute path.
    assert "loose.txt" not in str(top.json())
    assert str(calibre_root) not in str(top.json())

    assert inside.json()["parent"] == ""
    assert inside.json()["directories"] == ["Notes", "library"]
    # `Fiction` itself holds no metadata.db; the library one level down does.
    assert inside.json()["importable"] is False
    assert nested.json() == {
        "path": "Fiction/library",
        "parent": "Fiction",
        "directories": [],
        "importable": True,
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path",
    ["../..", "Fiction/../../etc", "/etc", "Fiction/../../../", "\\etc"],
)
async def test_browsing_refuses_to_leave_the_mount(tmp_path: Path, path: str) -> None:
    calibre_root = tmp_path / "calibre"
    calibre_root.mkdir()
    _browsable_calibre_tree(calibre_root)
    (tmp_path / "secret").mkdir()
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
        response = await client.get("/api/import/calibre/browse", params={"path": path})

    assert response.status_code == 422
    assert response.json()["error"]["code"] in {
        "invalid_calibre_path",
        "calibre_library_not_found",
    }
    assert "secret" not in response.text


@pytest.mark.anyio
async def test_a_symlink_out_of_the_mount_is_not_a_way_out(tmp_path: Path) -> None:
    """Resolution happens after the string checks, which is what catches this."""
    calibre_root = tmp_path / "calibre"
    calibre_root.mkdir()
    outside = tmp_path / "outside"
    (outside / "private").mkdir(parents=True)
    (calibre_root / "escape").symlink_to(outside)
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
        listing = await client.get("/api/import/calibre/browse")
        followed = await client.get("/api/import/calibre/browse", params={"path": "escape"})

    # The link is not offered, and asking for it by name is refused.
    assert listing.json()["directories"] == []
    assert followed.status_code == 422
    assert followed.json()["error"]["code"] == "invalid_calibre_path"


@pytest.mark.anyio
async def test_an_upload_connector_has_nothing_to_browse(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.get("/api/import/goodreads/browse")
        missing = await client.get("/api/import/nowhere/browse")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "importer_not_browsable"
    assert missing.status_code == 404


@pytest.mark.anyio
async def test_a_read_failure_publishes_what_the_reader_can_do_about_it(
    tmp_path: Path,
) -> None:
    """A 422 that only says `invalid_calibre_database` is a dead end (DEC-080)."""
    calibre_root = tmp_path / "calibre"
    library = calibre_root / "broken"
    library.mkdir(parents=True)
    (library / "metadata.db").write_bytes(b"not a database at all")
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
        response = await client.post("/api/import/calibre/preview", json={"library_path": "broken"})
        empty = await client.post(
            "/api/import/goodreads/preview",
            files={"file": ("empty.csv", b"nothing,useful\n", "text/csv")},
        )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_calibre_database"
    assert error["user_message"]
    assert error["action"] == (
        "Close Calibre and try again; it locks the database while it is writing."
    )

    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "missing_columns"
    assert "goodreads.com" in empty.json()["error"]["action"]


@pytest.mark.anyio
async def test_an_ordinary_error_payload_keeps_its_shape(tmp_path: Path) -> None:
    """The two new keys appear only where a connector supplied them."""
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.post("/api/import/goodreads/preview", json={})

    assert response.status_code == 422
    assert set(response.json()["error"]) == {"code", "message", "details"}
