"""Which episodes or chapters are done, on the entry that holds them (Sprint 107, DEC-171).

One nullable JSON text column. NULL is *no marks recorded*, which is every existing
row, so this is a plain `ADD COLUMN` with no rebuild: there is no constraint to place
(the shape is validated where it is written, and the schema holds no application
vocabulary), and SQLite adds a nullable column without copying the table.

Marks are not child entities (DEC-077): they have no status, date or row of their own,
and nothing outside the entry reads them.
"""

import sqlalchemy as sa

from alembic import op

revision = "0027_progress_marks"
down_revision = "0026_goals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("entries", sa.Column("progress_marks", sa.Text(), nullable=True))


def downgrade() -> None:
    """Marks are owner data and this loses them; `progress` keeps their count.

    A native `DROP COLUMN` (SQLite 3.35+), not a batch rebuild: nothing references the
    column, and a rebuild of `entries` is the copy 0015's docstring warns about.
    """
    op.execute("ALTER TABLE entries DROP COLUMN progress_marks")
