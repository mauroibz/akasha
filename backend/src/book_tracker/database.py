import sqlite3
from collections.abc import Iterator

from sqlalchemy import Engine, event
from sqlalchemy import create_engine as sqlalchemy_create_engine
from sqlalchemy.engine import Connection

from book_tracker.config import Settings
from book_tracker.domain.normalization import normalize_text


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
        # Insights (Sprint 065) groups a ranking key the same way search/sort already
        # fold text — case and diacritics — which only holds if it is the same function.
        # Registered unconditionally: SQLite UDF registration has no per-call cost until
        # a query actually invokes it, so every connection carries it whether or not a
        # given request ranks anything.
        dbapi_connection.create_function(
            "normalize_text", 1, lambda value: normalize_text(value) if value is not None else None
        )

    return engine


def connection(engine: Engine) -> Iterator[Connection]:
    with engine.connect() as database_connection:
        yield database_connection
