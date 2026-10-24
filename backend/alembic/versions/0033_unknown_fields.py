"""What the owner does not remember (Sprint 124, DEC-179).

`entries.unknown_fields` is a JSON list of the fields the owner answered *I don't
remember* for (`date_finished`, `formats` …), so the question about each is not asked
again. NULL is none, which is every existing row, so it is a plain `ADD COLUMN`.
"""

import sqlalchemy as sa

from alembic import op

revision = "0033_unknown_fields"
down_revision = "0032_shelf_suggestion_dismissals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("entries", sa.Column("unknown_fields", sa.Text(), nullable=True))


def downgrade() -> None:
    """The owner's answers are lost with the column."""
    op.execute("ALTER TABLE entries DROP COLUMN unknown_fields")
