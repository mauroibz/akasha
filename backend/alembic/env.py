from typing import Any

from sqlalchemy import Connection, Engine, engine_from_config, event, pool

from alembic import context

config = context.config
target_metadata = None


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _one_sqlite_transaction(engine: Engine) -> None:
    """Make the whole upgrade one real SQLite transaction (Sprint 129).

    pysqlite opens a transaction only before INSERT/UPDATE/DELETE, so every CREATE,
    DROP and ALTER a migration ran committed on its own while the DML around it
    rolled back. A failure halfway through 0034 left `_attachments_owned` behind at
    revision 0033, and every restart then died on "table already exists". This is
    SQLAlchemy's documented pysqlite recipe: take the driver out of its own
    transaction handling and emit BEGIN ourselves, so DDL rolls back with the rest
    and `alembic_version` moves only if every step of the upgrade succeeded.
    """

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection: Any, _record: object) -> None:
        dbapi_connection.isolation_level = None
        # Deliberately off for migrations (DEC-092). Migrations 0014, 0015 and 0016
        # batch-rebuild parent tables; SQLite implements that as `DROP TABLE`, which
        # would otherwise cascade entry_shelves, entry_formats, import_records and
        # import_effects away while reporting success. Runtime connections enable
        # the pragma in database.py; migration connections remain the documented
        # exception. SQLite ignores this pragma inside a transaction, so it is set
        # here, on the raw connection, before the BEGIN below can run.
        dbapi_connection.execute("PRAGMA foreign_keys=OFF")

    @event.listens_for(engine, "begin")
    def _on_begin(connection: Connection) -> None:
        # Deferred, not IMMEDIATE: every start runs this, and a start with nothing
        # pending only reads `alembic_version`. It must not need the write lock,
        # or a writer elsewhere (a backup, the CLI) would stall or fail the start.
        connection.exec_driver_sql("BEGIN")


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    if connectable.dialect.name == "sqlite":
        _one_sqlite_transaction(connectable)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            transactional_ddl=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
