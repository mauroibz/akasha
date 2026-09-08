"""Migration 0007 rewrites every item row, so upgrading is a data operation.

These tests cover the guard around it: an existing library is copied before the
schema moves, a fresh install is not slowed down by a backup of nothing, and a
backup that cannot be written stops the upgrade rather than proceeding blind.
"""

import json
import re
import sqlite3
from pathlib import Path

import httpx
import pytest
from alembic.script import ScriptDirectory

from book_tracker.application.library import LibraryService
from book_tracker.backup import read_manifest, restore_backup, verify_backup
from book_tracker.config import Settings
from book_tracker.main import _back_up_before_migrating, create_app
from book_tracker.migrations import (
    alembic_config,
    pending_revisions,
    revision_chain_from_files,
    upgrade,
)

PRE_PROJECTION = "0006_job_error_code"
NOW = "2026-08-13T00:00:00+00:00"

# `jobs.state` is a schema-owned finite-state machine: its CHECK is the transition
# invariant, not an extensible registry vocabulary. Every other string-valued `IN`
# constraint needs an explicit architectural decision before it may enter the schema.
SCHEMA_OWNED_STATE_CHECKS = frozenset({("jobs", "ck_jobs_state")})
STRING_ENUM_CHECK = re.compile(
    r"(?:CONSTRAINT\s+(?P<name>[A-Za-z0-9_]+)\s+)?"
    r"CHECK\s*\((?P<body>[^)]*\bIN\s*\([^)]*'[^)]*)\)",
    re.IGNORECASE,
)


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


def revisions_above(revision: str) -> list[str]:
    """Every shipped revision after ``revision``, oldest first.

    Derived from Alembic's own version files (DEC-148), so moving head touches no
    pinned list here: the fixture revision stays pinned, the production chain is
    whatever the files declare, exactly as Alembic itself reads it.
    """
    chain = revision_chain_from_files()
    if revision not in chain:
        raise AssertionError(f"pinned fixture revision {revision!r} is no longer shipped")
    return chain[chain.index(revision) + 1 :]


def assert_no_frozen_application_vocabulary(connection: sqlite3.Connection) -> None:
    """Read head schema DDL and reject a new code-owned string enumeration."""
    frozen: list[str] = []
    rows = connection.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND sql IS NOT NULL"
    )
    for table, sql in rows:
        for match in STRING_ENUM_CHECK.finditer(sql):
            name = match.group("name") or "<unnamed>"
            if (table, name) not in SCHEMA_OWNED_STATE_CHECKS:
                frozen.append(f"{table}.{name}: {match.group('body')}")
    assert not frozen, "schema freezes an application vocabulary: " + "; ".join(frozen)


def test_head_schema_does_not_freeze_an_application_vocabulary(tmp_path: Path) -> None:
    configured = database_at(tmp_path / "data", "head")
    connection = sqlite3.connect(configured.data_dir / "books.db")

    assert_no_frozen_application_vocabulary(connection)

    # Prove the guard bites on the exact class of constraint Sprints 028 and 041
    # removed. This table exists only inside this test and is never a migration.
    connection.execute(
        "CREATE TABLE frozen_vocabulary_probe (value TEXT CHECK(value IN ('first', 'second')))"
    )
    with pytest.raises(AssertionError, match="frozen_vocabulary_probe"):
        assert_no_frozen_application_vocabulary(connection)
    connection.close()


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

    expected = revisions_above(PRE_PROJECTION)
    assert len(expected) > 0, "the pinned fixture revision must still be below head"

    assert pending_revisions(configured.database_url) == expected

    upgrade(configured.database_url)
    assert pending_revisions(configured.database_url) == []


def test_the_revision_chain_read_from_files_is_alembics_own_graph(tmp_path: Path) -> None:
    """DEC-148: the file-derived chain must be exactly the graph Alembic itself reads.

    Asserts equality against the running migration engine rather than a frozen copy, so
    the two cannot drift again the moment a new revision lands.
    """
    fake_url = f"sqlite:///{tmp_path / 'books.db'}"
    script = ScriptDirectory.from_config(alembic_config(fake_url))
    head = script.get_current_head()
    alembic_chain = [rev.revision for rev in script.iterate_revisions(head, None)][::-1]

    assert revision_chain_from_files() == alembic_chain


def test_revision_numbers_are_unique_and_in_order() -> None:
    """The shipped chain is exactly the numeric line 0001..NNNN of its version files."""
    numbers = [int(revision.split("_", 1)[0]) for revision in revision_chain_from_files()]

    assert numbers == list(range(1, len(numbers) + 1)), (
        "migration numbers must be the gapless line 0001 onward "
        f"(found {numbers[0]:04d}..{numbers[-1]:04d}, {len(numbers)} revisions)"
    )


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

    # Refusing to migrate is the whole point: the pre-0007 rows must still be there,
    # and everything the files say must still be outstanding.
    assert configured.database_url is not None
    expected = revisions_above(PRE_PROJECTION)
    assert len(expected) > 0, "the pinned fixture revision must still be below head"
    assert pending_revisions(configured.database_url) == expected


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


def test_progress_is_added_without_disturbing_an_existing_row(tmp_path: Path) -> None:
    """Migration 0015 rebuilds `entries`, so what it must not lose is everything else.

    A rebuild is the only way to add a CHECK on SQLite, and `copy_from` skips
    reflection — SQLAlchemy does not reflect SQLite CHECK constraints at all, so a
    mis-spelled table silently drops them. This walks a populated row through the
    upgrade and back down again.
    """
    from alembic import command

    configured = database_at(tmp_path / "data", "0014_status_is_the_domains")
    database_path = configured.data_dir / "books.db"
    connection = sqlite3.connect(database_path)
    connection.execute(
        "INSERT INTO items (id, type, title, identifiers, metadata, created_at, updated_at)"
        " VALUES (1, 'anime', 'Black Clover', '{}', '{}', ?, ?)",
        (NOW, NOW),
    )
    connection.execute(
        "INSERT INTO entries (id, user_id, item_id, status, score, notes, date_added,"
        " date_started, date_finished, reread_count, score_provisional, created_at, updated_at)"
        " VALUES (1, 1, 1, 'dropped', 4, 'kept', '2026-01-01', '2026-01-02', '2026-02-02',"
        " 3, 1, ?, ?)",
        (NOW, NOW),
    )
    # Children of `entries`, because a rebuild is a DROP TABLE and SQLite fires
    # `ON DELETE CASCADE` on one when `PRAGMA foreign_keys` is on. `alembic/env.py`
    # deliberately never enables it, and nothing asserted that until now: the failure
    # empties both of these tables, reports success, and no backup manifest counts them.
    connection.execute(
        "INSERT INTO shelves (id, user_id, name, slug, created_at, updated_at)"
        " VALUES (1, 1, 'Shelf', 'shelf', ?, ?)",
        (NOW, NOW),
    )
    connection.execute("INSERT INTO entry_shelves (entry_id, shelf_id) VALUES (1, 1)")
    connection.execute("INSERT INTO entry_formats (entry_id, format) VALUES (1, 'streaming')")
    connection.commit()
    connection.close()

    command.upgrade(alembic_config(configured.database_url), "0015_entry_progress")

    connection = sqlite3.connect(database_path)
    row = connection.execute(
        "SELECT status, score, notes, date_started, date_finished, reread_count,"
        " score_provisional, progress FROM entries WHERE id = 1"
    ).fetchone()
    # Everything survives, and the new column is NULL rather than 0: an existing entry
    # has not recorded a progress, which is a different fact from having recorded zero.
    assert row == ("dropped", 4, "kept", "2026-01-02", "2026-02-02", 3, 1, None)

    assert connection.execute("SELECT count(*) FROM entry_shelves").fetchone()[0] == 1
    assert connection.execute("SELECT count(*) FROM entry_formats").fetchone()[0] == 1

    schema = connection.execute("SELECT sql FROM sqlite_master WHERE name='entries'").fetchone()[0]
    for surviving in (
        "ck_entries_score",
        "ck_entries_reread_count",
        "ck_entries_score_provisional",
        "ck_entries_progress",
    ):
        assert surviving in schema, f"the rebuild dropped {surviving}"
    # `copy_from` is a declaration and not a check, so an index left out of it is
    # dropped in silence. `ix_entries_user_finished_id` serves `sort=date_finished`:
    # losing it makes a page slower and says nothing.
    indexes = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='entries'"
        )
    }
    assert indexes >= {
        "ix_entries_status",
        "ix_entries_score",
        "ix_entries_date_added",
        "ix_entries_user_status_date_id",
        "ix_entries_user_status_score_id",
        "ix_entries_user_finished_id",
    }

    # Zero is storable and negatives are not: the one bound the database keeps.
    connection.execute("UPDATE entries SET progress = 0 WHERE id = 1")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("UPDATE entries SET progress = -1 WHERE id = 1")
    # There is deliberately no upper bound: the total is display only and a cached one
    # goes stale, so a count above it must still be storable (DEC-077, this sprint).
    connection.execute("UPDATE entries SET progress = 100000 WHERE id = 1")
    connection.commit()
    connection.close()

    command.downgrade(alembic_config(configured.database_url), "0014_status_is_the_domains")
    connection = sqlite3.connect(database_path)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(entries)")}
    assert "progress" not in columns
    assert connection.execute("SELECT status, score FROM entries WHERE id = 1").fetchone() == (
        "dropped",
        4,
    )
    connection.close()


def test_the_connector_name_is_the_registrys_and_its_batches_keep_their_records(
    tmp_path: Path,
) -> None:
    """`ck_import_batches_kind` was `ck_entries_status`'s mistake one table over.

    It listed `goodreads` and `calibre` and was frozen in migration `0002`, so the first
    connector added since — Sprint 041's — passed every application check and was then
    refused by SQLite. `IMPORTERS` is the authority and is strictly stronger: the route
    404s a name it does not hold, which the constraint could never express.

    The rebuild is also a `DROP TABLE`, and `import_records` cascades from this table.
    """
    from alembic import command

    configured = database_at(tmp_path / "data", "0015_entry_progress")
    database_path = configured.data_dir / "books.db"
    connection = sqlite3.connect(database_path)
    connection.execute(
        "INSERT INTO import_batches (id, kind, fingerprint, state, created_at, updated_at)"
        " VALUES ('b1', 'goodreads', 'abc', 'committed', ?, ?)",
        (NOW, NOW),
    )
    connection.execute(
        "INSERT INTO import_records (id, batch_id, row_number, created_at, updated_at)"
        " VALUES (1, 'b1', 2, ?, ?)",
        (NOW, NOW),
    )
    connection.commit()
    # Before: a connector this list never heard of is refused by the database.
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO import_batches (id, kind, fingerprint, state, created_at, updated_at)"
            " VALUES ('b2', 'myanimelist', 'def', 'previewed', ?, ?)",
            (NOW, NOW),
        )
    connection.close()

    command.upgrade(alembic_config(configured.database_url), "0016_import_kind_is_the_registrys")

    connection = sqlite3.connect(database_path)
    schema = connection.execute(
        "SELECT sql FROM sqlite_master WHERE name='import_batches'"
    ).fetchone()[0]
    assert "ck_import_batches_kind" not in schema
    # The replay key is a real invariant and stays.
    assert "uq_import_batch_input" in schema
    # The batch and its record both survived the rebuild.
    assert connection.execute("SELECT count(*) FROM import_batches").fetchone()[0] == 1
    assert connection.execute("SELECT count(*) FROM import_records").fetchone()[0] == 1
    # And a third connector's batch is now the registry's business, not the schema's.
    connection.execute(
        "INSERT INTO import_batches (id, kind, fingerprint, state, created_at, updated_at)"
        " VALUES ('b2', 'myanimelist', 'def', 'previewed', ?, ?)",
        (NOW, NOW),
    )
    # The replay key still refuses the same source twice for one connector.
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO import_batches (id, kind, fingerprint, state, created_at, updated_at)"
            " VALUES ('b3', 'myanimelist', 'def', 'previewed', ?, ?)",
            (NOW, NOW),
        )
    connection.commit()
    connection.close()


IDENTITY_SEED_REVISION = "0016_import_kind_is_the_registrys"


def seed_identity_library(database_path: Path) -> None:
    """A `0016` library holding every kind of row Sprint 075's migrations walk.

    One entry written with an explicit ``user_id`` and one relying on the column's
    ``server_default``: both already mean user 1, and the migrations must keep saying
    so. A shelf with an entry on it and a format on that entry covers the two rebuild
    children; a committed batch with one record and one effect covers the import
    ledger; two job rows split the queue the way the schema is about to need it split
    — one enrichment job chained to the batch, one with no batch at all.
    """
    connection = sqlite3.connect(database_path)
    connection.execute(
        "INSERT INTO items (id, type, title, identifiers, metadata, created_at, updated_at)"
        " VALUES (1, 'book', 'Rayuela', '{}', '{}', ?, ?)",
        (NOW, NOW),
    )
    connection.execute(
        "INSERT INTO items (id, type, title, identifiers, metadata, created_at, updated_at)"
        " VALUES (2, 'album', 'Kind of Blue', '{}', '{}', ?, ?)",
        (NOW, NOW),
    )
    connection.execute(
        "INSERT INTO entries (id, user_id, item_id, status, score, notes, date_added,"
        " reread_count, score_provisional, created_at, updated_at)"
        " VALUES (1, 1, 1, 'read', 9, 'hopscotch', ?, 0, 0, ?, ?)",
        (NOW, NOW, NOW),
    )
    connection.execute(
        "INSERT INTO entries (id, item_id, status, date_added, reread_count,"
        " score_provisional, created_at, updated_at)"
        " VALUES (2, 2, 'owned', ?, 0, 0, ?, ?)",
        (NOW, NOW, NOW),
    )
    connection.execute(
        "INSERT INTO shelves (id, user_id, name, slug, created_at, updated_at)"
        " VALUES (1, 1, 'Argentina', 'argentina', ?, ?)",
        (NOW, NOW),
    )
    connection.execute("INSERT INTO entry_shelves (entry_id, shelf_id) VALUES (1, 1)")
    connection.execute("INSERT INTO entry_formats (entry_id, format) VALUES (1, 'paperback')")
    connection.execute(
        "INSERT INTO import_batches (id, kind, fingerprint, state, committed_at,"
        " created_at, updated_at)"
        " VALUES ('batch-1', 'goodreads', 'fp-1', 'committed', ?, ?, ?)",
        (NOW, NOW, NOW),
    )
    connection.execute(
        "INSERT INTO import_records (id, batch_id, row_number, created_at, updated_at)"
        " VALUES (1, 'batch-1', 1, ?, ?)",
        (NOW, NOW),
    )
    connection.execute(
        "INSERT INTO import_effects (effect_id, batch_id, record_id, effect_type,"
        " entity_type, entity_id)"
        " VALUES (1, 'batch-1', 1, 'insert', 'entry', '1')"
    )
    connection.execute(
        "INSERT INTO jobs (id, batch_id, kind, state, payload, available_at,"
        " created_at, updated_at)"
        " VALUES ('job-batched', 'batch-1', 'enrich_item', 'queued', '{}', ?, ?, ?)",
        (NOW, NOW, NOW),
    )
    connection.execute(
        "INSERT INTO jobs (id, batch_id, kind, state, payload, available_at,"
        " created_at, updated_at)"
        " VALUES ('job-shared', NULL, 'enrich_item', 'queued', '{}', ?, ?, ?)",
        (NOW, NOW, NOW),
    )
    connection.commit()
    connection.close()


def test_users_and_sessions_are_created_from_the_previous_head(tmp_path: Path) -> None:
    """Sprint 075 AC1/AC3/AC5 for the identity revision.

    The upgrade is a data operation here — the seeded first user arrives — so the test
    seeds every table the sprint walks and proves each one comes through untouched
    while ``users`` and ``sessions`` appear with the shapes the proposal's §2.2 fixes.
    """
    from alembic import command

    configured = database_at(tmp_path / "data", IDENTITY_SEED_REVISION)
    database_path = configured.data_dir / "books.db"
    seed_identity_library(database_path)
    assert configured.database_url is not None

    command.upgrade(alembic_config(configured.database_url), "0017_users_and_sessions")

    connection = sqlite3.connect(database_path)
    assert (
        connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        == "0017_users_and_sessions"
    )

    # The seeded first user: exactly one row, admin, no credentials (AC5).
    rows = connection.execute(
        "SELECT id, username, display_name, password_hash, password_salt, is_admin FROM users"
    ).fetchall()
    assert len(rows) == 1
    user_id, username, display_name, password_hash, password_salt, is_admin = rows[0]
    assert (user_id, is_admin, password_hash, password_salt) == (1, 1, None, None)
    # Stored normalized: the column's value is its own stripped-casefold form.
    assert username == username.strip().casefold()
    # The seed's name is `admin` (the owner directed it on close day, taking the
    # cheap re-migration DEC-147 offered: Sprint 077's setup screen still chooses
    # the real credentials).
    assert username == "admin"

    # `users` shape (proposal §2.2). `display_name` is optional and typed — the
    # normalized `username` is the identity. Credentials are nullable on purpose:
    # the seeded user gets its password from the Sprint 077 setup screen.
    user_columns = {
        row[1]: (row[2].upper(), row[3], row[5])
        for row in connection.execute("PRAGMA table_info(users)")
    }
    assert user_columns == {
        "id": ("INTEGER", 1, 1),
        "username": ("TEXT", 1, 0),
        "display_name": ("TEXT", 0, 0),
        "password_hash": ("TEXT", 0, 0),
        "password_salt": ("TEXT", 0, 0),
        "is_admin": ("INTEGER", 1, 0),
        "created_at": ("TEXT", 1, 0),
        "updated_at": ("TEXT", 1, 0),
    }
    # It is the table everything points at; it points at nothing itself.
    assert connection.execute("PRAGMA foreign_key_list(users)").fetchall() == []
    # `PRAGMA index_list` shows a UNIQUE constraint declared in the table body as an
    # unnamed autoindex, so the named constraint is asserted where it actually lives:
    # the table's own DDL (the same channel the 0016 tests below use).
    users_ddl = connection.execute("SELECT sql FROM sqlite_master WHERE name='users'").fetchone()[0]
    assert "CONSTRAINT uq_users_username UNIQUE (username)" in users_ddl

    # `sessions` shape: server-side and therefore revocable. The token exists only as
    # its hash — unique — with the expiry sweep's (user_id, expires_at) index beside it.
    session_columns = {
        row[1]: (row[2].upper(), row[3])
        for row in connection.execute("PRAGMA table_info(sessions)")
    }
    assert session_columns == {
        "id": ("TEXT", 1),
        "user_id": ("INTEGER", 1),
        "token_hash": ("TEXT", 1),
        "created_at": ("TEXT", 1),
        "last_seen_at": ("TEXT", 1),
        "expires_at": ("TEXT", 1),
        "user_agent": ("TEXT", 0),
    }
    session_fks = {
        (row[2], row[3], row[6]) for row in connection.execute("PRAGMA foreign_key_list(sessions)")
    }
    assert session_fks == {("users", "user_id", "CASCADE")}
    sessions_ddl = connection.execute(
        "SELECT sql FROM sqlite_master WHERE name='sessions'"
    ).fetchone()[0]
    assert "CONSTRAINT uq_sessions_token_hash UNIQUE (token_hash)" in sessions_ddl
    sessions_indexes = {
        row[1]: bool(row[2]) for row in connection.execute("PRAGMA index_list(sessions)")
    }
    assert sessions_indexes.get("ix_sessions_user_expires") is False

    # AC1: nothing the library already had may move. Rows and values exactly as 0016
    # left them — including the tables the next revision will rebuild.
    entries = {
        row[0]: row[1:]
        for row in connection.execute(
            "SELECT id, user_id, item_id, status, score, notes FROM entries"
        )
    }
    # The second entry was written with no user_id: its column default already meant 1.
    assert entries == {1: (1, 1, "read", 9, "hopscotch"), 2: (1, 2, "owned", None, None)}
    assert connection.execute("SELECT name FROM shelves").fetchall() == [("Argentina",)]
    assert connection.execute("SELECT entry_id, shelf_id FROM entry_shelves").fetchall() == [(1, 1)]
    assert connection.execute("SELECT entry_id, format FROM entry_formats").fetchall() == [
        (1, "paperback")
    ]
    assert connection.execute("SELECT id, kind, state FROM import_batches").fetchall() == [
        ("batch-1", "goodreads", "committed")
    ]
    assert connection.execute("SELECT batch_id, row_number FROM import_records").fetchall() == [
        ("batch-1", 1)
    ]
    assert connection.execute("SELECT effect_type, entity_id FROM import_effects").fetchall() == [
        ("insert", "1")
    ]
    assert {row[0]: row[1] for row in connection.execute("SELECT id, batch_id FROM jobs")} == {
        "job-batched": "batch-1",
        "job-shared": None,
    }

    # Nobody's work is owned yet: user attribution lands one revision at a time.
    for table in ("import_batches", "import_records", "import_effects", "jobs"):
        assert "user_id" not in {
            row[1] for row in connection.execute(f"PRAGMA table_info({table})")
        }
    # AC3: the whole schema passes its own referential audit.
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    connection.close()


def test_users_refuses_a_second_user_with_the_same_username(tmp_path: Path) -> None:
    """`uq_users_username` bites: one identity per stored normalized form."""
    configured = database_at(tmp_path / "data", "0017_users_and_sessions")
    connection = sqlite3.connect(configured.data_dir / "books.db")
    connection.execute(
        "INSERT INTO users (id, username, is_admin, created_at, updated_at)"
        " VALUES (2, 'second', 0, ?, ?)",
        (NOW, NOW),
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO users (id, username, is_admin, created_at, updated_at)"
            " VALUES (3, 'second', 0, ?, ?)",
            (NOW, NOW),
        )
    connection.close()


def test_sessions_cascade_when_their_user_is_deleted(tmp_path: Path) -> None:
    """ON DELETE CASCADE: revoking a user revokes its sessions.

    No route deletes a user in Sprint 075 — Sprint 079 owns that product decision — but
    the constraint has to state what deletion would do, and for a credential table the
    answer is 'never orphan a session' rather than 'refuse'.
    """
    configured = database_at(tmp_path / "data", "0017_users_and_sessions")
    database_path = configured.data_dir / "books.db"
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        "INSERT INTO sessions (id, user_id, token_hash, created_at, last_seen_at,"
        " expires_at, user_agent)"
        " VALUES ('s1', 1, 'hash-1', ?, ?, ?, NULL)",
        (NOW, NOW, NOW),
    )
    connection.commit()
    assert connection.execute("SELECT count(*) FROM sessions").fetchone()[0] == 1

    connection.execute("DELETE FROM users WHERE id = 1")
    connection.commit()

    assert connection.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
    connection.close()


def test_the_identity_revision_downgrades_back_to_the_previous_head(tmp_path: Path) -> None:
    """Down from `0017` removes both tables and leaves the 0016 library untouched."""
    from alembic import command

    configured = database_at(tmp_path / "data", IDENTITY_SEED_REVISION)
    database_path = configured.data_dir / "books.db"
    seed_identity_library(database_path)
    assert configured.database_url is not None
    command.upgrade(alembic_config(configured.database_url), "0017_users_and_sessions")

    command.downgrade(alembic_config(configured.database_url), IDENTITY_SEED_REVISION)

    connection = sqlite3.connect(database_path)
    tables = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "users" not in tables and "sessions" not in tables
    assert (
        connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        == IDENTITY_SEED_REVISION
    )
    # The library was never this revision's to lose.
    assert connection.execute("SELECT count(*) FROM entries").fetchone()[0] == 2
    assert connection.execute("SELECT count(*) FROM jobs").fetchone()[0] == 2
    connection.close()


FK_REVISION = "0018_user_foreign_keys"


def test_every_user_owned_row_now_points_at_a_real_user(tmp_path: Path) -> None:
    """Sprint 075 AC1/AC3/AC4, exercised the way 0013/0015 did their rebuilds.

    A populated `0016` library walks up two new revisions; every row that said
    `user_id = 1` by convention now says it by foreign key, and every constraint
    the previous head had survives the rebuild of `entries` — byte for byte in
    name and columns, asserted against `sqlite_master` (AC4).
    """
    from alembic import command

    configured = database_at(tmp_path / "data", IDENTITY_SEED_REVISION)
    database_path = configured.data_dir / "books.db"
    seed_identity_library(database_path)
    assert configured.database_url is not None

    command.upgrade(alembic_config(configured.database_url), FK_REVISION)

    connection = sqlite3.connect(database_path)
    assert (
        connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == FK_REVISION
    )

    # AC4: the entries rebuild drops nothing and renames nothing. All five CHECKs,
    # both timestamp-carrying columns, six indexes and the user-scoped unique —
    # exactly the list the sprint's baseline names.
    entries_ddl = connection.execute(
        "SELECT sql FROM sqlite_master WHERE name='entries'"
    ).fetchone()[0]
    for surviving in (
        "uq_entries_user_item",
        "ck_entries_score",
        "ck_entries_reread_count",
        "ck_entries_score_provisional",
        "ck_entries_progress",
    ):
        assert surviving in entries_ddl, f"the rebuild dropped {surviving}"
    # The foreign key the revision exists to add...
    entries_fks = {
        (row[2], row[3], row[6]) for row in connection.execute("PRAGMA foreign_key_list(entries)")
    }
    assert entries_fks == {("items", "item_id", "RESTRICT"), ("users", "user_id", "RESTRICT")}
    # AC4 in names and columns: every entry index back from the rebuild with its
    # exact column list. Names alone would pass a rebuild that silently reordered
    # or dropped an indexed column, which is the failure mode AC4 exists to catch.
    entry_index_columns = {
        name: tuple(info_row[2] for info_row in connection.execute(f"PRAGMA index_info('{name}')"))
        for name in (
            "ix_entries_status",
            "ix_entries_score",
            "ix_entries_date_added",
            "ix_entries_user_status_date_id",
            "ix_entries_user_status_score_id",
            "ix_entries_user_finished_id",
        )
    }
    assert entry_index_columns == {
        "ix_entries_status": ("user_id", "status"),
        "ix_entries_score": ("user_id", "score"),
        "ix_entries_date_added": ("user_id", "date_added"),
        "ix_entries_user_status_date_id": ("user_id", "status", "date_added", "id"),
        "ix_entries_user_status_score_id": ("user_id", "status", "score", "id"),
        "ix_entries_user_finished_id": ("user_id", "date_finished", "id"),
    }
    # ...and a column order built to prove nothing moved: `progress` stays last.
    assert [row[1] for row in connection.execute("PRAGMA table_info(entries)")] == [
        "id",
        "user_id",
        "item_id",
        "status",
        "score",
        "notes",
        "date_added",
        "date_started",
        "date_finished",
        "reread_count",
        "score_provisional",
        "suggested_status",
        "created_at",
        "updated_at",
        "progress",
    ]

    shelves_ddl = connection.execute(
        "SELECT sql FROM sqlite_master WHERE name='shelves'"
    ).fetchone()[0]
    assert "uq_shelves_user_slug" in shelves_ddl
    shelves_fks = {
        (row[2], row[3], row[6]) for row in connection.execute("PRAGMA foreign_key_list(shelves)")
    }
    assert shelves_fks == {("users", "user_id", "RESTRICT")}

    # AC1 continued: every row came through both rebuilds with its values intact,
    # and the rebuild children — entry_shelves and entry_formats — survived a DROP
    # TABLE that would have emptied them under PRAGMA foreign_keys.
    rows = connection.execute(
        "SELECT id, user_id, item_id, status, score, notes FROM entries ORDER BY id"
    ).fetchall()
    assert rows == [
        (1, 1, 1, "read", 9, "hopscotch"),
        (2, 1, 2, "owned", None, None),
    ]
    assert connection.execute("SELECT id, user_id, name, slug FROM shelves").fetchall() == [
        (1, 1, "Argentina", "argentina")
    ]
    assert connection.execute("SELECT entry_id, shelf_id FROM entry_shelves").fetchall() == [(1, 1)]
    assert connection.execute("SELECT entry_id, format FROM entry_formats").fetchall() == [
        (1, "paperback")
    ]

    # AC3: the referential audit keeps returning empty on the upgraded schema.
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

    # And the new constraint bites through the connection the application uses
    # (database.py enables the pragma): a row claiming a user nobody is refused.
    import sqlalchemy as _sa

    engine = _sa.create_engine(f"sqlite:///{database_path}")
    with engine.connect() as verification:
        verification.execute(_sa.text("PRAGMA foreign_keys=ON"))
        with pytest.raises(_sa.exc.IntegrityError):
            verification.execute(
                _sa.text(
                    "INSERT INTO entries (id, user_id, item_id, status, date_added,"
                    " reread_count, score_provisional, created_at, updated_at)"
                    " VALUES (3, 42, 1, 'read', 'now', 0, 0, 'now', 'now')"
                )
            )
    engine.dispose()
    connection.close()


def test_the_foreign_key_revision_downgrades_without_the_keys(tmp_path: Path) -> None:
    """Down from 0018 returns both tables to their FK-less 0016 shapes."""
    from alembic import command

    configured = database_at(tmp_path / "data", IDENTITY_SEED_REVISION)
    database_path = configured.data_dir / "books.db"
    seed_identity_library(database_path)
    assert configured.database_url is not None
    command.upgrade(alembic_config(configured.database_url), FK_REVISION)

    # 0017's tables are a no-op for this downgrade: it rebuilds from their left.
    command.downgrade(alembic_config(configured.database_url), "0017_users_and_sessions")

    connection = sqlite3.connect(database_path)
    assert (
        connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        == "0017_users_and_sessions"
    )
    for table in ("entries", "shelves"):
        fk_targets = {row[2] for row in connection.execute(f"PRAGMA foreign_key_list({table})")}
        assert "users" not in fk_targets
    # Data survived the rebuild down just as it survived up.
    assert connection.execute("SELECT count(*) FROM entries").fetchone()[0] == 2
    assert connection.execute("SELECT count(*) FROM entry_formats").fetchone()[0] == 1
    connection.close()


LEDGER_REVISION = "0019_ownership_on_the_import_ledger"


def test_the_import_ledger_and_job_queue_belong_to_the_seeded_user(tmp_path: Path) -> None:
    """Sprint 075 AC1/AC4/AC6: `0016` -> head with all six tables populated.

    The three import-ledger tables gain a NOT NULL user defaulted and backfilled to
    1 — an import and its undo ledger are someone's work, and everyone here is the
    seeded user. `jobs` is the deliberate asymmetry (sprint risks section, proposal
    §1 line 54): an enrichment job acts on a shared item and belongs to nobody, so
    the column is nullable with no default, and the migration tells the two apart
    the only way a `0016` row can be told — by `batch_id`. A job the import pipeline
    chained to a batch is user 1's; a standalone enrichment job stays nobody's.
    """
    from alembic import command

    configured = database_at(tmp_path / "data", IDENTITY_SEED_REVISION)
    database_path = configured.data_dir / "books.db"
    seed_identity_library(database_path)
    assert configured.database_url is not None

    command.upgrade(alembic_config(configured.database_url), LEDGER_REVISION)

    connection = sqlite3.connect(database_path)
    assert (
        connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        == LEDGER_REVISION
    )

    # AC1: the ledger's user_id is 1 on every row, taken by reference now.
    assert connection.execute("SELECT DISTINCT user_id FROM import_batches").fetchall() == [(1,)]
    assert connection.execute("SELECT DISTINCT user_id FROM import_records").fetchall() == [(1,)]
    assert connection.execute("SELECT DISTINCT user_id FROM import_effects").fetchall() == [(1,)]

    # AC6: the queue splits by import origin. The batch-chained enrichment is user
    # 1's work; the standalone enrichment belongs to nobody.
    assert {row[0]: row[1] for row in connection.execute("SELECT id, user_id FROM jobs")} == {
        "job-batched": 1,
        "job-shared": None,
    }

    # AC4 for the ledger: every constraint and index from the baseline's list
    # survives the upgrade, asserted from sqlite_master. The uq_*/ck_* constraints
    # live in the table body; ix_* are separate objects and are asserted via the
    # index query below, once each.
    for table, surviving in (
        ("import_batches", ("uq_import_batch_input",)),
        ("import_records", ("uq_import_record_row",)),
        ("jobs", ("ck_jobs_state", "ck_jobs_attempts")),
    ):
        ddl = connection.execute(f"SELECT sql FROM sqlite_master WHERE name='{table}'").fetchone()[
            0
        ]
        for name in surviving:
            assert name in ddl, f"{table} lost {name}"
    # …and the three independent indexes survive with their exact column lists.
    ledger_index_columns = {
        name: tuple(info_row[2] for info_row in connection.execute(f"PRAGMA index_info('{name}')"))
        for name in (
            "ix_import_records_batch_action",
            "ix_import_effects_batch_effect",
            "ix_jobs_claim",
        )
    }
    assert ledger_index_columns == {
        "ix_import_records_batch_action": ("batch_id", "planned_action", "row_number"),
        "ix_import_effects_batch_effect": ("batch_id", "effect_id"),
        "ix_jobs_claim": ("state", "available_at"),
    }

    # ...and the new reference (AC3's audit + a runtime enforcement check).
    for table in ("import_batches", "import_records", "import_effects", "jobs"):
        fks = {
            (row[2], row[3], row[6])
            for row in connection.execute(f"PRAGMA foreign_key_list({table})")
        }
        assert ("users", "user_id", "RESTRICT") in fks
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

    # The application's connection (database.py enables the pragma) refuses a batch
    # claimed by a user nobody is. The default still writes user 1 — AC8 depends on
    # INSERTs that name no user still landing.
    import sqlalchemy as _sa

    engine = _sa.create_engine(f"sqlite:///{database_path}")
    with engine.connect() as verification:
        verification.execute(_sa.text("PRAGMA foreign_keys=ON"))
        with pytest.raises(_sa.exc.IntegrityError):
            verification.execute(
                _sa.text(
                    "INSERT INTO import_batches (id, kind, fingerprint, state, user_id,"
                    " created_at, updated_at)"
                    " VALUES ('b-42', 'calibre', 'fp-42', 'previewed', 42, 'now', 'now')"
                )
            )
        # A batch naming nobody falls to the column's default: user 1.
        verification.execute(
            _sa.text(
                "INSERT INTO import_batches (id, kind, fingerprint, state, created_at,"
                " updated_at) VALUES ('b-default', 'calibre', 'fp-d', 'previewed', 'now',"
                " 'now')"
            )
        )
        assert (
            verification.execute(
                _sa.text("SELECT user_id FROM import_batches WHERE id = 'b-default'")
            ).scalar_one()
            == 1
        )
    engine.dispose()
    connection.close()


def test_a_job_written_by_enrichment_claims_no_user(tmp_path: Path) -> None:
    """AC6 at runtime: JobRepository.enqueue produces a shared, userless job.

    The queue's only writer today is enrichment. Its jobs act on shared items, so
    the schema must record them as nobody's — a NULL user_id is the claim the
    Sprint 076 resolver fills in, and a batch-chained job claiming an owner is the
    opposite kind of row, told apart by batch_id at migration time.
    """
    configured = database_at(tmp_path / "data", IDENTITY_SEED_REVISION)
    assert configured.database_url is not None
    upgrade(configured.database_url)

    from book_tracker.database import create_engine
    from book_tracker.infrastructure.jobs import JobRepository

    engine = create_engine(configured)
    repository = JobRepository(engine)
    job_id = repository.enqueue(None, "enrich_item", {"item_id": 1})
    connection = sqlite3.connect(configured.data_dir / "books.db")
    assert (
        connection.execute("SELECT user_id FROM jobs WHERE id = ?", (job_id,)).fetchone()[0] is None
    )
    connection.close()
    engine.dispose()


@pytest.mark.anyio
async def test_a_full_downgrade_returns_0016_and_the_application_still_starts(
    tmp_path: Path,
) -> None:
    """AC2: `alembic downgrade` from the new head restores the `0016` schema.

    The three revisions of the sprint all invert, rows follow the copy back, and
    the application still services it — its startup takes the pre-migration
    backup, reruns the chain upward and refers to being ready. A downgrade that
    corrosed any of that is one the restart: unless-stopped loop would find on a
    real server.
    """
    from alembic import command

    configured = database_at(tmp_path / "data", IDENTITY_SEED_REVISION)
    database_path = configured.data_dir / "books.db"
    seed_identity_library(database_path)
    assert configured.database_url is not None
    upgrade(configured.database_url)

    command.downgrade(alembic_config(configured.database_url), IDENTITY_SEED_REVISION)

    connection = sqlite3.connect(database_path)
    assert (
        connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        == IDENTITY_SEED_REVISION
    )
    tables = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    # Both identity revisions' additions are gone — not schema ghosts left behind.
    assert "users" not in tables and "sessions" not in tables
    # entries and shelves have carried user_id since 0002 — only the FK goes with
    # the downgrade. The import ledger and jobs gained theirs in 0019, so those are
    # the ones that must not leave a ghost column behind.
    for table in ("import_batches", "import_records", "import_effects", "jobs"):
        assert "user_id" not in {
            row[1] for row in connection.execute(f"PRAGMA table_info({table})")
        }
    # The library that never read anyone's data comes back with everything.
    assert connection.execute("SELECT count(*) FROM entries").fetchone()[0] == 2
    assert connection.execute("SELECT count(*) FROM entry_formats").fetchone()[0] == 1
    assert connection.execute("SELECT count(*) FROM import_records").fetchone()[0] == 1
    assert connection.execute("SELECT count(*) FROM jobs").fetchone()[0] == 2
    connection.close()

    # And the application serves it: backup, upgrade, ready.
    app = create_app(configured)
    async with app.router.lifespan_context(app):
        pass

    assert configured.database_url is not None
    assert pending_revisions(configured.database_url) == []
    connection = sqlite3.connect(database_path)
    assert connection.execute("SELECT count(*) FROM users").fetchone()[0] == 1
    connection.close()


@pytest.mark.anyio
async def test_the_pre_migration_backup_is_taken_and_restores_a_working_0016_database(
    tmp_path: Path,
) -> None:
    """AC9: the DEC-039 guard fires at 0016, and its copy is a rollback point.

    A database holding all six tables of the sprint gets backed up by app startup,
    migrated without error, and the preserved copy restores as a working `0016`
    library — same schema, same rows, no identity tables. That copy is the answer
    to the owner's question "how is this reversible?".
    """
    configured = database_at(tmp_path / "data", IDENTITY_SEED_REVISION)
    database_path = configured.data_dir / "books.db"
    seed_identity_library(database_path)
    app = create_app(configured)

    async with app.router.lifespan_context(app):
        pass

    assert configured.backup_dir is not None
    backups = sorted(configured.backup_dir.glob("pre-migration-*"))
    assert len(backups) == 1
    manifest = verify_backup(backups[0])
    # The copy predates the upgrade or it isn't a rollback point.
    assert manifest["alembic_revision"] == IDENTITY_SEED_REVISION
    assert manifest["label"] == "pre-migration"

    restored_dir = tmp_path / "restored"
    restore_backup(backups[0], into=restored_dir)

    connection = sqlite3.connect(restored_dir / "books.db")
    assert (
        connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        == IDENTITY_SEED_REVISION
    )
    tables = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "users" not in tables and "sessions" not in tables
    # Every row of the 0016 library rides in the backup.
    assert connection.execute("SELECT count(*) FROM entries").fetchone()[0] == 2
    assert connection.execute("SELECT count(*) FROM shelves").fetchone()[0] == 1
    assert connection.execute("SELECT count(*) FROM entry_formats").fetchone()[0] == 1
    assert connection.execute("SELECT count(*) FROM import_batches").fetchone()[0] == 1
    assert connection.execute("SELECT count(*) FROM import_records").fetchone()[0] == 1
    assert connection.execute("SELECT count(*) FROM import_effects").fetchone()[0] == 1
    assert connection.execute("SELECT count(*) FROM jobs").fetchone()[0] == 2
    # A restored 0016 — byte-for-byte, referentially clean.
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    connection.close()

    # The live database is on the chain and nothing is pending.
    assert configured.database_url is not None
    assert pending_revisions(configured.database_url) == []


def test_the_ownership_revision_downgrades_without_user_columns(tmp_path: Path) -> None:
    """Down from `0019` strips user_id from all four tables, rows intact."""
    from alembic import command

    configured = database_at(tmp_path / "data", IDENTITY_SEED_REVISION)
    database_path = configured.data_dir / "books.db"
    seed_identity_library(database_path)
    assert configured.database_url is not None
    command.upgrade(alembic_config(configured.database_url), LEDGER_REVISION)

    command.downgrade(alembic_config(configured.database_url), FK_REVISION)

    connection = sqlite3.connect(database_path)
    assert (
        connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == FK_REVISION
    )
    for table in ("import_batches", "import_records", "import_effects", "jobs"):
        assert "user_id" not in {
            row[1] for row in connection.execute(f"PRAGMA table_info({table})")
        }
    # Rows ride through the four rebuilds; the rebuild children of the ledger keep
    # their CASCADEs, which is what the seed asserts indirectly by still existing.
    assert connection.execute("SELECT count(*) FROM import_batches").fetchone()[0] == 1
    assert connection.execute("SELECT count(*) FROM import_records").fetchone()[0] == 1
    assert connection.execute("SELECT count(*) FROM import_effects").fetchone()[0] == 1
    assert connection.execute("SELECT count(*) FROM jobs").fetchone()[0] == 2
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    connection.close()
