"""Whose work an import is, and whose job a job is.

Sprint 075 (DEC-146): `import_batches`, `import_records` and `import_effects`
held an import and its undo ledger with no owner, and `jobs` could not tell an
importer's enrichment pass from a background backfill that belonged to nobody.
This revision gives the first three a user and the fourth one the column that
will tell the two apart.

**The three ledger tables gain `user_id`, `NOT NULL`, defaulted and backfilled to
1, with a foreign key to `users` (RESTRICT).** An import is someone's work; on a
`0016` database that someone is only ever the seeded user, and the column's
`server_default '1'` is also how this build's unchanged INSERT paths keep writing
(Sprint 076 threads the real one through; nothing in this sprint may change
behaviour, AC8). RESTRICT like `entries` and `shelves`: a user cannot be deleted
out from under their import history any more than out from under their library,
and Sprint 079 owns whatever deletion ends up meaning.

**`jobs` gains a *nullable* `user_id`.** This is the deliberate asymmetry the
sprint's risks section names: an enrichment job acts on a shared cached item and
belongs to nobody — forcing it to claim a user is the actual lie — while a job the
import pipeline chains to its batch belongs to whoever ran it. The migration
tells them apart the only way a `0016` row can be told: `batch_id`. Jobs chained
to a batch are backfilled to the seeded user; jobs with no batch stay nobody's.
Nobody's jobs must not go to user 1 by default, which is why the column has no
default at all.

**Why four rebuilds.** A new foreign key on SQLite costs a table copy, same shape
as `0013`, `0015` and `0018`. Each `copy_from` spells the table in full as `0018`
left it — deliberately not reflected, not read from `models.py` — and carries
every constraint and index, whose silent loss is exactly the failure mode the
tests read `sqlite_master` to catch. `ck_jobs_state`, `ck_jobs_attempts` and all
three ledger constraints/uniques are in the snapshots; `ix_jobs_claim` and the
two ledger indexes ride the same rebuilds.

Rebuild order is `import_batches`, then `import_records` and `import_effects`
(both CASCADE from it), then `jobs` (SET NULL to it) — under
`PRAGMA foreign_keys=ON` any drop would fire those child rules, and
`alembic/env.py` never enables the pragma, which is load-bearing here as in
`0013`/`0015`/`0016`/`0018`.
"""

import sqlalchemy as sa

from alembic import op

revision = "0019_ownership_on_the_import_ledger"
down_revision = "0018_user_foreign_keys"
branch_labels = None
depends_on = None


def _import_batches(*extra: sa.Column) -> sa.Table:
    """`import_batches` as `0018` left it (0016 dropped its kind CHECK), plus extras.

    Frozen snapshot: a migration is history, and a column, constraint or default
    omitted from `copy_from` is dropped in silence on the rebuild.
    """
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
        *extra,
        sa.UniqueConstraint("kind", "fingerprint", name="uq_import_batch_input"),
    )


def _import_records(*extra: sa.Column) -> sa.Table:
    """`import_records` as `0018` left it, plus extras."""
    return sa.Table(
        "import_records",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "batch_id",
            sa.Text(),
            sa.ForeignKey("import_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("normalized_payload", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("matched_item_id", sa.Integer(), sa.ForeignKey("items.id", ondelete="SET NULL")),
        sa.Column(
            "matched_entry_id", sa.Integer(), sa.ForeignKey("entries.id", ondelete="SET NULL")
        ),
        sa.Column("match_kind", sa.Text()),
        sa.Column("planned_action", sa.Text()),
        sa.Column("conflicts", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("validation_errors", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("ambiguity_resolution", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        *extra,
        sa.UniqueConstraint("batch_id", "row_number", name="uq_import_record_row"),
        sa.Index("ix_import_records_batch_action", "batch_id", "planned_action", "row_number"),
    )


def _import_effects(*extra: sa.Column) -> sa.Table:
    """`import_effects` as `0018` left it, plus extras."""
    return sa.Table(
        "import_effects",
        sa.MetaData(),
        sa.Column("effect_id", sa.Integer(), primary_key=True),
        sa.Column(
            "batch_id",
            sa.Text(),
            sa.ForeignKey("import_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "record_id",
            sa.Integer(),
            sa.ForeignKey("import_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("effect_type", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("before_values", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("after_values", sa.Text(), nullable=False, server_default="{}"),
        *extra,
        sa.Index("ix_import_effects_batch_effect", "batch_id", "effect_id"),
    )


def _jobs(*extra: sa.Column) -> sa.Table:
    """`jobs` as `0018` left it (0006 appended error_code), plus extras."""
    return sa.Table(
        "jobs",
        sa.MetaData(),
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("batch_id", sa.Text(), sa.ForeignKey("import_batches.id", ondelete="SET NULL")),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("progress", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("error", sa.Text()),
        sa.Column("error_code", sa.Text()),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.Text(), nullable=False),
        sa.Column("heartbeat_at", sa.Text()),
        sa.Column("lease_expires_at", sa.Text()),
        sa.Column("finished_at", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        *extra,
        sa.CheckConstraint(
            "state IN ('queued','running','succeeded','failed','cancelled')", name="ck_jobs_state"
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_jobs_attempts"),
        sa.Index("ix_jobs_claim", "state", "available_at"),
    )


def _owned_user_column(table: str) -> sa.Column:
    """The ledger's `user_id`: NOT NULL, defaulted to the seeded user, RESTRICT.

    New columns arrive through `batch_op.add_column` and never through `copy_from`:
    Alembic builds the rebuild's `INSERT INTO _alembic_tmp_x (…) SELECT … FROM x`
    from the `copy_from` columns, so a snapshot that already spells the new column
    dies on `no such column` — and Alembic deliberately excludes a batch-added
    column from that SELECT (the lesson `0015` wrote down; this revision adds a
    column to four tables in one file). The `server_default` is what fills the copy
    with 1 on every existing row, and what this build's unchanged INSERT paths
    keep landing on.

    The foreign key carries a name because a batch-added column's constraints go
    through `add_constraint`, which refuses an unnamed one; SQLite emits no
    constraint name for an FK, so the name exists for Alembic's bookkeeping alone.
    """
    return sa.Column(
        "user_id",
        sa.Integer(),
        sa.ForeignKey("users.id", ondelete="RESTRICT", name=f"fk_{table}_user_id"),
        nullable=False,
        server_default="1",
    )


def upgrade() -> None:
    with op.batch_alter_table("import_batches", copy_from=_import_batches(), recreate="always") as batch:
        batch.add_column(_owned_user_column("import_batches"))
    with op.batch_alter_table("import_records", copy_from=_import_records(), recreate="always") as batch:
        batch.add_column(_owned_user_column("import_records"))
    with op.batch_alter_table("import_effects", copy_from=_import_effects(), recreate="always") as batch:
        batch.add_column(_owned_user_column("import_effects"))

    # No default on `jobs.user_id` on purpose (docstring): nobody's work must not
    # silently become user 1's. A batch-added column copies NULL for every existing
    # row, so the import-owned half is attributed after the copy.
    with op.batch_alter_table("jobs", copy_from=_jobs(), recreate="always") as batch:
        batch.add_column(
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="RESTRICT", name="fk_jobs_user_id"),
                nullable=True,
            )
        )
    # A migration constant, spelled rather than bound: the revision describes what it
    # did, and nobody on a 0016 database is anyone but the seeded user.
    op.execute(sa.text("UPDATE jobs SET user_id = 1 WHERE batch_id IS NOT NULL"))


def downgrade() -> None:
    """All four tables lose `user_id` and their link to `users`; rows stay.

    The downward copy is 0018's shape, so the four snapshots are reused as their
    own images and each column is dropped explicitly rather than reflected away.
    The ownership fact is not recoverable once dropped — a restored `0016`
    database says an import belongs to nobody, which is exactly what `0016`
    meant.
    """
    # `copy_from` describes the table as the downgrade finds it — user_id included —
    # and the drop removes it; a snapshot missing the column would describe the wrong
    # shape to the downward copy. (`jobs` is the nullable variant: that is how the
    # table at the downgrade's start looks.)
    for table, snapshot in (
        ("import_batches", _import_batches),
        ("import_records", _import_records),
        ("import_effects", _import_effects),
    ):
        with op.batch_alter_table(
            table, copy_from=snapshot(_owned_user_column(table)), recreate="always"
        ) as batch:
            batch.drop_column("user_id")
    with op.batch_alter_table(
        "jobs",
        copy_from=_jobs(
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="RESTRICT", name="fk_jobs_user_id"),
                nullable=True,
            )
        ),
        recreate="always",
    ) as batch:
        batch.drop_column("user_id")