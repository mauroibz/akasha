"""Pairs the owner said are not duplicates (Sprint 113, DEC-176).

Candidates are found from stored data each time they are asked for, so nothing about
them is kept except the owner's answer that two entries differ. A pair is stored with
its lower id first, so it is one row whichever way it was asked. The rows go with
either entry, and with the user.
"""

import sqlalchemy as sa

from alembic import op

revision = "0029_duplicate_dismissals"
down_revision = "0028_location_and_loans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "duplicate_dismissals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entry_low",
            sa.Integer(),
            sa.ForeignKey("entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entry_high",
            sa.Integer(),
            sa.ForeignKey("entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint("entry_low < entry_high", name="ck_duplicate_dismissals_order"),
        sa.UniqueConstraint(
            "user_id", "entry_low", "entry_high", name="uq_duplicate_dismissals_pair"
        ),
    )


def downgrade() -> None:
    op.drop_table("duplicate_dismissals")
