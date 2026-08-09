"""Record a typed failure code alongside the human-readable job error."""

import sqlalchemy as sa

from alembic import op

revision = "0006_job_error_code"
down_revision = "0005_book_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("error_code", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "error_code")
