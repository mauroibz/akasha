"""A rank inside a score (Sprint 116, DEC-176).

`entries.score_rank` orders entries that share a score, 1 the best, NULL not placed. It
never changes a score. A trigger sets it aside whenever the score changes, by any write
path, because a place among the 8s means nothing among the 7s.
"""

import sqlalchemy as sa

from alembic import op

revision = "0031_score_rank"
down_revision = "0030_score_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("entries", sa.Column("score_rank", sa.Integer(), nullable=True))
    op.execute(
        "CREATE TRIGGER score_rank_reset AFTER UPDATE OF score ON entries "
        "WHEN NEW.score IS NOT OLD.score AND NEW.score_rank IS NOT NULL BEGIN "
        "UPDATE entries SET score_rank = NULL WHERE id = NEW.id; END"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS score_rank_reset")
    op.execute("ALTER TABLE entries DROP COLUMN score_rank")
