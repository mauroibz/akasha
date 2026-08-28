from sqlalchemy import engine_from_config, pool

from alembic import context

config = context.config
target_metadata = None


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # Deliberately do not enable SQLite `PRAGMA foreign_keys` here (DEC-092).
        # Migrations 0014, 0015 and 0016 batch-rebuild parent tables; SQLite implements
        # that as `DROP TABLE`, which would otherwise cascade entry_shelves,
        # entry_formats, import_records and import_effects away while reporting success.
        # Runtime connections enable the pragma in database.py; migration connections
        # must remain the documented exception until those rebuilds no longer exist.
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
