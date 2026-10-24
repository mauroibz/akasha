"""Suggested shelves the owner said are not useful (Sprint 119, DEC-176).

Suggestions are computed from the library each time they are asked for, so only the
owner's "not useful" is kept, keyed by what the suggestion groups on
(`creator:…`, `series:…`, `work:…`), so it stays dismissed as the library grows.
"""

import sqlalchemy as sa

from alembic import op

revision = "0032_shelf_suggestion_dismissals"
down_revision = "0031_score_rank"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shelf_suggestion_dismissals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.UniqueConstraint("user_id", "key", name="uq_shelf_suggestion_dismissals"),
    )


def downgrade() -> None:
    op.drop_table("shelf_suggestion_dismissals")
