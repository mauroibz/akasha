"""Where a thing is, and who has it (Sprint 110, DEC-176).

`entries.location` is one line of the owner's own text ("Living room, shelf 2"); NULL is
*not recorded*, which is every existing row, so it is a plain `ADD COLUMN`.

A loan is a row of its own because a thing is lent more than once and the history is
the owner's. At most one loan per entry is open (no `returned_on`), held by a partial
unique index rather than by the application alone. Loans go with their entry.
"""

import sqlalchemy as sa

from alembic import op

revision = "0028_location_and_loans"
down_revision = "0027_progress_marks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("entries", sa.Column("location", sa.Text(), nullable=True))
    op.create_table(
        "loans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "entry_id",
            sa.Integer(),
            sa.ForeignKey("entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("person", sa.Text(), nullable=False),
        sa.Column("lent_on", sa.Text(), nullable=False),
        sa.Column("returned_on", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    op.create_index("ix_loans_entry", "loans", ["entry_id"])
    op.create_index(
        "uq_loans_one_open",
        "loans",
        ["entry_id"],
        unique=True,
        sqlite_where=sa.text("returned_on IS NULL"),
    )


def downgrade() -> None:
    """Locations and loans are owner data and this loses them."""
    op.drop_index("uq_loans_one_open", table_name="loans")
    op.drop_index("ix_loans_entry", table_name="loans")
    op.drop_table("loans")
    op.execute("ALTER TABLE entries DROP COLUMN location")
