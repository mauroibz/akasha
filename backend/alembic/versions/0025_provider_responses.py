"""Provider search answers kept for a day (Sprint 101, proposal §6.6).

Keyed by provider and the normalized question, so the command bar typing the same
title twice, or an import searching the same row again, costs one request to a free
API. Only answers are stored; a failure is never cached.
"""

import sqlalchemy as sa

from alembic import op

revision = "0025_provider_responses"
down_revision = "0024_saved_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_responses",
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("request_key", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("provider", "request_key"),
    )


def downgrade() -> None:
    op.drop_table("provider_responses")
