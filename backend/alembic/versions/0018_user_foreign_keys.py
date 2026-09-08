"""Every row a user owns now points at the user who owns it.

Sprint 075 (DEC-146): `entries.user_id` and `shelves.user_id` have existed since
migration `0002` with a `server_default` of `1` and **no foreign key**, because
there was nothing to point at. `0017_users_and_sessions` created that something;
this revision attaches the constraint to both tables, `ON DELETE RESTRICT` on
each: a user with a library cannot be deleted out from under it. Deleting a user
is not a route in this sprint — Sprint 079 owns that product decision — but the
constraint has to state what deletion would do, and for someone's library the
answer is 'refuse' rather than the anything-else alternatives.

(Sessions, one revision over, deliberately CASCADE: a revocation mechanism that
refuses to be revoked along with its user is a worse one.)

**Why rebuilds, twice.** SQLite cannot `ALTER TABLE … ADD CONSTRAINT`, so a new
foreign key costs a copy, and both tables need one. The shape is the one `0013`
and `0015` already used: `copy_from` spells the table in full — deliberately not
reflected, deliberately not read from `models.py` — and Alembic recreates it,
moving every row across in an `INSERT … SELECT`. `copy_from` here describes each
table **as 0017 left it**, since the only change is on the `user_id` column itself
and lives inside the snapshot. A column left out is dropped with its data, an
index left out is dropped, and an `ondelete` omitted becomes `NO ACTION` — all
silently, which is why the sprint's tests read the result back from
`sqlite_master`.

The `server_default` of `1` survives on purpose. It is not vestigial: it is the
mechanism by which `INSERT`s from this build — where no request carries a user yet
(Sprint 076 removes the literals, 077 decides who asks) — keep meaning user 1, now
with a real referent behind the default. Taking it off would be a behaviour change
in a sprint whose whole contract is that there isn't one.

One caution inherited from `0015`, doubled. `entry_shelves` and `entry_formats`
both cascade from `entries`, and `entry_shelves` cascades from `shelves`; a
rebuild is a `DROP TABLE` that would empty all of them under
`PRAGMA foreign_keys=ON`. `alembic/env.py` never enables the pragma —
load-bearing, asserted in `test_migrations.py`, and now relied on by two rebuilds
in one revision instead of one.
"""

import sqlalchemy as sa

from alembic import op

revision = "0018_user_foreign_keys"
down_revision = "0017_users_and_sessions"
branch_labels = None
depends_on = None


def _user_id_column(with_user_fk: bool) -> sa.Column:
    """The `user_id` column, with or without the revision's new foreign key.

    A `Column` cannot change its constraints conditionally on a flag, and two
    near-copied columns drift; one function spells both states. The type, the
    `NOT NULL` and the `server_default "1"` are identical in each state — only the
    referent moves.
    """
    referencing = [sa.ForeignKey("users.id", ondelete="RESTRICT")] if with_user_fk else []
    return sa.Column(
        "user_id", sa.Integer(), *referencing, nullable=False, server_default="1"
    )


def _entries_table(with_user_fk: bool) -> sa.Table:
    """The `entries` table as `0017` left it, or with the new foreign key.

    A frozen snapshot, deliberately not read from `models.py`: a migration is
    history, and one that reads live code describes a different schema on every
    install. `copy_from` is a declaration, not a check — Alembic recreates whatever
    is spelled here, so every column, CHECK, unique and index below is one of the
    things whose silent loss the rebuild test watches.
    """
    return sa.Table(
        "entries",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), primary_key=True),
        _user_id_column(with_user_fk),
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
        sa.Column("progress", sa.Integer()),
        sa.UniqueConstraint("user_id", "item_id", name="uq_entries_user_item"),
        sa.CheckConstraint("score IS NULL OR score BETWEEN 1 AND 10", name="ck_entries_score"),
        sa.CheckConstraint("reread_count >= 0", name="ck_entries_reread_count"),
        sa.CheckConstraint("score_provisional IN (0, 1)", name="ck_entries_score_provisional"),
        sa.CheckConstraint("progress IS NULL OR progress >= 0", name="ck_entries_progress"),
        sa.Index("ix_entries_status", "user_id", "status"),
        sa.Index("ix_entries_score", "user_id", "score"),
        sa.Index("ix_entries_date_added", "user_id", "date_added"),
        sa.Index("ix_entries_user_status_date_id", "user_id", "status", "date_added", "id"),
        sa.Index("ix_entries_user_status_score_id", "user_id", "status", "score", "id"),
        sa.Index("ix_entries_user_finished_id", "user_id", "date_finished", "id"),
    )


def _shelves_table(with_user_fk: bool) -> sa.Table:
    """The `shelves` table as `0017` left it, or with the new foreign key."""
    return sa.Table(
        "shelves",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), primary_key=True),
        _user_id_column(with_user_fk),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.UniqueConstraint("user_id", "slug", name="uq_shelves_user_slug"),
    )


def upgrade() -> None:
    with op.batch_alter_table("entries", copy_from=_entries_table(True), recreate="always"):
        pass
    with op.batch_alter_table("shelves", copy_from=_shelves_table(True), recreate="always"):
        pass


def downgrade() -> None:
    """Both tables return to the FK-less shape they had from `0002` to `0017`.

    A downgrade is the inverse, not an assertion: the constraint goes and the rows
    stay, which is the only thing that is safe on a live library without knowing
    what Sprint 079 has since decided.
    """
    with op.batch_alter_table("entries", copy_from=_entries_table(False), recreate="always"):
        pass
    with op.batch_alter_table("shelves", copy_from=_shelves_table(False), recreate="always"):
        pass