"""Saved views: a library filter kept under a name (Sprint 100, DEC-139).

`query` is the library's own URL query string, so a view reopens exactly the filters
that were on screen without this table knowing what a filter is. One person's views
are theirs alone (`user_id`), and a name is unique per person, so saving under the
same name again replaces the filters rather than adding a twin.
"""

import sqlalchemy as sa

from alembic import op

revision = "0024_saved_views"
down_revision = "0023_entry_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_views",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_saved_views_user_name"),
    )


def downgrade() -> None:
    op.drop_table("saved_views")
