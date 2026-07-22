"""Create the foundation schema probe."""

import sqlalchemy as sa

from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("schema_probe", sa.Column("id", sa.Integer(), primary_key=True))


def downgrade() -> None:
    op.drop_table("schema_probe")
