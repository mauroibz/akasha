import json
import sqlite3
import tempfile
import tracemalloc
from pathlib import Path, PurePosixPath
from typing import Any

import httpx
import pytest
from PIL import Image
from sqlalchemy import text
from sqlalchemy.orm import Session

from book_tracker.api.imports import MAX_IMPORT_BYTES, _DiskSpooledMultiPart
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
from book_tracker.domain.registry import IMPORTERS
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
    item_types = ("album",)
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
    # Derived, not spelled. This asserted `["goodreads", "calibre"]` and would have
    # failed the moment a third connector registered, with no behaviour changing — the
    # fourth instance of that defect class in four sprints (DEC-090, DEC-091, DEC-092).
    from book_tracker.domain.registry import IMPORTERS

    assert [row["id"] for row in published] == list(IMPORTERS)

    goodreads, calibre = published[0], published[1]
    assert goodreads["input"]["kind"] == "upload"
    assert goodreads["input"]["accept"] == ".csv,text/csv"
    assert goodreads["input"]["browsable"] is False
    assert goodreads["input"]["alternates"] == []

    # Calibre leads with the folder chooser and keeps the mount and the export bundle
    # beneath it, published as one input with alternates rather than as three
    # connectors (DEC-081, generalized).
    assert calibre["input"]["kind"] == "directory"
    assert calibre["input"]["accepts_files"] is True
    assert calibre["input"]["max_bytes"] > 5 * 1024 * 1024
    assert calibre["input"]["max_files"] > 0
    alternates = {alternate["kind"]: alternate for alternate in calibre["input"]["alternates"]}
    assert alternates["path"]["browsable"] is True
    assert alternates["export"]["accepts_files"] is True
    # One deep, so the screen never has to recurse.
    assert alternates["path"]["alternates"] == []
    assert alternates["export"]["alternates"] == []

    # The screen renders what the connector declares, so what it declares has to
    # arrive intact: ordered steps, an empty state and an https help address.
    for row in published:
        spec = row["input"]
        assert spec["guide"] and all(step.strip() for step in spec["guide"])
        assert spec["empty_state"]
        assert spec["help_url"].startswith("https://")
    assert any("review/import" in step for step in goodreads["input"]["guide"])
    assert any("provisional" in step.lower() for step in goodreads["input"]["guide"])
    assert any("metadata.db" in step for step in calibre["input"]["guide"])


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

        # The third connector, and the first for a domain that is not books. It goes
        # through the same two routes with no shared code knowing it exists — which is
        # the whole claim Sprint 032's boundary makes.
        mal = await client.post(
            "/api/import/myanimelist/preview",
            files={
                "file": (
                    "animelist.xml",
                    (FIXTURES / "imports" / "myanimelist_sample.xml").read_bytes(),
                    "text/xml",
                )
            },
        )
        assert mal.status_code == 201, mal.text
        assert mal.json()["summary"]["total"] == 8
        mal_commit = await client.post(
            "/api/import/myanimelist/commit", json={"batch_id": mal.json()["batch_id"]}
        )
        assert mal_commit.status_code == 200
        assert mal_commit.json()["created_entries"] == 8

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
        (
            {"creators": []},
            {"future_domain_value": "would otherwise reach storage"},
            "Album entries have no declared value 'future_domain_value'",
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


def _bundle_library(root: Path) -> Path:
    """A Calibre library with a real book path, so it has a cover to carry."""
    root.mkdir(parents=True, exist_ok=True)
    book_path = "Brandon Sanderson/Mistborn_ The Final Empire (2)"
    connection = sqlite3.connect(root / "metadata.db")
    connection.executescript(
        f"""
        CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, pubdate TEXT, path TEXT, uuid TEXT);
        CREATE TABLE authors (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE books_authors_link (book INTEGER, author INTEGER);
        CREATE TABLE identifiers (book INTEGER, type TEXT, val TEXT);
        CREATE TABLE data (id INTEGER PRIMARY KEY, book INTEGER NOT NULL,
                           format TEXT NOT NULL, uncompressed_size INTEGER NOT NULL,
                           name TEXT NOT NULL);
        INSERT INTO books VALUES (1, 'Mistborn', '2006-01-01', '{book_path}', 'uuid-m1');
        INSERT INTO authors VALUES (1, 'Brandon Sanderson');
        INSERT INTO books_authors_link VALUES (1, 1);
        INSERT INTO data VALUES (1, 1, 'EPUB', 10, 'book');
        """
    )
    connection.commit()
    connection.close()
    cover = root / book_path / "cover.jpg"
    cover.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (300, 450), "navy").save(cover, "JPEG")
    # The noise a real library carries and a bundle must not.
    (root / book_path / "book.epub").write_bytes(b"epub bytes")
    (root / ".caltrash" / "b" / "1").mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (10, 10), "red").save(root / ".caltrash/b/1/cover.jpg", "JPEG")
    return root


def _parts(root: Path) -> list[tuple[str, tuple[str, bytes, str]]]:
    """The multipart body the client builds: relative path as the part filename."""
    cover = "Brandon Sanderson/Mistborn_ The Final Empire (2)/cover.jpg"
    return [
        ("files", ("metadata.db", (root / "metadata.db").read_bytes(), "application/x-sqlite3")),
        ("files", (cover, (root / cover).read_bytes(), "image/jpeg")),
    ]


def _no_mount_app(tmp_path: Path) -> Any:
    """Deliberately no mount that exists: the point is importing without one."""
    return create_app(
        Settings(
            data_dir=tmp_path / "data",
            calibre_dir=tmp_path / "absent",
            user_agent_contact="test@example.invalid",
        )
    )


@pytest.mark.anyio
async def test_a_calibre_library_imports_with_no_mount_at_all(tmp_path: Path) -> None:
    """The point of DEC-081: no CALIBRE_DIR, no restart, cover intact."""
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _no_mount_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.post("/api/import/calibre/preview", files=_parts(library))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["summary"]["total"] == 1
    record = body["records"][0]
    assert record["title"] == "Mistborn"
    # The cover came from the bundle: no mount and no provider was involved.
    assert record["cover_staged"] is True


@pytest.mark.anyio
async def test_the_bundle_is_read_by_the_same_adapter_as_a_mount(tmp_path: Path) -> None:
    """An uploaded library and a mounted one normalize identically (deliverable 3)."""
    library = _bundle_library(tmp_path / "Calibre Library")

    mounted = create_app(
        Settings(
            data_dir=tmp_path / "mounted-data",
            calibre_dir=tmp_path,
            user_agent_contact="test@example.invalid",
        )
    )
    async with (
        mounted.router.lifespan_context(mounted),
        httpx.AsyncClient(transport=httpx.ASGITransport(mounted), base_url="http://test") as c,
    ):
        via_mount = await c.post(
            "/api/import/calibre/preview", json={"library_path": "Calibre Library"}
        )

    uploaded = _no_mount_app(tmp_path)
    async with (
        uploaded.router.lifespan_context(uploaded),
        httpx.AsyncClient(transport=httpx.ASGITransport(uploaded), base_url="http://test") as c,
    ):
        via_upload = await c.post("/api/import/calibre/preview", files=_parts(library))

    assert via_mount.status_code == 201, via_mount.text
    assert via_upload.status_code == 201, via_upload.text

    def comparable(payload: dict[str, Any]) -> Any:
        return [
            {key: value for key, value in row.items() if key != "record_id"}
            for row in payload["records"]
        ]

    assert comparable(via_upload.json()) == comparable(via_mount.json())
    # The fingerprint is the database's digest, so one library fingerprints the same
    # however it arrived — which is what makes a replay across both paths idempotent.
    assert via_upload.json()["fingerprint"] == via_mount.json()["fingerprint"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "member",
    [
        "/etc/passwd",
        "../../etc/passwd",
        "books/../../escape/cover.jpg",
        ".caltrash/b/1/cover.jpg",
        ".secret",
        # Declared formats are accepted now (DEC-083); an undeclared one is not.
        "Author/Book/book.mp3",
        "Author/Book/notes.docx",
        "Author/Book/metadata.opf",
        "Author/metadata.db",
    ],
)
async def test_a_bundle_member_the_connector_did_not_ask_for_is_refused(
    tmp_path: Path, member: str
) -> None:
    """Member paths come from the client, so they are checked before a byte is written."""
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _no_mount_app(tmp_path)
    parts = [*_parts(library), ("files", (member, b"payload", "application/octet-stream"))]
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.post("/api/import/calibre/preview", files=parts)

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "invalid_import_source"
    assert not (tmp_path / "escape").exists()
    assert not (tmp_path / "passwd").exists()


@pytest.mark.anyio
async def test_a_bundle_without_a_database_is_refused_with_something_to_do(
    tmp_path: Path,
) -> None:
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _no_mount_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.post("/api/import/calibre/preview", files=[_parts(library)[1]])

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_import_source"
    assert response.json()["error"]["action"]


@pytest.mark.anyio
async def test_a_bundle_over_the_declared_caps_is_refused(tmp_path: Path) -> None:
    """The caps are the connector's, not the shared route's 5 MiB (deliverable 1)."""
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _no_mount_app(tmp_path)
    calibre = IMPORTERS["calibre"]
    assert calibre.input.max_bytes and calibre.input.max_bytes > MAX_IMPORT_BYTES
    assert calibre.input.max_files

    oversize = [
        *_parts(library),
        ("files", ("Author/Big (1)/cover.jpg", b"x" * (calibre.input.max_bytes + 1), "image/jpeg")),
    ]
    too_many = [
        _parts(library)[0],
        *[
            ("files", (f"Author/Book {index} (1)/cover.jpg", b"x", "image/jpeg"))
            for index in range(calibre.input.max_files + 1)
        ],
    ]
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        big = await client.post("/api/import/calibre/preview", files=oversize)
        many = await client.post("/api/import/calibre/preview", files=too_many)

    assert big.status_code == 413, big.text
    assert many.status_code == 413, many.text


@pytest.mark.anyio
async def test_a_large_bundle_is_streamed_rather_than_held_in_memory(tmp_path: Path) -> None:
    """AC5: peak tracks one member, not the shelf.

    Starlette spools a part to disk only past 1 MiB, and a cover is smaller than that,
    so the default parser would hold an entire library of covers in memory at once.
    `_DiskSpooledMultiPart` is what makes this bound hold; without it this test fails by
    roughly the size of the bundle.
    """
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _no_mount_app(tmp_path)
    cover = b"\xff\xd8" + b"z" * (1024 * 1024)
    parts = [_parts(library)[0]]
    parts += [
        ("files", (f"Author/Book {index} (1)/cover.jpg", cover, "image/jpeg"))
        for index in range(60)
    ]
    bundle_bytes = sum(len(part[1][1]) for part in parts)
    assert bundle_bytes > 10 * MAX_IMPORT_BYTES

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        tracemalloc.start()
        response = await client.post("/api/import/calibre/preview", files=parts)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

    assert response.status_code == 201, response.text
    # Measured at ~1.8 MiB for a 60 MiB bundle. The bound is generous against noise
    # and still an order of magnitude below the payload, which is the property.
    assert peak < 8 * 1024 * 1024, f"peak {peak / 1048576:.1f} MiB for {bundle_bytes} bytes"


def test_every_uploaded_part_is_spooled_to_disk() -> None:
    """The mechanism the bound above rests on, asserted directly.

    `SpooledTemporaryFile` rolls over only when `max_size > 0` and a write exceeds it,
    so 0 would mean *never* roll. 1 means roll on first write. This is easy to "tidy"
    into 0 later and silently lose the property, so it is pinned.
    """
    assert _DiskSpooledMultiPart.spool_max_size == 1
    with tempfile.SpooledTemporaryFile(max_size=_DiskSpooledMultiPart.spool_max_size) as spooled:
        spooled.write(b"x" * 4096)
        assert spooled._rolled, "parts must reach disk, not stay in memory"


def _manifest(root: Path) -> str:
    parts = _parts(root)
    return json.dumps([{"path": p[1][0], "size": len(p[1][1])} for p in parts])


async def _plan(client: httpx.AsyncClient, root: Path, importer: str = "calibre") -> Any:
    return await client.post(
        f"/api/import/{importer}/plan",
        files=_parts(root),
        data={"manifest": _manifest(root)},
    )


@pytest.mark.anyio
async def test_an_empty_library_wants_everything_offered(tmp_path: Path) -> None:
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _no_mount_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await _plan(client, library)

    assert response.status_code == 200, response.text
    body = response.json()
    assert sorted(body["wanted"]) == sorted(
        ["metadata.db", "Brandon Sanderson/Mistborn_ The Final Empire (2)/cover.jpg"]
    )
    assert body["holding"] == 0


@pytest.mark.anyio
async def test_an_unchanged_library_wants_only_the_database(tmp_path: Path) -> None:
    """The point of DEC-082: a re-sync that changes nothing moves 416 KB, not 10 MB."""
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _no_mount_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        preview = await client.post("/api/import/calibre/preview", files=_parts(library))
        await client.post(
            "/api/import/calibre/commit", json={"batch_id": preview.json()["batch_id"]}
        )
        response = await _plan(client, library)

    body = response.json()
    assert body["wanted"] == ["metadata.db"], body
    assert body["holding"] == 1
    assert "already in your library" in (body["reason"] or "")


@pytest.mark.anyio
async def test_an_item_without_a_cover_is_offered_one_again(tmp_path: Path) -> None:
    """A failed first attempt heals; it is not skipped forever (AC3)."""
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _no_mount_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        preview = await client.post("/api/import/calibre/preview", files=_parts(library))
        await client.post(
            "/api/import/calibre/commit", json={"batch_id": preview.json()["batch_id"]}
        )
        # The book is held, but its picture never landed.
        with Session(app.state.engine) as session:
            session.execute(text("UPDATE items SET cover_path = NULL"))
            session.commit()
        response = await _plan(client, library)

    assert sorted(response.json()["wanted"]) == sorted(
        ["metadata.db", "Brandon Sanderson/Mistborn_ The Final Empire (2)/cover.jpg"]
    )
    assert response.json()["holding"] == 0


@pytest.mark.anyio
async def test_planning_refuses_what_the_upload_route_refuses(tmp_path: Path) -> None:
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _no_mount_app(tmp_path)
    parts = [*_parts(library), ("files", ("../escape.jpg", b"x", "image/jpeg"))]
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.post(
            "/api/import/calibre/plan", files=parts, data={"manifest": _manifest(library)}
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_import_source"
    assert not (tmp_path / "escape.jpg").exists()


@pytest.mark.anyio
async def test_a_connector_that_does_not_plan_has_no_plan_route(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.post(
            "/api/import/goodreads/plan",
            files={"file": ("library.csv", b"a,b\n", "text/csv")},
            data={"manifest": "[]"},
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "importer_not_incremental"


@pytest.mark.anyio
async def test_planning_leaves_no_bundle_behind(tmp_path: Path) -> None:
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _no_mount_app(tmp_path)
    before = set(Path(tempfile.gettempdir()).glob("akasha-import-*"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        await _plan(client, library)
        await client.post(
            "/api/import/calibre/plan",
            files=[*_parts(library), ("files", ("../x.jpg", b"x", "image/jpeg"))],
            data={"manifest": _manifest(library)},
        )

    assert set(Path(tempfile.gettempdir()).glob("akasha-import-*")) == before


EBOOK = "Brandon Sanderson/Mistborn_ The Final Empire (2)/book.epub"


def _manifest_with_files(root: Path) -> str:
    """What the client offers with the ebook toggle on: covers *and* the files."""
    rows = json.loads(_manifest(root))
    rows.append({"path": EBOOK, "size": (root / EBOOK).stat().st_size})
    return json.dumps(rows)


async def _plan_with_files(client: httpx.AsyncClient, root: Path) -> Any:
    return await client.post(
        "/api/import/calibre/plan",
        files=_parts(root),
        data={"manifest": _manifest_with_files(root)},
    )


@pytest.mark.anyio
async def test_an_offered_ebook_is_wanted_when_the_library_holds_no_file(tmp_path: Path) -> None:
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _no_mount_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await _plan_with_files(client, library)

    assert response.status_code == 200, response.text
    assert EBOOK in response.json()["wanted"]


@pytest.mark.anyio
async def test_an_ebook_the_library_already_holds_is_not_wanted(tmp_path: Path) -> None:
    """Planned by identity and filename, so a re-sync sends no file it already has."""
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _no_mount_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        preview = await client.post("/api/import/calibre/preview", files=_parts(library))
        await client.post(
            "/api/import/calibre/commit", json={"batch_id": preview.json()["batch_id"]}
        )
        item_id = _only_item(app)
        attached = await client.post(
            f"/api/items/{item_id}/attachments",
            files={"file": ("book.epub", b"epub bytes", "application/epub+zip")},
        )
        assert attached.status_code == 201, attached.text
        response = await _plan_with_files(client, library)

        assert EBOOK not in response.json()["wanted"], response.text

        # AC4: deleting it in Akasha makes the next import want that one file again.
        await client.delete(f"/api/items/{item_id}/attachments/{attached.json()['id']}")
        again = await _plan_with_files(client, library)

    assert EBOOK in again.json()["wanted"]


@pytest.mark.anyio
async def test_an_item_with_a_cover_but_no_file_still_wants_its_file(tmp_path: Path) -> None:
    """ "Already imported", "has a picture" and "holds the file" are three questions."""
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _no_mount_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        preview = await client.post("/api/import/calibre/preview", files=_parts(library))
        await client.post(
            "/api/import/calibre/commit", json={"batch_id": preview.json()["batch_id"]}
        )
        response = await _plan_with_files(client, library)

    body = response.json()
    assert sorted(body["wanted"]) == sorted([EBOOK, "metadata.db"]), body
    assert body["holding"] == 1


def _only_item(app: Any) -> int:
    with Session(app.state.engine) as session:
        return int(session.execute(text("SELECT id FROM items")).scalars().one())


async def _import(client: httpx.AsyncClient, library: Path) -> str:
    preview = await client.post("/api/import/calibre/preview", files=_parts(library))
    batch_id = str(preview.json()["batch_id"])
    await client.post("/api/import/calibre/commit", json={"batch_id": batch_id})
    return batch_id


def _file_part(library: Path, path: str = EBOOK) -> dict[str, Any]:
    return {
        "files": {
            "file": (
                PurePosixPath(path).name,
                (library / path).read_bytes(),
                "application/epub+zip",
            )
        },
        "data": {"path": path},
    }


@pytest.mark.anyio
async def test_a_committed_batch_takes_the_file_its_record_named(tmp_path: Path) -> None:
    """The path resolves to a record through `source_files`, and to that record's item."""
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _no_mount_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        batch_id = await _import(client, library)
        response = await client.post(
            f"/api/import/calibre/batches/{batch_id}/files", **_file_part(library)
        )
        item_id = _only_item(app)
        listed = await client.get(f"/api/items/{item_id}/attachments")

    assert response.status_code == 201, response.text
    assert response.json()["filename"] == "book.epub"
    assert [row["filename"] for row in listed.json()["attachments"]] == ["book.epub"]


@pytest.mark.anyio
async def test_a_file_over_the_cap_is_refused_and_leaves_nothing_behind(tmp_path: Path) -> None:
    """AC5: named and skipped, never a half-stored blob."""
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _no_mount_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        batch_id = await _import(client, library)
        cap = int(app.state.attachment_max_bytes)
        response = await client.post(
            f"/api/import/calibre/batches/{batch_id}/files",
            files={"file": ("book.epub", b"x" * (cap + 1), "application/epub+zip")},
            data={"path": EBOOK},
        )
        listed = await client.get(f"/api/items/{_only_item(app)}/attachments")

    assert response.status_code == 413, response.text
    assert listed.json()["attachments"] == []
    store = tmp_path / "data" / "attachments"
    assert not [blob for blob in store.rglob("*") if blob.is_file()]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path",
    [
        "../escape.epub",
        ".caltrash/b/1/book.epub",
        "Brandon Sanderson/Mistborn_ The Final Empire (2)/notes.docx",
    ],
)
async def test_the_file_route_refuses_what_the_upload_route_refuses(
    tmp_path: Path, path: str
) -> None:
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _no_mount_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        batch_id = await _import(client, library)
        response = await client.post(
            f"/api/import/calibre/batches/{batch_id}/files",
            files={"file": ("x.epub", b"payload", "application/epub+zip")},
            data={"path": path},
        )

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "invalid_import_source"
    assert not (tmp_path / "escape.epub").exists()


@pytest.mark.anyio
async def test_a_file_no_record_claims_is_refused(tmp_path: Path) -> None:
    """A declared shape is not a promise that this batch has that book."""
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _no_mount_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        batch_id = await _import(client, library)
        response = await client.post(
            f"/api/import/calibre/batches/{batch_id}/files",
            files={"file": ("other.epub", b"payload", "application/epub+zip")},
            data={"path": "Someone Else/A Book (9)/other.epub"},
        )

    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "import_file_not_wanted"


@pytest.mark.anyio
async def test_a_batch_that_has_not_committed_takes_no_files(tmp_path: Path) -> None:
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _no_mount_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        preview = await client.post("/api/import/calibre/preview", files=_parts(library))
        pending = str(preview.json()["batch_id"])
        response = await client.post(
            f"/api/import/calibre/batches/{pending}/files", **_file_part(library)
        )
        missing = await client.post(
            "/api/import/calibre/batches/does-not-exist/files", **_file_part(library)
        )

    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "import_batch_not_committed"
    assert missing.status_code == 404


@pytest.mark.anyio
async def test_the_same_file_twice_is_one_attachment(tmp_path: Path) -> None:
    """Retrying a request that timed out must not double the row or the blob."""
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _no_mount_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        batch_id = await _import(client, library)
        first = await client.post(
            f"/api/import/calibre/batches/{batch_id}/files", **_file_part(library)
        )
        second = await client.post(
            f"/api/import/calibre/batches/{batch_id}/files", **_file_part(library)
        )
        listed = await client.get(f"/api/items/{_only_item(app)}/attachments")

    assert first.status_code == 201 and second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]
    assert len(listed.json()["attachments"]) == 1


@pytest.mark.anyio
async def test_the_attachment_cap_is_published_with_the_registry(tmp_path: Path) -> None:
    """So the client can refuse a too-large file before spending the upload."""
    app = _no_mount_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.get("/api/importers")

    calibre = next(row for row in response.json() if row["id"] == "calibre")
    assert calibre["attachment_max_bytes"] == 25 * 1024 * 1024


@pytest.mark.anyio
async def test_undoing_an_import_takes_back_the_files_it_attached(tmp_path: Path) -> None:
    """AC6: undo returns the library to where it was, rows and bytes alike."""
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _no_mount_app(tmp_path)
    store = tmp_path / "data" / "attachments"
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        batch_id = await _import(client, library)
        await client.post(f"/api/import/calibre/batches/{batch_id}/files", **_file_part(library))
        assert [blob for blob in store.rglob("*") if blob.is_file()]

        undone = await client.delete(f"/api/import/batches/{batch_id}")

    assert undone.status_code == 200, undone.text
    with Session(app.state.engine) as session:
        assert session.execute(text("SELECT count(*) FROM attachments")).scalar_one() == 0
        assert session.execute(text("SELECT count(*) FROM items")).scalar_one() == 0
    assert not [blob for blob in store.rglob("*") if blob.is_file()]


def test_the_inventory_answers_in_a_bounded_number_of_queries(tmp_path: Path) -> None:
    """AC5: a bigger shelf must not mean a query per book."""
    from sqlalchemy import event

    from book_tracker.database import create_engine
    from book_tracker.infrastructure.repositories import DomainRepository
    from book_tracker.migrations import upgrade

    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url)
    repository = DomainRepository(create_engine(configured))
    engine = repository.engine

    statements: list[str] = []
    event.listen(engine, "before_cursor_execute", lambda *a: statements.append(a[2]))

    values = [f"uuid-{index}" for index in range(1200)]
    repository.with_cover("calibre_uuid", values)
    # 1200 values, chunked at 500: three statements, not twelve hundred.
    assert len(statements) == 3, statements

    # The third question is bounded the same way, for the same reason (AC9).
    statements.clear()
    assert repository.attached("calibre_uuid", values) == {}
    assert len(statements) == 3, statements


@pytest.mark.anyio
async def test_the_import_path_refuses_a_progress_the_domain_does_not_record(
    tmp_path: Path,
) -> None:
    """Sprint 040 wired the write and not the guard, and said otherwise.

    The old passage-field validator was a denylist, so `progress`—deliberately not one
    of those fields—passed straight through it. The value reached the column
    unvalidated: a domain declaring no `ProgressSpec` could be given one, and a negative
    would be stored, where the PATCH and add paths refused both. The unified allowlist
    keeps this regression case on the import boundary.
    """
    from book_tracker.application.imports import ImportService
    from book_tracker.application.library import LibraryError
    from book_tracker.domain.importers import ImportEntry, ImportItem, NormalizedImportRecord
    from book_tracker.domain.registry import IMPORTERS

    def record(item_type_progress: int | None) -> NormalizedImportRecord:
        return NormalizedImportRecord(
            row_number=2,
            item=ImportItem(title="Rayuela", subtitle=None, year=None, identifiers={}, metadata={}),
            entry=ImportEntry(
                score=None,
                notes=None,
                date_added=None,
                values={"progress": item_type_progress},
            ),
            shelves=(),
            errors=(),
            source_fields={},
        )

    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        # Goodreads targets books, and a book records no progress at all.
        service = ImportService(app.state.engine, tmp_path, tmp_path, IMPORTERS["goodreads"])
        with pytest.raises(LibraryError) as refused:
            service._validate(record(3))
        assert service._validate(record(None)) == {"progress": None}
    assert refused.value.status_code == 422
    assert "progress" in str(refused.value).lower() or "Book" in str(refused.value)


class _CapFixtureImporter:
    """An upload-only connector with no alternate, declaring its own byte cap.

    No production connector does this yet (Sprint 060's own baseline note), so the
    only way to prove the upload branch reads `spec.max_bytes` rather than the
    module default is a fixture connector built for exactly that.
    """

    name = "cap_fixture"
    label = "Cap Fixture"
    item_types: tuple[str, ...] = ("book",)
    input = ImportInputSpec(kind="upload", label="Fixture", field="file", max_bytes=1000)
    identity_kinds: frozenset[str] = frozenset()

    def read(self, source: ImportSource, _context: ImportReadContext) -> ImportSnapshot:
        return ImportSnapshot(
            fingerprint=f"cap-{len(source.data or b'')}",
            filename="fixture",
            source_descriptor={},
            records=(
                NormalizedImportRecord(
                    row_number=1,
                    item=ImportItem(
                        title="Cap Fixture Book",
                        subtitle=None,
                        year=None,
                        identifiers={},
                        metadata={},
                    ),
                    entry=ImportEntry(score=None, notes=None, date_added=None, values={}),
                    shelves=(),
                    errors=(),
                    source_fields={},
                ),
            ),
        )

    def stage(self, snapshot: ImportSnapshot, _directory: Path, _data_dir: Path) -> ImportSnapshot:
        return snapshot

    def match(self, record: NormalizedImportRecord, matcher: Any) -> MatchDecision:
        return matcher.match(identifiers=[], title=record.item.title, first_author="")


@pytest.mark.anyio
async def test_a_declared_upload_cap_is_honoured_in_both_directions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deliverable 5: the upload branch reads `spec.max_bytes`, not just the directory
    branch — a connector declaring a larger cap accepts what the module default would
    have refused, and its own refusal still fires above that larger cap."""
    import book_tracker.api.imports as imports_module

    monkeypatch.setattr(imports_module, "MAX_IMPORT_BYTES", 100)
    monkeypatch.setitem(IMPORTERS, "cap_fixture", _CapFixtureImporter())

    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        accepted = await client.post(
            "/api/import/cap_fixture/preview",
            files={"file": ("fixture.csv", b"x" * 500, "text/csv")},
        )
        assert accepted.status_code == 201, accepted.text

        refused = await client.post(
            "/api/import/cap_fixture/preview",
            files={"file": ("fixture.csv", b"x" * 1500, "text/csv")},
        )

    assert refused.status_code == 413, refused.text
    body = refused.json()["error"]
    assert body["code"] == "import_too_large"
    # No alternate on this connector, so the refusal must not suggest one that does
    # not exist (deliverable 5's other half: "offers the alternate only when declared").
    assert "mounted path" not in body["action"]
    assert "Export a smaller file" in body["action"]
