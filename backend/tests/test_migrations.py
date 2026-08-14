"""Migration 0007 rewrites every item row, so upgrading is a data operation.

These tests cover the guard around it: an existing library is copied before the
schema moves, a fresh install is not slowed down by a backup of nothing, and a
backup that cannot be written stops the upgrade rather than proceeding blind.
"""

import json
import sqlite3
from pathlib import Path

import httpx
import pytest

from book_tracker.application.library import LibraryService
from book_tracker.backup import read_manifest, verify_backup
from book_tracker.config import Settings
from book_tracker.main import _back_up_before_migrating, create_app
from book_tracker.migrations import alembic_config, pending_revisions, upgrade

PRE_PROJECTION = "0006_job_error_code"
NOW = "2026-08-13T00:00:00+00:00"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def database_at(data_dir: Path, revision: str) -> Settings:
    data_dir.mkdir(parents=True, exist_ok=True)
    configured = Settings(
        data_dir=data_dir,
        backup_dir=data_dir.parent / "backups",
        user_agent_contact="test@example.invalid",
    )
    assert configured.database_url is not None
    upgrade(configured.database_url, revision=revision)
    return configured


def seed_accented_library(database_path: Path) -> None:
    """Rows written the way 0006 knew how: no normalized projection columns."""
    connection = sqlite3.connect(database_path)
    for index, (title, author) in enumerate(
        [
            ("Ávila", "Ángela Ruiz"),
            ("Zurita", "Zoé Valdés"),
            ("Ébano", "Ernesto Sábato"),
        ],
        start=1,
    ):
        connection.execute(
            "INSERT INTO items (id, type, title, identifiers, metadata, created_at, updated_at)"
            " VALUES (?, 'book', ?, '{}', ?, ?, ?)",
            (index, title, json.dumps({"authors": [author]}), NOW, NOW),
        )
        connection.execute(
            "INSERT INTO entries (id, user_id, item_id, status, score, notes, date_added,"
            " reread_count, score_provisional, created_at, updated_at)"
            " VALUES (?, 1, ?, 'read', 8, 'kept', ?, 0, 0, ?, ?)",
            (index, index, NOW, NOW, NOW),
        )
    connection.commit()
    connection.close()


def test_pending_revisions_reports_what_is_outstanding(tmp_path: Path) -> None:
    configured = database_at(tmp_path / "data", PRE_PROJECTION)
    assert configured.database_url is not None

    pending = pending_revisions(configured.database_url)

    assert pending == [
        "0007_normalized_sort_projection",
        "0008_plain_text_descriptions",
        "0009_provider_usage",
        "0010_attachments",
        "0011_creator_sort_names",
    ]

    upgrade(configured.database_url)
    assert pending_revisions(configured.database_url) == []


@pytest.mark.anyio
async def test_existing_library_is_backed_up_before_the_projection_migration(
    tmp_path: Path,
) -> None:
    configured = database_at(tmp_path / "data", PRE_PROJECTION)
    seed_accented_library(configured.data_dir / "books.db")
    app = create_app(configured)

    async with app.router.lifespan_context(app):
        pass

    assert configured.backup_dir is not None
    backups = sorted(configured.backup_dir.glob("pre-migration-*"))
    assert len(backups) == 1
    manifest = verify_backup(backups[0])
    # The copy has to predate the upgrade, or it is not a rollback point.
    assert manifest["alembic_revision"] == PRE_PROJECTION
    assert manifest["counts"]["items"] == 3
    assert manifest["label"] == "pre-migration"
    assert configured.database_url is not None
    assert pending_revisions(configured.database_url) == []


@pytest.mark.anyio
async def test_fresh_install_is_not_slowed_down_by_a_backup_of_nothing(tmp_path: Path) -> None:
    configured = Settings(
        data_dir=tmp_path / "data",
        backup_dir=tmp_path / "backups",
        user_agent_contact="test@example.invalid",
    )
    app = create_app(configured)

    async with app.router.lifespan_context(app):
        pass

    assert configured.backup_dir is not None
    assert list(configured.backup_dir.glob("pre-migration-*")) == []
    assert configured.database_url is not None
    assert pending_revisions(configured.database_url) == []


@pytest.mark.anyio
async def test_an_unwritable_backup_directory_stops_the_upgrade(tmp_path: Path) -> None:
    configured = database_at(tmp_path / "data", PRE_PROJECTION)
    seed_accented_library(configured.data_dir / "books.db")
    blocked = tmp_path / "blocked"
    blocked.write_text("a file where the backup directory should be", encoding="utf-8")
    configured.backup_dir = blocked
    app = create_app(configured)

    with pytest.raises(RuntimeError, match="backup"):
        async with app.router.lifespan_context(app):
            pass

    # Refusing to migrate is the whole point: the pre-0007 rows must still be there.
    assert configured.database_url is not None
    assert pending_revisions(configured.database_url) == [
        "0007_normalized_sort_projection",
        "0008_plain_text_descriptions",
        "0009_provider_usage",
        "0010_attachments",
        "0011_creator_sort_names",
    ]


@pytest.mark.anyio
async def test_a_second_start_with_nothing_pending_takes_no_backup(tmp_path: Path) -> None:
    configured = database_at(tmp_path / "data", PRE_PROJECTION)
    seed_accented_library(configured.data_dir / "books.db")
    app = create_app(configured)
    async with app.router.lifespan_context(app):
        pass

    async with app.router.lifespan_context(app):
        pass

    assert configured.backup_dir is not None
    assert len(list(configured.backup_dir.glob("pre-migration-*"))) == 1


@pytest.mark.anyio
async def test_the_backup_directory_is_not_created_inside_the_data_volume(tmp_path: Path) -> None:
    """DEC-040: a backup kept inside the volume it backs up is lost with it."""
    configured = database_at(tmp_path / "data", PRE_PROJECTION)
    seed_accented_library(configured.data_dir / "books.db")
    app = create_app(configured)

    async with app.router.lifespan_context(app):
        pass

    assert not (configured.data_dir / "backups").exists()


@pytest.mark.anyio
async def test_the_application_serves_after_the_guarded_upgrade(tmp_path: Path) -> None:
    configured = database_at(tmp_path / "data", PRE_PROJECTION)
    seed_accented_library(configured.data_dir / "books.db")
    app = create_app(configured)

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        ready = await client.get("/api/health/ready")

    assert ready.status_code == 200


def test_alembic_config_still_resolves_a_named_revision(tmp_path: Path) -> None:
    configured = database_at(tmp_path / "data", PRE_PROJECTION)
    assert configured.database_url is not None

    assert alembic_config(configured.database_url) is not None
    assert read_manifest(tmp_path) is None


@pytest.mark.anyio
async def test_accented_sorting_and_search_survive_the_projection_backfill(
    tmp_path: Path,
) -> None:
    """AC4 is about behaviour after the backfill, not about the columns existing.

    The rows below were written the way 0006 knew how, with no projection at all.
    If the backfill missed them they sort by raw code point and an unaccented
    query matches nothing.
    """
    configured = database_at(tmp_path / "data", PRE_PROJECTION)
    seed_accented_library(configured.data_dir / "books.db")
    app = create_app(configured)

    async with app.router.lifespan_context(app):
        service = LibraryService(app.state.engine)
        by_title = service.list_entries(sort="title", order="asc")
        unaccented_query = service.list_entries(q="avila")
        author_query = service.list_entries(q="sabato")
        by_author = service.list_entries(sort="sort_author", order="asc")

    # "Ávila" before "Ébano" before "Zurita": accent-folded, not code-point order,
    # which would put every accented capital after "Z".
    assert [row["item"]["title"] for row in by_title["items"]] == ["Ávila", "Ébano", "Zurita"]
    assert [row["item"]["title"] for row in unaccented_query["items"]] == ["Ávila"]
    assert [row["item"]["title"] for row in author_query["items"]] == ["Ébano"]
    assert [row["item"]["sort_author"] for row in by_author["items"]] == [
        "Ángela Ruiz",
        "Ernesto Sábato",
        "Zoé Valdés",
    ]


def test_the_backfill_reaches_rows_written_before_the_projection_existed(tmp_path: Path) -> None:
    configured = database_at(tmp_path / "data", PRE_PROJECTION)
    seed_accented_library(configured.data_dir / "books.db")
    assert configured.database_url is not None

    upgrade(configured.database_url)

    connection = sqlite3.connect(configured.data_dir / "books.db")
    projected = connection.execute(
        "SELECT title, title_normalized, sort_author_normalized FROM items ORDER BY id"
    ).fetchall()
    connection.close()

    assert projected == [
        ("Ávila", "avila", "angela ruiz"),
        ("Zurita", "zurita", "zoe valdes"),
        ("Ébano", "ebano", "ernesto sabato"),
    ]


@pytest.mark.anyio
async def test_a_failing_migration_does_not_write_a_backup_per_restart(tmp_path: Path) -> None:
    """`restart: unless-stopped` turns a failing migration into a loop.

    Sprint 018's upgrade drill produced six identical pre-migration backups in
    eleven seconds. Nightly retention is scoped by label and never prunes these,
    so a loop would fill the disk with copies of the same database.
    """
    configured = database_at(tmp_path / "data", PRE_PROJECTION)
    seed_accented_library(configured.data_dir / "books.db")
    app = create_app(configured)
    assert configured.backup_dir is not None

    for _ in range(3):
        _back_up_before_migrating(configured)

    backups = list(configured.backup_dir.glob("pre-migration-*"))
    assert len(backups) == 1
    # Still the copy taken before the first attempt, which is the useful one.
    assert verify_backup(backups[0])["alembic_revision"] == PRE_PROJECTION
    assert app is not None


PRE_PLAIN_TEXT = "0007_normalized_sort_projection"


def seed_markup_descriptions(database_path: Path) -> None:
    """Descriptions as they are already stored in a library imported before 0008."""
    connection = sqlite3.connect(database_path)
    rows = [
        # The exact shape the Sprint 019 walkthrough saw on the detail page.
        ("Escaping the Build Trap", "<p>To stay competitive, companies <b>must</b> innovate.</p>"),
        ("Cien años de soledad", "<p> <b>Macondo</b> y los Buendía.</p>"),
        # Already prose: must come through byte-identical, not round-tripped.
        ("The Shadow of the Wind", "A boy discovers a book."),
        # Nothing but markup: the key is dropped rather than left as an empty string.
        ("Empty", "<p></p>"),
    ]
    for index, (title, description) in enumerate(rows, start=1):
        connection.execute(
            "INSERT INTO items (id, type, title, identifiers, metadata, created_at, updated_at)"
            " VALUES (?, 'book', ?, '{}', ?, ?, ?)",
            (index, title, json.dumps({"description": description}), NOW, NOW),
        )
    connection.execute(
        "INSERT INTO items (id, type, title, identifiers, metadata, created_at, updated_at)"
        " VALUES (99, 'book', 'No description', '{}', '{}', ?, ?)",
        (NOW, NOW),
    )
    connection.commit()
    connection.close()


def test_stored_descriptions_are_reduced_to_plain_text(tmp_path: Path) -> None:
    """Stripping at the provider boundary does nothing for a library imported earlier."""
    configured = database_at(tmp_path / "data", PRE_PLAIN_TEXT)
    seed_markup_descriptions(configured.data_dir / "books.db")
    assert configured.database_url is not None

    upgrade(configured.database_url)

    connection = sqlite3.connect(configured.data_dir / "books.db")
    stored = connection.execute("SELECT id, metadata FROM items ORDER BY id").fetchall()
    connection.close()
    descriptions = {row[0]: json.loads(row[1]).get("description") for row in stored}

    assert descriptions[1] == "To stay competitive, companies must innovate."
    assert descriptions[2] == "Macondo y los Buendía."
    assert descriptions[3] == "A boy discovers a book."
    # An all-markup description would otherwise read as "present, and blank".
    assert descriptions[4] is None
    assert descriptions[99] is None
