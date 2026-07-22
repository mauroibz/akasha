from pathlib import Path

from alembic.config import Config
from sqlalchemy import Engine, inspect, text

from alembic import command


def alembic_config(database_url: str) -> Config:
    working_root = Path.cwd()
    source_root = Path(__file__).resolve().parents[2]
    root = working_root if (working_root / "alembic").is_dir() else source_root
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def upgrade(database_url: str) -> None:
    command.upgrade(alembic_config(database_url), "head")


def schema_is_current(engine: Engine) -> bool:
    inspector = inspect(engine)
    if "alembic_version" not in inspector.get_table_names():
        return False
    config = alembic_config(str(engine.url))
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(config)
    with engine.connect() as connection:
        current = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    head: str | None = script.get_current_head()
    return bool(current == head)
