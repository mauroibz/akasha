"""Sprint 060, deliverable 1: a committed batch's staging directory is collected once
its undo window has passed.

Unlike `reclaim.py`'s attachment sweep, this is not deletion by inference:
`application/undo.py` never reads `data_dir / "imports" / batch_id` (verified by
grepping the whole package — only `application/imports.py`'s `preview` writes there,
and `ImportService.commit` already moves staged covers out of it before returning), so
a committed batch past its undo window has nothing left that depends on this directory.
The tests below are the two things that could make that unsafe if it were ever untrue:
the directory must survive until commit, and undo itself must be provably unaffected by
the directory having already been collected.
"""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from PIL import Image

from book_tracker.application.undo import UndoService
from book_tracker.config import Settings
from book_tracker.infrastructure.models import ImportBatchRow
from book_tracker.main import create_app
from book_tracker.reclaim import reclaim_import_batches


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _bundle_library(root: Path) -> Path:
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
    return root


def _parts(root: Path) -> list[tuple[str, tuple[str, bytes, str]]]:
    cover = "Brandon Sanderson/Mistborn_ The Final Empire (2)/cover.jpg"
    return [
        ("files", ("metadata.db", (root / "metadata.db").read_bytes(), "application/x-sqlite3")),
        ("files", (cover, (root / cover).read_bytes(), "image/jpeg")),
    ]


def _app(tmp_path: Path) -> Any:
    return create_app(
        Settings(
            data_dir=tmp_path / "data",
            calibre_dir=tmp_path / "absent",
            user_agent_contact="test@example.invalid",
        )
    )


async def _commit_a_batch(client: httpx.AsyncClient, library: Path) -> str:
    preview = await client.post("/api/import/calibre/preview", files=_parts(library))
    batch_id = str(preview.json()["batch_id"])
    committed = await client.post("/api/import/calibre/commit", json={"batch_id": batch_id})
    assert committed.status_code == 200, committed.text
    return batch_id


def _set_undo_expired(engine: Any, batch_id: str) -> None:
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        batch = session.get(ImportBatchRow, batch_id)
        assert batch is not None
        batch.undo_expires_at = (
            (datetime.now(UTC) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        )
        session.commit()


@pytest.mark.anyio
async def test_a_committed_batch_inside_its_undo_window_keeps_its_staging_directory(
    tmp_path: Path,
) -> None:
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        batch_id = await _commit_a_batch(client, library)
        staging = tmp_path / "data" / "imports" / batch_id
        report = reclaim_import_batches(app.state.engine, tmp_path / "data")

    assert report.reclaimed == ()
    assert staging.is_dir()


@pytest.mark.anyio
async def test_a_committed_batch_past_its_undo_window_is_collected(tmp_path: Path) -> None:
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        batch_id = await _commit_a_batch(client, library)
        staging = tmp_path / "data" / "imports" / batch_id
        assert staging.is_dir()
        _set_undo_expired(app.state.engine, batch_id)

        report = reclaim_import_batches(app.state.engine, tmp_path / "data")

    assert report.reclaimed == (batch_id,)
    assert not staging.exists()


@pytest.mark.anyio
async def test_undo_still_works_on_a_batch_whose_staging_was_already_collected(
    tmp_path: Path,
) -> None:
    """AC2: the staging directory being gone must not be what undo silently depends on."""
    library = _bundle_library(tmp_path / "Calibre Library")
    app = _app(tmp_path)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        batch_id = await _commit_a_batch(client, library)
        staging = tmp_path / "data" / "imports" / batch_id
        assert staging.is_dir()
        # Undo is still inside its real 24h window; only the staging directory is made
        # to look expired and collected, isolating exactly the property AC2 asks for.
        engine = app.state.engine
        report = reclaim_import_batches(
            engine, tmp_path / "data", now=datetime.now(UTC) + timedelta(hours=25)
        )
        assert report.reclaimed == (batch_id,)
        assert not staging.exists()

        undo = UndoService(engine, data_dir=tmp_path / "data")
        result = undo.undo(batch_id)

    assert result["state"] != "undone" or result["skipped"] == 0
    assert result["batch_id"] == batch_id
    assert result["reverted_items"] >= 1


def test_an_uncommitted_batch_is_never_a_candidate(tmp_path: Path) -> None:
    """A previewed-but-never-committed batch has no undo_expires_at and is left alone —
    a narrower, separate leak this sprint's acceptance criteria do not cover (see the
    function's own docstring)."""
    from book_tracker.database import create_engine
    from book_tracker.migrations import upgrade

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "imports" / "abandoned").mkdir(parents=True)
    settings = Settings(data_dir=data_dir, user_agent_contact="test@example.invalid")
    assert settings.database_url is not None
    upgrade(settings.database_url)
    engine = create_engine(settings)
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        session.add(
            ImportBatchRow(
                id="abandoned",
                kind="calibre",
                fingerprint="fp",
                state="previewed",
                source_descriptor="{}",
                preview_summary="{}",
                counters="{}",
                undo_expires_at=None,
                created_at="2020-01-01T00:00:00Z",
                updated_at="2020-01-01T00:00:00Z",
            )
        )
        session.commit()

    report = reclaim_import_batches(engine, data_dir, now=datetime.now(UTC) + timedelta(days=365))

    assert report.reclaimed == ()
    assert (data_dir / "imports" / "abandoned").is_dir()
