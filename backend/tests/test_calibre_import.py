import hashlib
import json
import sqlite3
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image
from sqlalchemy import text

from book_tracker.config import Settings
from book_tracker.domain.registry import IMPORTERS
from book_tracker.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def calibre_library(root: Path, *, minimal: bool = False) -> Path:
    library = root / "library"
    library.mkdir(parents=True)
    database = library / "metadata.db"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, pubdate TEXT, path TEXT, uuid TEXT);
        CREATE TABLE authors (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE books_authors_link (book INTEGER, author INTEGER);
        CREATE TABLE identifiers (book INTEGER, type TEXT, val TEXT);
        INSERT INTO books VALUES (1, 'Ficciones', '1944-01-01', 'Borges/Ficciones (1)', 'uuid-1');
        INSERT INTO authors VALUES (1, 'Jorge Luis Borges');
        INSERT INTO books_authors_link VALUES (1, 1);
        INSERT INTO identifiers VALUES (1, 'isbn', '9780141187761');
        """
    )
    if not minimal:
        connection.executescript(
            """
            CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE books_tags_link (book INTEGER, tag INTEGER);
            CREATE TABLE comments (book INTEGER, text TEXT);
            CREATE TABLE series (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE books_series_link (book INTEGER, series INTEGER);
            CREATE TABLE ratings (id INTEGER PRIMARY KEY, rating INTEGER);
            CREATE TABLE books_ratings_link (book INTEGER, rating INTEGER);
            INSERT INTO tags VALUES (1, 'Cuentos');
            INSERT INTO books_tags_link VALUES (1, 1);
            INSERT INTO comments VALUES (1, 'Relatos completos');
            INSERT INTO series VALUES (1, 'Biblioteca Borges');
            INSERT INTO books_series_link VALUES (1, 1);
            INSERT INTO ratings VALUES (1, 9);
            INSERT INTO books_ratings_link VALUES (1, 1);
            """
        )
    connection.commit()
    connection.close()
    cover = library / "Borges/Ficciones (1)/cover.jpg"
    cover.parent.mkdir(parents=True)
    Image.new("RGB", (300, 450), "navy").save(cover, "JPEG")
    return database


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.anyio
async def test_calibre_preview_is_read_only_stages_cover_and_commit_never_rereads_source(
    tmp_path: Path,
) -> None:
    mount = tmp_path / "calibre"
    database = calibre_library(mount)
    before = digest(database)
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            calibre_dir=mount,
            user_agent_contact="test@example.invalid",
        )
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        preview = await client.post("/api/import/calibre/preview", json={"library_path": "library"})
        assert preview.status_code == 201
        record = preview.json()["records"][0]
        assert record["calibre_uuid"] == "uuid-1"
        assert record["creators"] == ["Jorge Luis Borges"]
        assert record["shelves"] == ["cuentos"]
        assert record["score"] == 9 and record["score_provisional"] is False
        assert record["description"] == "Relatos completos"
        assert record["series"] == "Biblioteca Borges"
        assert record["cover_staged"] is True
        assert record["connection_mode"] == "ro" and record["query_only"] is True
        assert digest(database) == before
        database.rename(database.with_suffix(".removed"))
        committed = await client.post(
            "/api/import/calibre/commit", json={"batch_id": preview.json()["batch_id"]}
        )
        retried = await client.post(
            "/api/import/calibre/commit", json={"batch_id": preview.json()["batch_id"]}
        )
        assert committed.status_code == 200 and retried.json() == committed.json()
        item_id = app.state.engine.connect().scalar(text("SELECT id FROM items"))
        assert (tmp_path / "data" / "covers" / f"{item_id}.jpg").is_file()
        with app.state.engine.connect() as connection:
            entry = connection.execute(
                text("SELECT status,score,score_provisional,suggested_status FROM entries")
            ).one()
            assert tuple(entry) == ("unsorted", 9, 0, None)
            assert connection.scalar(text("SELECT count(*) FROM shelves")) == 1
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM item_identifiers WHERE kind='calibre_uuid'")
                )
                == 1
            )


@pytest.mark.anyio
@pytest.mark.parametrize("library_path", ["/absolute", "../escape", "missing"])
async def test_calibre_rejects_unsafe_or_missing_paths(tmp_path: Path, library_path: str) -> None:
    mount = tmp_path / "calibre"
    mount.mkdir()
    app = create_app(
        Settings(data_dir=tmp_path / "data", calibre_dir=mount, user_agent_contact="x@y.invalid")
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.post(
            "/api/import/calibre/preview", json={"library_path": library_path}
        )
    assert response.status_code == 422
    assert str(mount) not in response.text


@pytest.mark.anyio
async def test_calibre_rejects_symlink_escape_and_non_database(tmp_path: Path) -> None:
    mount = tmp_path / "calibre"
    outside = tmp_path / "outside"
    mount.mkdir()
    outside.mkdir()
    (outside / "metadata.db").write_text("not sqlite")
    (mount / "linked").symlink_to(outside, target_is_directory=True)
    (mount / "plain").mkdir()
    (mount / "plain/metadata.db").write_text("not sqlite")
    app = create_app(
        Settings(data_dir=tmp_path / "data", calibre_dir=mount, user_agent_contact="x@y.invalid")
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        escaped = await client.post("/api/import/calibre/preview", json={"library_path": "linked"})
        invalid = await client.post("/api/import/calibre/preview", json={"library_path": "plain"})
    assert escaped.status_code == 422 and invalid.status_code == 422


@pytest.mark.anyio
async def test_calibre_minimal_schema_and_resync_fill_only(tmp_path: Path) -> None:
    mount = tmp_path / "calibre"
    calibre_library(mount, minimal=True)
    app = create_app(
        Settings(data_dir=tmp_path / "data", calibre_dir=mount, user_agent_contact="x@y.invalid")
    )
    async with app.router.lifespan_context(app):
        with app.state.engine.begin() as connection:
            item_id = connection.execute(
                text(
                    "INSERT INTO items(title,year,metadata,created_at,updated_at) "
                    'VALUES(\'Manual title\',NULL,\'{"creators":[],"publisher":"Manual"}\','
                    "'n','n') RETURNING id"
                )
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO item_identifiers("
                    "item_id,kind,normalized_value,value,created_at,updated_at) "
                    "VALUES(:id,'isbn','9780141187761','9780141187761','n','n')"
                ),
                {"id": item_id},
            )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            preview = await client.post(
                "/api/import/calibre/preview", json={"library_path": "library"}
            )
            committed = await client.post(
                "/api/import/calibre/commit", json={"batch_id": preview.json()["batch_id"]}
            )
            assert committed.status_code == 200
        with app.state.engine.connect() as connection:
            item = connection.execute(
                text("SELECT title,year,metadata FROM items WHERE id=:id"), {"id": item_id}
            ).one()
            assert item.title == "Manual title" and item.year == 1944
            assert '"publisher": "Manual"' in item.metadata
            assert "Jorge Luis Borges" in item.metadata
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM item_identifiers "
                        "WHERE item_id=:id AND kind='calibre_uuid' AND normalized_value='uuid-1'"
                    ),
                    {"id": item_id},
                )
                == 1
            )


def calibre_library_with_author_sort(root: Path) -> Path:
    """A real Calibre schema: `authors` carries the curated `sort` beside `name`."""
    library = root / "library"
    library.mkdir(parents=True)
    connection = sqlite3.connect(library / "metadata.db")
    connection.executescript(
        """
        CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, pubdate TEXT, path TEXT, uuid TEXT);
        CREATE TABLE authors (id INTEGER PRIMARY KEY, name TEXT, sort TEXT);
        CREATE TABLE books_authors_link (book INTEGER, author INTEGER);
        CREATE TABLE identifiers (book INTEGER, type TEXT, val TEXT);
        INSERT INTO books VALUES (1, 'El Aleph', '1949-01-01', '', 'uuid-1');
        INSERT INTO books VALUES (2, 'El hacedor', '1960-01-01', '', 'uuid-2');
        INSERT INTO authors VALUES (1, 'Jorge Luis Borges', 'Borges, Jorge Luis');
        -- An author row whose `sort` is empty falls back to the heuristic.
        INSERT INTO authors VALUES (2, 'Gabriel García Márquez', '');
        INSERT INTO books_authors_link VALUES (1, 1);
        INSERT INTO books_authors_link VALUES (2, 2);
        """
    )
    connection.commit()
    connection.close()
    return library / "metadata.db"


@pytest.mark.anyio
async def test_calibre_author_sort_seeds_the_creator_sort_name(tmp_path: Path) -> None:
    """Calibre's `authors.sort` is curated by hand, so it lands as the override.

    "Borges, Jorge Luis" is what the heuristic would have produced here anyway;
    the point is that it is stored as owner data rather than as a guess, so a
    later refresh or re-import cannot recompute over it.
    """
    mount = tmp_path / "calibre"
    database = calibre_library_with_author_sort(mount)
    before = digest(database)
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            calibre_dir=mount,
            user_agent_contact="test@example.invalid",
        )
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        preview = await client.post("/api/import/calibre/preview", json={"library_path": "library"})
        committed = await client.post(
            "/api/import/calibre/commit", json={"batch_id": preview.json()["batch_id"]}
        )
        assert committed.status_code == 200
        with app.state.engine.connect() as connection:
            rows = connection.execute(
                text("SELECT title, creator_sort, creator_sort_override FROM items ORDER BY id")
            ).all()
    assert digest(database) == before
    assert rows[0] == ("El Aleph", "Borges, Jorge Luis", "Borges, Jorge Luis")
    # No curated value, so the heuristic seeds it and nothing is claimed as owner data.
    assert rows[1] == ("El hacedor", "García Márquez, Gabriel", None)


@pytest.mark.anyio
async def test_calibre_without_an_author_sort_column_still_imports(tmp_path: Path) -> None:
    """The column is optional: an older or hand-built database has only `name`."""
    mount = tmp_path / "calibre"
    calibre_library(mount, minimal=True)
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            calibre_dir=mount,
            user_agent_contact="test@example.invalid",
        )
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        preview = await client.post("/api/import/calibre/preview", json={"library_path": "library"})
        assert preview.status_code == 201
        committed = await client.post(
            "/api/import/calibre/commit", json={"batch_id": preview.json()["batch_id"]}
        )
        assert committed.status_code == 200
        with app.state.engine.connect() as connection:
            row = connection.execute(
                text("SELECT creator_sort, creator_sort_override FROM items")
            ).one()
    # The heuristic, unaided: two given names is the case it gets wrong, and this
    # is what the curated column above exists to avoid.
    assert row == ("Luis Borges, Jorge", None)


def _jpeg_bytes(color: str = "navy") -> bytes:

    buffer = BytesIO()
    Image.new("RGB", (300, 450), color).save(buffer, "JPEG")
    return buffer.getvalue()


def build_calibre_export(
    root: Path,
    *,
    book_path: str = "Brandon Sanderson/Mistborn (2)",
    corrupt_checksum: bool = False,
    omit_part_one: bool = False,
) -> list[Path]:
    """A synthetic two-part "Export/import all calibre data" bundle.

    Mirrors the real format verified against actual Calibre output (part-0001 and
    part-0002 in ./exports/, kept local and never committed): part 1 holds the raw
    concatenated bytes of metadata.db, then the cover, then the ebook; part 2 holds the
    JSON manifest — with trailing junk bytes after it, exactly like the real export —
    whose offsets are relative to the start of the part that holds them, not to a
    concatenation across parts.
    """
    root.mkdir(parents=True, exist_ok=True)
    database = root / "staged.db"
    connection = sqlite3.connect(database)
    connection.executescript(
        f"""
        CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, pubdate TEXT, path TEXT, uuid TEXT);
        CREATE TABLE authors (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE books_authors_link (book INTEGER, author INTEGER);
        CREATE TABLE identifiers (book INTEGER, type TEXT, val TEXT);
        CREATE TABLE data (id INTEGER PRIMARY KEY, book INTEGER NOT NULL,
                           format TEXT NOT NULL, uncompressed_size INTEGER NOT NULL,
                           name TEXT NOT NULL);
        INSERT INTO books VALUES (2, 'Mistborn', '2006-01-01', '{book_path}', 'uuid-m1');
        INSERT INTO authors VALUES (1, 'Brandon Sanderson');
        INSERT INTO books_authors_link VALUES (2, 1);
        INSERT INTO data VALUES (1, 2, 'EPUB', 10, 'Mistborn');
        """
    )
    connection.commit()
    connection.close()
    db_bytes = database.read_bytes()
    database.unlink()
    cover_bytes = _jpeg_bytes()
    epub_bytes = b"pretend epub bytes, not a real container"

    part1 = root / "part-0001.calibre-data"
    part1.write_bytes(db_bytes + cover_bytes + epub_bytes)

    def entry(offset: int, length: int, data: bytes, *, corrupt: bool = False) -> list:
        digest = "0" * 40 if corrupt else hashlib.sha1(data).hexdigest()
        return [1, offset, length, digest, None]

    library_path = "/home/user/Calibre Library"
    manifest = {
        "file_metadata": {
            "db": entry(0, len(db_bytes), db_bytes),
            "cover": entry(len(db_bytes), len(cover_bytes), cover_bytes, corrupt=corrupt_checksum),
            "epub": entry(len(db_bytes) + len(cover_bytes), len(epub_bytes), epub_bytes),
        },
        "libraries": {library_path: 1},
        library_path: {
            "format_data": {"2": {"EPUB": "epub", ".cover": "cover"}},
            "metadata.db": "db",
            "total": 1,
            "extra_files": {"2": {}},
        },
        "config_dir": [],
    }
    part2 = root / "part-0002.calibre-data"
    part2.write_bytes(json.dumps(manifest).encode() + b"\x00trailing bytes, not json")

    if omit_part_one:
        part1.unlink()
        return [part2]
    return [part1, part2]


def _export_files(
    paths: list[Path],
) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("parts", (path.name, path.read_bytes(), "application/octet-stream")) for path in paths]


def _no_mount_app(tmp_path: Path) -> object:
    return create_app(
        Settings(
            data_dir=tmp_path / "data",
            calibre_dir=tmp_path / "absent",
            user_agent_contact="test@example.invalid",
        )
    )


@pytest.mark.anyio
async def test_a_calibre_export_previews_and_attaches_its_ebook_automatically(
    tmp_path: Path,
) -> None:
    """The export path is the one place attachment needs no second upload."""
    parts = build_calibre_export(tmp_path / "export")
    app = _no_mount_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        preview = await client.post("/api/import/calibre/preview", files=_export_files(parts))
        assert preview.status_code == 201, preview.text
        record = preview.json()["records"][0]
        assert record["title"] == "Mistborn"
        assert record["creators"] == ["Brandon Sanderson"]
        assert record["calibre_uuid"] == "uuid-m1"
        assert record["cover_staged"] is True
        assert record["attachment_staged"] is True

        committed = await client.post(
            "/api/import/calibre/commit", json={"batch_id": preview.json()["batch_id"]}
        )
        assert committed.status_code == 200
        item_id = app.state.engine.connect().scalar(text("SELECT id FROM items"))
        listed = await client.get(f"/api/items/{item_id}/attachments")
        assert [row["filename"] for row in listed.json()["attachments"]] == ["Mistborn.epub"]


@pytest.mark.anyio
async def test_a_calibre_export_manifest_may_arrive_in_either_part(tmp_path: Path) -> None:
    """The manifest is found by content, not by name or upload order."""
    parts = build_calibre_export(tmp_path / "export")
    app = _no_mount_app(tmp_path)
    # The manifest lives in the higher-numbered file; upload it first anyway.
    reordered = _export_files(list(reversed(parts)))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.post("/api/import/calibre/preview", files=reordered)
    assert response.status_code == 201, response.text
    assert response.json()["records"][0]["title"] == "Mistborn"


@pytest.mark.anyio
async def test_a_calibre_export_missing_a_referenced_part_is_refused(tmp_path: Path) -> None:
    parts = build_calibre_export(tmp_path / "export", omit_part_one=True)
    app = _no_mount_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.post("/api/import/calibre/preview", files=_export_files(parts))
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "invalid_calibre_export"


@pytest.mark.anyio
async def test_a_calibre_export_with_a_corrupted_checksum_is_refused(tmp_path: Path) -> None:
    parts = build_calibre_export(tmp_path / "export", corrupt_checksum=True)
    app = _no_mount_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.post("/api/import/calibre/preview", files=_export_files(parts))
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "invalid_calibre_export"


@pytest.mark.anyio
async def test_a_calibre_export_naming_a_book_path_outside_the_library_is_refused(
    tmp_path: Path,
) -> None:
    """A malicious `books.path` is a write-side traversal attempt, refused the same
    way a read-side one already is."""
    parts = build_calibre_export(tmp_path / "export", book_path="../../escape")
    app = _no_mount_app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.post("/api/import/calibre/preview", files=_export_files(parts))
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "invalid_calibre_export"
    assert not (tmp_path / "escape").exists()


@pytest.mark.anyio
async def test_a_calibre_export_rejects_an_undeclared_file(tmp_path: Path) -> None:
    parts = build_calibre_export(tmp_path / "export")
    app = _no_mount_app(tmp_path)
    files = [*_export_files(parts), ("parts", ("notes.txt", b"hello", "text/plain"))]
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.post("/api/import/calibre/preview", files=files)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "invalid_import_source"


@pytest.mark.anyio
async def test_a_calibre_export_over_the_declared_file_cap_is_refused(tmp_path: Path) -> None:
    export = IMPORTERS["calibre"].input.alternates
    spec = next(alternate for alternate in export if alternate.kind == "export")
    assert spec.max_files
    parts = build_calibre_export(tmp_path / "export")
    app = _no_mount_app(tmp_path)
    too_many = [
        *_export_files(parts),
        *[
            ("parts", (f"part-{index:04d}.calibre-data", b"x", "application/octet-stream"))
            for index in range(3, spec.max_files + 3)
        ],
    ]
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.post("/api/import/calibre/preview", files=too_many)
    assert response.status_code == 413, response.text


@pytest.mark.anyio
async def test_a_calibre_export_and_a_mount_normalize_the_same_book_identically(
    tmp_path: Path,
) -> None:
    """The export path shares the same reader as every other path (DEC-081, generalized):
    only `attachment_staged` differs, because only the export has the ebook bytes."""
    book_path = "Brandon Sanderson/Mistborn (2)"
    mount = tmp_path / "calibre"
    library = mount / "library"
    library.mkdir(parents=True)
    connection = sqlite3.connect(library / "metadata.db")
    connection.executescript(
        f"""
        CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, pubdate TEXT, path TEXT, uuid TEXT);
        CREATE TABLE authors (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE books_authors_link (book INTEGER, author INTEGER);
        CREATE TABLE identifiers (book INTEGER, type TEXT, val TEXT);
        CREATE TABLE data (id INTEGER PRIMARY KEY, book INTEGER NOT NULL,
                           format TEXT NOT NULL, uncompressed_size INTEGER NOT NULL,
                           name TEXT NOT NULL);
        INSERT INTO books VALUES (2, 'Mistborn', '2006-01-01', '{book_path}', 'uuid-m1');
        INSERT INTO authors VALUES (1, 'Brandon Sanderson');
        INSERT INTO books_authors_link VALUES (2, 1);
        INSERT INTO data VALUES (1, 2, 'EPUB', 10, 'Mistborn');
        """
    )
    connection.commit()
    connection.close()
    cover = library / book_path / "cover.jpg"
    cover.parent.mkdir(parents=True)
    cover.write_bytes(_jpeg_bytes())

    mounted = create_app(
        Settings(data_dir=tmp_path / "mounted-data", calibre_dir=mount, user_agent_contact="x@y.z")
    )
    async with (
        mounted.router.lifespan_context(mounted),
        httpx.AsyncClient(transport=httpx.ASGITransport(mounted), base_url="http://test") as client,
    ):
        via_mount = await client.post(
            "/api/import/calibre/preview", json={"library_path": "library"}
        )
    assert via_mount.status_code == 201, via_mount.text

    parts = build_calibre_export(tmp_path / "export", book_path=book_path)
    uploaded = _no_mount_app(tmp_path)
    async with (
        uploaded.router.lifespan_context(uploaded),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(uploaded), base_url="http://test"
        ) as client,
    ):
        via_export = await client.post("/api/import/calibre/preview", files=_export_files(parts))
    assert via_export.status_code == 201, via_export.text

    def comparable(payload: dict) -> dict:
        row = dict(payload["records"][0])
        row.pop("record_id")
        row.pop("attachment_staged")
        return row

    assert comparable(via_export.json()) == comparable(via_mount.json())
    assert via_mount.json()["records"][0]["attachment_staged"] is False
    assert via_export.json()["records"][0]["attachment_staged"] is True
    assert via_export.json()["fingerprint"] == via_mount.json()["fingerprint"]
