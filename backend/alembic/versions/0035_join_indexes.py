"""Indexes for two lookups that had none of their own (Sprint 129, performance).

- `entry_shelves(shelf_id)`: the primary key leads with `entry_id`, so "who is on
  this shelf" (the shelf filter, shelf previews and counts, deleting a shelf's
  memberships through the foreign key) scanned the whole table.
- `entries(item_id)`: the `(user_id, item_id)` unique index answers it only by a
  skip-scan, and only once `ANALYZE` has run; "who else holds this item" (the
  shared-item edit check, pruning, the item foreign key) needs it directly.

`IF NOT EXISTS`, because an install could have added one by hand while tuning.
"""

from alembic import op

revision = "0035_join_indexes"
down_revision = "0034_attachment_owners"
branch_labels = None
depends_on = None

_INDEXES = (
    ("ix_entry_shelves_shelf", "entry_shelves", "shelf_id"),
    ("ix_entries_item", "entries", "item_id"),
)


def upgrade() -> None:
    for name, table, columns in _INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")


def downgrade() -> None:
    for name, _table, _columns in _INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
