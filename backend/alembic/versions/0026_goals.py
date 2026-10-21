"""Gentle goals: a count per month or per year, per person and domain (Sprint 103, DEC-169).

Progress is not stored. It is read from `entries.date_finished` whenever it is asked
for, so a goal changed mid-year applies to the whole year and nothing here can drift
from the Diary. `period` is validated where it is written, not frozen in a CHECK:
the schema holds no application vocabulary (the migrations suite enforces it).
"""

import sqlalchemy as sa

from alembic import op

revision = "0026_goals"
down_revision = "0025_provider_responses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_type", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("period", sa.Text(), nullable=False),
        sa.Column("suggest", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.CheckConstraint("count BETWEEN 1 AND 999", name="ck_goals_count"),
        sa.UniqueConstraint("user_id", "item_type", name="uq_goals_user_type"),
    )


def downgrade() -> None:
    op.drop_table("goals")
