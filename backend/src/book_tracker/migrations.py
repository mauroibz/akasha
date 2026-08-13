from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, inspect, text

from alembic import command


def alembic_config(database_url: str) -> Config:
    working_root = Path.cwd()
    source_root = Path(__file__).resolve().parents[2]
    root = working_root if (working_root / "alembic").is_dir() else source_root
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def upgrade(database_url: str, revision: str = "head") -> None:
    command.upgrade(alembic_config(database_url), revision)


def pending_revisions(database_url: str) -> list[str]:
    """Revisions between the database's current version and head, oldest first.

    Returns every revision for a database that has never been stamped, so a fresh
    file and an out-of-date one are distinguishable by the caller: only the second
    has anything worth backing up before the upgrade runs.
    """
    config = alembic_config(database_url)
    script = ScriptDirectory.from_config(config)
    engine = create_engine(database_url)
    try:
        if "alembic_version" not in inspect(engine).get_table_names():
            current = None
        else:
            with engine.connect() as connection:
                current = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one_or_none()
    finally:
        engine.dispose()
    head = script.get_current_head()
    if head is None or current == head:
        return []
    return [revision.revision for revision in script.iterate_revisions(head, current)][::-1]


def schema_is_current(engine: Engine) -> bool:
    inspector = inspect(engine)
    if "alembic_version" not in inspector.get_table_names():
        return False
    config = alembic_config(str(engine.url))
    with engine.connect() as connection:
        current = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    head: str | None = ScriptDirectory.from_config(config).get_current_head()
    return bool(current == head)
