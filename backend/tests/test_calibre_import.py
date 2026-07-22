import hashlib
import sqlite3
from pathlib import Path

import httpx
import pytest
from PIL import Image
from sqlalchemy import text

from book_tracker.config import Settings
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
        assert record["authors"] == ["Jorge Luis Borges"]
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
                    "VALUES('Manual title',NULL,'{\"authors\":[],\"publisher\":\"Manual\"}','n','n') RETURNING id"
                )
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO item_identifiers(item_id,kind,normalized_value,value,created_at,updated_at) "
                    "VALUES(:id,'calibre_uuid','uuid-1','uuid-1','n','n')"
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
