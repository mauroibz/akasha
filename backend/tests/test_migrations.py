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
        "0012_creators",
        "0013_entry_formats",
        "0014_status_is_the_domains",
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
        "0012_creators",
        "0013_entry_formats",
        "0014_status_is_the_domains",
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
        by_author = service.list_entries(sort="creator", order="asc")

    # "Ávila" before "Ébano" before "Zurita": accent-folded, not code-point order,
    # which would put every accented capital after "Z".
    assert [row["item"]["title"] for row in by_title["items"]] == ["Ávila", "Ébano", "Zurita"]
    assert [row["item"]["title"] for row in unaccented_query["items"]] == ["Ávila"]
    assert [row["item"]["title"] for row in author_query["items"]] == ["Ébano"]
    assert [row["item"]["creator"] for row in by_author["items"]] == [
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
        "SELECT title, title_normalized, creator_primary_normalized FROM items ORDER BY id"
    ).fetchall()
    connection.close()

    assert projected == [
        ("Ávila", "avila", "angela ruiz"),
        ("Zurita", "zurita", "zoe valdes"),
        ("Ébano", "ebano", "ernesto sabato"),
    ]


def seed_library_at_creator_sort_names(database_path: Path) -> None:
    """Rows as 0011 left them: `metadata.authors`, one of them hand-corrected."""
    connection = sqlite3.connect(database_path)
    # `creator_sort` is written the way 0011's backfill left it: the override when the
    # owner supplied one, the heuristic's answer otherwise.
    rows = [
        (
            "Cien años de soledad",
            "Gabriel García Márquez",
            "García Márquez, Gabriel José",
            "García Márquez, Gabriel José",
        ),
        ("Ficciones", "Jorge Luis Borges", None, "Luis Borges, Jorge"),
    ]
    for index, (title, author, override, sort_name) in enumerate(rows, start=1):
        connection.execute(
            "INSERT INTO items (id, type, title, identifiers, metadata, created_at, updated_at,"
            " creator_sort_override, creator_sort) VALUES (?, 'book', ?, '{}', ?, ?, ?, ?, ?)",
            (
                index,
                title,
                json.dumps({"authors": [author], "publisher": "Sudamericana"}),
                NOW,
                NOW,
                override,
                sort_name,
            ),
        )
    connection.commit()
    connection.close()


def test_the_creators_rename_carries_the_owner_correction_rather_than_recomputing_it(
    tmp_path: Path,
) -> None:
    """AC9: no row loses its creator sort name across `authors` -> `creators`.

    The override is the only value here that is not derived, and the heuristic that
    would replace it is known to be wrong on exactly the names it exists to fix —
    "Jorge Luis Borges" becomes "Luis Borges, Jorge" (DEC-051). Recomputing it during
    the rename would silently undo a hand correction.
    """
    configured = database_at(tmp_path / "data", "0011_creator_sort_names")
    seed_library_at_creator_sort_names(configured.data_dir / "books.db")
    assert configured.database_url is not None

    upgrade(configured.database_url)

    connection = sqlite3.connect(configured.data_dir / "books.db")
    migrated = connection.execute(
        "SELECT metadata, creator_primary, creator_primary_normalized, creator_sort_override,"
        " creator_sort FROM items ORDER BY id"
    ).fetchall()
    connection.close()

    corrected, heuristic = migrated
    assert json.loads(corrected[0]) == {
        "creators": ["Gabriel García Márquez"],
        "publisher": "Sudamericana",
    }
    assert corrected[1] == "Gabriel García Márquez"
    assert corrected[2] == "gabriel garcia marquez"
    # Carried verbatim, and still the value the library sorts under.
    assert corrected[3] == "García Márquez, Gabriel José"
    assert corrected[4] == "García Márquez, Gabriel José"
    # A row nobody corrected keeps the heuristic's answer, wrong as it is.
    assert json.loads(heuristic[0])["creators"] == ["Jorge Luis Borges"]
    assert heuristic[3] is None
    assert heuristic[4] == "Luis Borges, Jorge"


def test_an_item_with_no_creators_survives_the_rename(tmp_path: Path) -> None:
    """An album can credit nobody, and so can a hand-entered book."""
    configured = database_at(tmp_path / "data", "0011_creator_sort_names")
    connection = sqlite3.connect(configured.data_dir / "books.db")
    connection.execute(
        "INSERT INTO items (id, type, title, identifiers, metadata, created_at, updated_at)"
        " VALUES (1, 'book', 'Anonymous', '{}', '{}', ?, ?)",
        (NOW, NOW),
    )
    connection.commit()
    connection.close()
    assert configured.database_url is not None

    upgrade(configured.database_url)

    connection = sqlite3.connect(configured.data_dir / "books.db")
    row = connection.execute("SELECT metadata, creator_primary, creator_sort FROM items").fetchone()
    connection.close()
    assert row == ("{}", None, None)


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


def test_every_book_status_survives_the_vocabulary_change(tmp_path: Path) -> None:
    """Sprint 026 AC3: no data migration silently remaps a value.

    `entries` is rebuilt by 0013 to widen a CHECK constraint that listed the six book
    statuses, and a rebuild copies every row. This seeds one entry in each of those
    six statuses *before* the change and reads them back after, because "the copy
    preserved the data" is the kind of claim a schema test does not make on its own.
    """
    configured = database_at(tmp_path / "data", "0012_creators")
    assert configured.database_url is not None
    before = ["unsorted", "read", "reading", "to_read", "wishlist", "dropped"]
    connection = sqlite3.connect(configured.data_dir / "books.db")
    for index, status in enumerate(before, start=1):
        connection.execute(
            "INSERT INTO items (id, type, title, identifiers, metadata, created_at, updated_at)"
            " VALUES (?, 'book', ?, '{}', '{}', ?, ?)",
            (index, f"Book {index}", NOW, NOW),
        )
        connection.execute(
            "INSERT INTO entries (id, user_id, item_id, status, suggested_status, score, notes,"
            " date_added, date_started, date_finished, reread_count, score_provisional,"
            " created_at, updated_at)"
            " VALUES (?, 1, ?, ?, ?, 7, 'kept', ?, '2026-01-01', '2026-02-02', 3, 1, ?, ?)",
            (index, index, status, status, NOW, NOW, NOW),
        )
    connection.commit()
    connection.close()

    upgrade(configured.database_url)

    connection = sqlite3.connect(configured.data_dir / "books.db")
    rows = connection.execute(
        "SELECT id, status, suggested_status, score, notes, date_started, date_finished,"
        " reread_count, score_provisional FROM entries ORDER BY id"
    ).fetchall()
    connection.close()
    assert [row[1] for row in rows] == before
    assert [row[2] for row in rows] == before
    # The rest of the row rides along in the same copy, so it is asserted in the same
    # place rather than trusted.
    assert all(row[3:] == (7, "kept", "2026-01-01", "2026-02-02", 3, 1) for row in rows)


def test_the_widened_constraint_admits_an_album_status_and_still_refuses_nonsense(
    tmp_path: Path,
) -> None:
    configured = database_at(tmp_path / "data", "head")
    connection = sqlite3.connect(configured.data_dir / "books.db")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        "INSERT INTO items (id, type, title, identifiers, metadata, created_at, updated_at)"
        " VALUES (1, 'album', 'Discovery', '{}', '{}', ?, ?)",
        (NOW, NOW),
    )
    connection.execute(
        "INSERT INTO entries (id, user_id, item_id, status, date_added, reread_count,"
        " score_provisional, created_at, updated_at)"
        " VALUES (1, 1, 1, 'owned', ?, 0, 0, ?, ?)",
        (NOW, NOW, NOW),
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO entries (id, user_id, item_id, status, date_added, reread_count,"
            " score_provisional, created_at, updated_at)"
            " VALUES (2, 1, 1, 'listened', ?, 0, 0, ?, ?)",
            (NOW, NOW, NOW),
        )
    connection.close()


def test_the_status_check_is_gone_and_the_neutral_ones_are_not(tmp_path: Path) -> None:
    """DEC-067 row 1, and the trap its own migration warns about.

    `copy_from` skips reflection, and SQLAlchemy does not reflect SQLite CHECK
    constraints at all — so a rebuild that dropped one constraint could silently drop
    the other three with it. Score, reread count and provisionality are neutral facts
    about an entry that no domain redefines, and they have to survive.
    """
    configured = database_at(tmp_path / "data", "head")
    database_path = configured.data_dir / "books.db"
    connection = sqlite3.connect(database_path)
    schema = connection.execute("SELECT sql FROM sqlite_master WHERE name='entries'").fetchone()[0]

    assert "ck_entries_status" not in schema
    assert "ck_entries_suggested_status" not in schema
    for surviving in (
        "ck_entries_score",
        "ck_entries_reread_count",
        "ck_entries_score_provisional",
    ):
        assert surviving in schema

    connection.execute(
        "INSERT INTO items (id, type, title, identifiers, metadata, created_at, updated_at)"
        " VALUES (1, 'game', 'Outer Wilds', '{}', '{}', ?, ?)",
        (NOW, NOW),
    )
    # A status no registered domain declares is now the database's business no longer:
    # `validate_status` is keyed on the item's own domain and is strictly stronger.
    connection.execute(
        "INSERT INTO entries (id, user_id, item_id, status, date_added, reread_count,"
        " score_provisional, created_at, updated_at)"
        " VALUES (1, 1, 1, 'playing', ?, 0, 0, ?, ?)",
        (NOW, NOW, NOW),
    )
    # A score out of range is still refused, which is the half that must not have moved.
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("UPDATE entries SET score = 11 WHERE id = 1")
    connection.close()


def test_the_status_check_comes_back_on_a_downgrade(tmp_path: Path) -> None:
    """Down restores the snapshot, which is the honest inverse rather than a no-op."""
    from alembic import command

    configured = database_at(tmp_path / "data", "head")
    assert configured.database_url is not None
    command.downgrade(alembic_config(configured.database_url), "0013_entry_formats")

    connection = sqlite3.connect(configured.data_dir / "books.db")
    schema = connection.execute("SELECT sql FROM sqlite_master WHERE name='entries'").fetchone()[0]
    connection.close()

    assert "ck_entries_status" in schema
    assert "'owned'" in schema
