"""How far through one of these you are, on the entry that holds it.

DEC-077 shape (a), built. The verdict priced entry *depth* across nine shared
surfaces, rejected child entities carrying their own state, and chose one number on
the flat entry instead — declared by the domain that means something by it. This is
the only shared-table change in the anime line (DEC-089).

Nullable because "not recorded" and "zero watched" are different facts and the
owner's library holds both: `Black Clover` dropped at 20 of 170, and a `Plan to
Watch` row sitting at 0 of 1. A `server_default` of `0` — which `reread_count` and
`score_provisional` legitimately carry two lines apart from it below — would assert
that every book and album entry had recorded a progress of zero, destroying that
distinction for the whole existing library in the one direction a downgrade cannot
repair.

**A CHECK for the floor and none for the ceiling**, and the asymmetry is the point.
The total lives in the item's opaque metadata, which the domain does not control:
AniList returns `episodes: null` for an airing show, a weekly series' cached total
is stale by definition, and a metadata refresh can lower `episodes` under a count
already stored — making a row that was valid when written violate a rule on its next
write. That is `ck_entries_status`'s mistake in a new costume, and `0014` exists to
undo it (DEC-067 row 1). Non-negativity is the opposite kind of rule: a neutral fact
about a count that no domain redefines and no provider can invalidate, which is the
category `ck_entries_score`, `ck_entries_reread_count` and
`ck_entries_score_provisional` already occupy. It is spelled the way they are
because it is the same kind of thing.

**Why a rebuild.** SQLite cannot ALTER a constraint into place, so a named CHECK
costs a copy. Two rules make that copy safe:

1. `copy_from` describes `entries` **as 0014 left it**, without `progress`. Alembic
   builds the `INSERT INTO _alembic_tmp_entries (…) SELECT … FROM entries` from the
   `copy_from` columns, so a `copy_from` that already spells the new column dies on
   `no such column: entries.progress`. The column arrives through `add_column`,
   which Alembic deliberately excludes from that SELECT.
2. `copy_from` rather than reflection — but **not** for the reason `0014`'s docstring
   gives. SQLAlchemy 2.0 *does* reflect named SQLite CHECK constraints now. A
   reflected rebuild still silently drops an **unnamed** CHECK and downgrades
   `ON DELETE RESTRICT` on the `items` foreign key to a bare reference. Spelling the
   table is how this migration says what it means instead of trusting a round trip.

The columns are built inside the function rather than shared from a module-level
tuple: a `Column` object may belong to only one `Table`, and this file builds two.

One caution for whoever writes the next rebuild of this table. Alembic's recreate is
create-tmp, `INSERT…SELECT`, **`DROP TABLE entries`**, rename. Under
`PRAGMA foreign_keys=ON` that DROP performs an implicit delete and fires the
`ON DELETE CASCADE` on `entry_shelves` and `entry_formats` — emptying both, with no
error and a migration that reports success. `alembic/env.py` never enables the
pragma, unlike `database.py`, and `0013` and `0014` already depend on that. It is
load-bearing; `test_migrations.py` now asserts the child rows survive.
"""

import sqlalchemy as sa

from alembic import op

revision = "0015_entry_progress"
down_revision = "0014_status_is_the_domains"
branch_labels = None
depends_on = None

_PROGRESS_CHECK = "progress IS NULL OR progress >= 0"


def _entries_table(*extra: sa.Column | sa.CheckConstraint) -> sa.Table:
    """The `entries` table as this revision found it, plus whatever `extra` adds.

    A frozen snapshot, deliberately not imported from `0014` and deliberately not read
    from `models.py`: a migration is history, and one that reads live code describes a
    different schema on every install.

    `copy_from` is a *declaration*, not a check — Alembic recreates whatever is spelled
    here and never compares it to what is actually there. A column omitted is dropped
    with its data, an index omitted is dropped, a CHECK omitted is dropped, and an
    `ondelete` omitted becomes `NO ACTION`. All of them silently.
    """
    return sa.Table(
        "entries",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "item_id", sa.Integer(), sa.ForeignKey("items.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer()),
        sa.Column("notes", sa.Text()),
        sa.Column("date_added", sa.Text(), nullable=False),
        sa.Column("date_started", sa.Text()),
        sa.Column("date_finished", sa.Text()),
        sa.Column("reread_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score_provisional", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suggested_status", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        *extra,
        sa.UniqueConstraint("user_id", "item_id", name="uq_entries_user_item"),
        sa.CheckConstraint("score IS NULL OR score BETWEEN 1 AND 10", name="ck_entries_score"),
        sa.CheckConstraint("reread_count >= 0", name="ck_entries_reread_count"),
        sa.CheckConstraint("score_provisional IN (0, 1)", name="ck_entries_score_provisional"),
        sa.Index("ix_entries_status", "user_id", "status"),
        sa.Index("ix_entries_score", "user_id", "score"),
        sa.Index("ix_entries_date_added", "user_id", "date_added"),
        sa.Index("ix_entries_user_status_date_id", "user_id", "status", "date_added", "id"),
        sa.Index("ix_entries_user_status_score_id", "user_id", "status", "score", "id"),
        sa.Index("ix_entries_user_finished_id", "user_id", "date_finished", "id"),
    )


def upgrade() -> None:
    with op.batch_alter_table("entries", copy_from=_entries_table(), recreate="always") as batch_op:
        # Not in `copy_from`: the row copy reads the old table, which has no such
        # column. Alembic excludes a batch-added column from that SELECT for exactly
        # this reason.
        batch_op.add_column(sa.Column("progress", sa.Integer(), nullable=True))
        batch_op.create_check_constraint("ck_entries_progress", _PROGRESS_CHECK)


def downgrade() -> None:
    """Drop the column, which SQLite will not do with a plain `ALTER TABLE`.

    `ALTER TABLE entries DROP COLUMN progress` fails with `error in table entries after
    drop column: no such column: progress` while a CHECK still mentions it, so down is
    a rebuild too. The constraint is dropped explicitly rather than left out of
    `copy_from`: a text CHECK reports no columns to Alembic, so the subset filter never
    excludes it and it would otherwise be carried onto a table that no longer has the
    column.

    A stored progress is owner data and this loses it. That is what down means here.
    """
    with op.batch_alter_table(
        "entries",
        copy_from=_entries_table(
            sa.Column("progress", sa.Integer()),
            sa.CheckConstraint(_PROGRESS_CHECK, name="ck_entries_progress"),
        ),
        recreate="always",
    ) as batch_op:
        batch_op.drop_constraint("ck_entries_progress", type_="check")
        batch_op.drop_column("progress")
