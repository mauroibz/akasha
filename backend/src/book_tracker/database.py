import sqlite3
from collections.abc import Iterator

from sqlalchemy import Engine, event
from sqlalchemy import create_engine as sqlalchemy_create_engine
from sqlalchemy.engine import Connection

from book_tracker.config import Settings
from book_tracker.domain.normalization import normalize_text


def _sqlite_normalize_text(value: str | None) -> str | None:
    return normalize_text(value) if value is not None else None


def create_engine(settings: Settings) -> Engine:
    assert settings.database_url is not None
    engine = sqlalchemy_create_engine(settings.database_url)

    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_connection: sqlite3.Connection, _record: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={settings.sqlite_busy_timeout_ms:d}")
        cursor.close()
        dbapi_connection.create_function(
            "normalize_text", 1, _sqlite_normalize_text, deterministic=True
        )

    return engine


def connection(engine: Engine) -> Iterator[Connection]:
    with engine.connect() as database_connection:
        yield database_connection
