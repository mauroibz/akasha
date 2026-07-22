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
