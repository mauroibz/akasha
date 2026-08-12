from pathlib import Path

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError

from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.migrations import alembic_config, upgrade


def migrated_engine(tmp_path: Path) -> Engine:
    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url)
    return create_engine(configured)


def test_complete_schema_migrates_and_round_trips(tmp_path: Path) -> None:
    from alembic import command

    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    command.upgrade(alembic_config(configured.database_url), "0001_foundation")
    command.upgrade(alembic_config(configured.database_url), "head")
    engine = create_engine(configured)
    expected = {
        "items",
        "item_identifiers",
        "item_sources",
        "entries",
        "shelves",
        "entry_shelves",
        "import_batches",
        "import_records",
        "import_effects",
        "jobs",
    }
    assert expected <= set(inspect(engine).get_table_names())
    command.downgrade(alembic_config(configured.database_url), "0001_foundation")
    assert "items" not in inspect(engine).get_table_names()
    command.upgrade(alembic_config(configured.database_url), "head")
    assert expected <= set(inspect(engine).get_table_names())


def test_list_index_migration_round_trips_from_domain_head(tmp_path: Path) -> None:
    from alembic import command

    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    config = alembic_config(configured.database_url)
    command.upgrade(config, "0002_domain_schema")
    command.upgrade(config, "head")


def test_import_planning_indexes_migrate_from_previous_head(tmp_path: Path) -> None:
    from alembic import command

    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    config = alembic_config(configured.database_url)
    command.upgrade(config, "0003_list_indexes")
    command.upgrade(config, "head")
    engine = create_engine(configured)
    assert "ix_import_records_batch_action" in {
        index["name"] for index in inspect(engine).get_indexes("import_records")
    }
    command.downgrade(config, "0003_list_indexes")
    assert "ix_import_records_batch_action" not in {
        index["name"] for index in inspect(engine).get_indexes("import_records")
    }
    command.upgrade(config, "head")
    engine = create_engine(configured)
    assert "ix_entries_user_status_date_id" in {
        index["name"] for index in inspect(engine).get_indexes("entries")
    }
    command.downgrade(config, "0002_domain_schema")
    assert "ix_entries_user_status_date_id" not in {
        index["name"] for index in inspect(engine).get_indexes("entries")
    }
    command.upgrade(config, "head")


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO entries(item_id,status,score,date_added) VALUES(1,'bad',NULL,'now')",
        "INSERT INTO entries(item_id,status,score,date_added) VALUES(1,'read',11,'now')",
        "INSERT INTO entries(item_id,status,reread_count,date_added) VALUES(1,'read',-1,'now')",
        "INSERT INTO entries(item_id,status,score_provisional,date_added) VALUES(1,'read',2,'now')",
    ],
)
def test_entry_constraints_reject_invalid_values(tmp_path: Path, statement: str) -> None:
    engine = migrated_engine(tmp_path)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO items(title,metadata,created_at,updated_at) VALUES('T','{}','n','n')")
        )
        with pytest.raises(IntegrityError):
            connection.execute(text(statement))


def test_source_primary_and_shelf_relationship_constraints(tmp_path: Path) -> None:
    engine = migrated_engine(tmp_path)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO items(title,metadata,created_at,updated_at) VALUES('T','{}','n','n')")
        )
        connection.execute(
            text(
                "INSERT INTO item_sources"
                "(item_id,source,source_id,is_primary,created_at,updated_at) "
                "VALUES(1,'a','1',1,'n','n')"
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO item_sources"
                    "(item_id,source,source_id,is_primary,created_at,updated_at) "
                    "VALUES(1,'b','2',1,'n','n')"
                )
            )
        with pytest.raises(IntegrityError):
            connection.execute(text("INSERT INTO entry_shelves(entry_id,shelf_id) VALUES(99,99)"))


# Sprint 017 / DEC-036: the normalized sort projection.
#
# The columns exist so text ordering stops invoking the `normalize_text` UDF once
# per candidate row. That only holds if their contents are indistinguishable from
# what the UDF would have returned, so these tests pin the equivalence rather than
# asserting the columns are merely non-empty.


def test_normalized_projection_matches_the_domain_function_on_insert(tmp_path: Path) -> None:
    from sqlalchemy.orm import Session

    from book_tracker.domain.normalization import normalize_text
    from book_tracker.infrastructure.models import ItemRow

    engine = migrated_engine(tmp_path)
    title = "  Cien años—de SOLEDAD! "
    author = "García Márquez, Gabriel"
    with Session(engine) as session:
        session.add(
            ItemRow(
                type="book",
                title=title,
                subtitle=None,
                year=1967,
                cover_path=None,
                identifiers="{}",
                metadata_json=f'{{"authors": ["{author}"]}}',
                created_at="now",
                updated_at="now",
            )
        )
        session.commit()
    with engine.connect() as connection:
        stored = connection.execute(
            text("SELECT title_normalized, sort_author_normalized, sort_author FROM items")
        ).one()
    assert stored[0] == normalize_text(title)
    assert stored[1] == normalize_text(author)
    # The projection must track the generated column it stands in for.
    assert stored[2] == author


def test_normalized_projection_follows_a_later_title_and_author_change(tmp_path: Path) -> None:
    from sqlalchemy.orm import Session

    from book_tracker.domain.normalization import normalize_text
    from book_tracker.infrastructure.models import ItemRow

    engine = migrated_engine(tmp_path)
    with Session(engine) as session:
        item = ItemRow(
            type="book",
            title="Original",
            subtitle=None,
            year=None,
            cover_path=None,
            identifiers="{}",
            metadata_json='{"authors": ["Original Author"]}',
            created_at="now",
            updated_at="now",
        )
        session.add(item)
        session.commit()
        item.title = "Rayuela"
        item.metadata_json = '{"authors": ["Cortázar, Julio"]}'
        session.commit()
    with engine.connect() as connection:
        stored = connection.execute(
            text("SELECT title_normalized, sort_author_normalized FROM items")
        ).one()
    assert stored[0] == normalize_text("Rayuela")
    assert stored[1] == normalize_text("Cortázar, Julio")


def test_item_without_authors_projects_a_null_sort_author(tmp_path: Path) -> None:
    from sqlalchemy.orm import Session

    from book_tracker.infrastructure.models import ItemRow

    engine = migrated_engine(tmp_path)
    with Session(engine) as session:
        session.add(
            ItemRow(
                type="book",
                title="Anonymous",
                subtitle=None,
                year=None,
                cover_path=None,
                identifiers="{}",
                metadata_json="{}",
                created_at="now",
                updated_at="now",
            )
        )
        session.commit()
    with engine.connect() as connection:
        stored = connection.execute(
            text("SELECT sort_author, sort_author_normalized FROM items")
        ).one()
    assert stored == (None, None)


def test_projection_migration_backfills_rows_written_before_it(tmp_path: Path) -> None:
    from alembic import command

    from book_tracker.domain.normalization import normalize_text

    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    config = alembic_config(configured.database_url)
    command.upgrade(config, "0006_job_error_code")
    engine = create_engine(configured)
    rows = [
        ("Pedro Páramo", '{"authors": ["Rulfo, Juan"]}'),
        ("Ædificium", '{"authors": []}'),
        ("Metadata that is not an object", "[]"),
    ]
    with engine.begin() as connection:
        for index, (title, metadata) in enumerate(rows, start=1):
            connection.execute(
                text(
                    "INSERT INTO items (id, type, title, identifiers, metadata,"
                    " created_at, updated_at)"
                    " VALUES (:id, 'book', :title, '{}', :metadata, 'now', 'now')"
                ),
                {"id": index, "title": title, "metadata": metadata},
            )
    command.upgrade(config, "head")
    engine = create_engine(configured)
    with engine.connect() as connection:
        stored = connection.execute(
            text("SELECT title_normalized, sort_author_normalized FROM items ORDER BY id")
        ).all()
    assert stored[0] == (normalize_text("Pedro Páramo"), normalize_text("Rulfo, Juan"))
    assert stored[1] == (normalize_text("Ædificium"), None)
    # `metadata` is only guaranteed to be JSON, not to be an object carrying
    # authors. Such a row still gets a usable title projection instead of
    # failing the migration for the whole library.
    assert stored[2] == (normalize_text("Metadata that is not an object"), None)
    command.downgrade(config, "0006_job_error_code")
    assert "title_normalized" not in {
        column["name"] for column in inspect(create_engine(configured)).get_columns("items")
    }
