"""Home's layout, one per person (Sprint 131, DEC-183).

The order, size and hidden flag of each of Home's modules, as one JSON list. The
module keys and sizes are validated where they are written and read leniently, never
frozen in the schema: a key the application no longer knows is ignored on read, so a
layout saved before a module was added or removed still loads.
"""

import sqlalchemy as sa

from alembic import op

revision = "0036_home_layouts"
down_revision = "0035_join_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "home_layouts",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("layout_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("home_layouts")
