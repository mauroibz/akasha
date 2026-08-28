"""A connector's name belongs to the registry, not to the schema.

`ck_import_batches_kind` was written as `kind IN ('goodreads','calibre')` in migration
`0002` and frozen there. It is **the same mistake as `ck_entries_status`**, one table
over, and it survived because no connector had been added since — Sprint 041's
MyAnimeList reader is the first, and it failed on commit with
`CHECK constraint failed: ck_import_batches_kind`.

The consequence is the one DEC-067 row 1 already named for statuses: adding a connector
passes every application check and is then refused by SQLite, so it needs a migration on
a shared table. That directly contradicts what `docs/guides/adding-a-domain.md` promises
about an importer — "another object in that same directory plus one registry tuple
entry; it does not change the shared pipeline" — and it is the kind of conflict two
connectors written in parallel could not resolve, since both would point
`down_revision` at the same head.

**What replaces it is not nothing.** `IMPORTERS` in `domain/registry.py` is the
authority, and it is strictly stronger: the route resolves `IMPORTERS.get(name)` and
answers 404 `importer_not_found` for anything it does not hold, so a batch can only ever
be written for a connector this build actually registers. The constraint could never say
that — it could only hold whichever names existed on the day it was written, and it
happily admitted `calibre` on a row an anime connector produced.

`uq_import_batch_input` stays: `(kind, fingerprint)` is what makes a re-preview replay
rather than import twice, and that is a real invariant rather than a frozen list.

The table is spelled out in full because `copy_from` skips reflection and is a
declaration rather than a check — anything omitted here is silently dropped. And note
that a rebuild is a `DROP TABLE`: `import_records` and `import_effects` both cascade from
`import_batches`, so this would empty them under `PRAGMA foreign_keys=ON`.
`alembic/env.py` never enables it, which is load-bearing and is asserted in
`test_migrations.py`.
"""

import sqlalchemy as sa

from alembic import op

revision = "0016_import_kind_is_the_registrys"
down_revision = "0015_entry_progress"
branch_labels = None
depends_on = None

#: Only for the downgrade, and frozen rather than read from the registry: a migration is
#: history, and one that reads live code describes a different schema on every install.
_KIND_LIST = "'goodreads','calibre'"


def _import_batches(*checks: sa.CheckConstraint) -> sa.Table:
    """The `import_batches` table as it should be, for a batch rebuild."""
    return sa.Table(
        "import_batches",
        sa.MetaData(),
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("source_descriptor", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("preview_summary", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("counters", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("error", sa.Text()),
        sa.Column("committed_at", sa.Text()),
        sa.Column("undo_expires_at", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.UniqueConstraint("kind", "fingerprint", name="uq_import_batch_input"),
        *checks,
    )


def upgrade() -> None:
    with op.batch_alter_table("import_batches", copy_from=_import_batches(), recreate="always"):
        pass


def downgrade() -> None:
    """Restore the snapshot, which is only safe for a library holding no later connector.

    A batch written by a connector this list never knew would fail the restored
    constraint — the correct outcome rather than a silent remap onto a connector that
    means something else.
    """
    check = sa.CheckConstraint(f"kind IN ({_KIND_LIST})", name="ck_import_batches_kind")
    with op.batch_alter_table(
        "import_batches", copy_from=_import_batches(check), recreate="always"
    ):
        pass
