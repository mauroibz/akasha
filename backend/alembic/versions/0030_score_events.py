"""The score history: every change of a score, dated, with why (Sprint 114, DEC-176).

The rows are written by triggers on `entries`, not by the application: a card, the
opinion dialog, bulk edits, imports, an import's undo and a merge all change scores, and
a history any one of them could skip would be a history nobody could trust. The
application only labels a row it caused (`reread` rather than `time`) or adds a
confirmation ("still a 9") that changed nothing.

`reason` is NULL for a first score, `time` for a change with nothing else said, or
`reread`. It is validated where it is written; the schema holds no vocabulary.

The backfill gives every scored entry one first row, dated when it was finished, else
when it was added: the nearest thing to when that score was given that the library knows.
An entry that arrives with a score (an import, an add) is dated the same way, by its
finish date when it brings one, else now.
"""

import sqlalchemy as sa

from alembic import op

revision = "0030_score_events"
down_revision = "0029_duplicate_dismissals"
branch_labels = None
depends_on = None

_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def upgrade() -> None:
    op.create_table(
        "score_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "entry_id",
            sa.Integer(),
            sa.ForeignKey("entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("previous", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("recorded_at", sa.Text(), nullable=False),
    )
    op.create_index("ix_score_events_entry", "score_events", ["entry_id", "id"])
    op.execute(
        "INSERT INTO score_events (entry_id, score, previous, reason, note, recorded_at) "
        "SELECT id, score, NULL, NULL, NULL, COALESCE(date_finished, date_added) "
        "FROM entries WHERE score IS NOT NULL ORDER BY id"
    )
    op.execute(
        "CREATE TRIGGER score_events_insert AFTER INSERT ON entries "
        "WHEN NEW.score IS NOT NULL BEGIN "
        "INSERT INTO score_events (entry_id, score, previous, reason, note, recorded_at) "
        f"VALUES (NEW.id, NEW.score, NULL, NULL, NULL, COALESCE(NEW.date_finished, {_NOW})); END"
    )
    op.execute(
        "CREATE TRIGGER score_events_update AFTER UPDATE OF score ON entries "
        "WHEN NEW.score IS NOT OLD.score BEGIN "
        "INSERT INTO score_events (entry_id, score, previous, reason, note, recorded_at) "
        "VALUES (NEW.id, NEW.score, OLD.score, "
        f"CASE WHEN OLD.score IS NULL THEN NULL ELSE 'time' END, NULL, {_NOW}); END"
    )


def downgrade() -> None:
    """The history is owner data and this loses it; the scores themselves stay."""
    op.execute("DROP TRIGGER IF EXISTS score_events_update")
    op.execute("DROP TRIGGER IF EXISTS score_events_insert")
    op.drop_index("ix_score_events_entry", table_name="score_events")
    op.drop_table("score_events")
