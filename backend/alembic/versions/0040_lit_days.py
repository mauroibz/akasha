"""Lit days (Sprint 147, DEC-193): the days something was read, watched or finished.

The Journal's *Every day* widget draws a light per day. Progress marks say which
episode or chapter is done, not on which day, so the day is recorded here: once per
person, day and entry, with how it came to be lit (`progress`, `finish`, or a `tap`
by hand; the application's words, checked where they are written and not frozen
here). A day lit by hand for nothing in particular has no entry, once per person and
day.

Days before this migration are lit from the dates the library already holds: the day
an entry was started and the day it was finished. A stored date that is not a whole
day (a bare year, as an old import can leave) is skipped.
"""

import sqlalchemy as sa

from alembic import op

revision = "0040_lit_days"
down_revision = "0039_media_preferences"
branch_labels = None
depends_on = None

#: `YYYY-MM-DD` and nothing else.
_DAY = "'____-__-__'"


def upgrade() -> None:
    op.create_table(
        "lit_days",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day", sa.Text(), nullable=False),
        sa.Column(
            "entry_id",
            sa.Integer(),
            sa.ForeignKey("entries.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_index(
        "uq_lit_days_entry",
        "lit_days",
        ["user_id", "day", "entry_id"],
        unique=True,
        sqlite_where=sa.text("entry_id IS NOT NULL"),
    )
    op.create_index(
        "uq_lit_days_bare",
        "lit_days",
        ["user_id", "day"],
        unique=True,
        sqlite_where=sa.text("entry_id IS NULL"),
    )
    # Finishes first, so a day an entry was both started and finished on reads as the
    # finish; then starts, ignored where that entry already lights that day.
    for column, source in (("date_finished", "finish"), ("date_started", "progress")):
        op.execute(
            f"INSERT OR IGNORE INTO lit_days (user_id, day, entry_id, source, created_at)"
            f" SELECT user_id, {column}, id, '{source}', {column} FROM entries"
            f" WHERE {column} LIKE {_DAY} AND status != 'unsorted'"
        )


def downgrade() -> None:
    op.drop_table("lit_days")
