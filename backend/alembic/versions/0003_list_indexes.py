"""Add composite indexes for library keyset queries."""

from alembic import op

revision = "0003_list_indexes"
down_revision = "0002_domain_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_entries_user_status_date_id",
        "entries",
        ["user_id", "status", "date_added", "id"],
    )
    op.create_index(
        "ix_entries_user_status_score_id", "entries", ["user_id", "status", "score", "id"]
    )
    op.create_index("ix_entries_user_finished_id", "entries", ["user_id", "date_finished", "id"])
    op.create_index("ix_items_year_id", "items", ["year", "id"])
    op.create_index("ix_items_sort_author_id", "items", ["sort_author", "id"])


def downgrade() -> None:
    op.drop_index("ix_items_sort_author_id", table_name="items")
    op.drop_index("ix_items_year_id", table_name="items")
    op.drop_index("ix_entries_user_finished_id", table_name="entries")
    op.drop_index("ix_entries_user_status_score_id", table_name="entries")
    op.drop_index("ix_entries_user_status_date_id", table_name="entries")
