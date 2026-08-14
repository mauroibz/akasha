"""Rename `metadata.authors` to `metadata.creators` for the second domain.

An album has artists, a film has directors, a game has studios. `authors` was never
a property of an item — it was a property of books, written into the shared layer
because books were the only domain (DEC-052). The neutral concept is an ordered list
of **creators**, and the item's column projection follows it: `sort_author` becomes
`creator_primary` and `sort_author_normalized` becomes `creator_primary_normalized`.

`creator_sort_override` is **carried, never recomputed**. It is the only value on the
row that is not derived, and the heuristic that would replace it is known to be wrong
on exactly the names it exists to correct (DEC-051). `creator_sort` is left untouched
for the same reason: the first creator is the same string the first author was, so
every derived value on the row is already correct.

No table rebuild. `sort_author` is a VIRTUAL generated column, which SQLite can drop
and re-add through `ALTER TABLE`, and an ordinary column can be renamed in place — so
this migration never copies `items` and never risks the foreign keys pointing at it.
"""

import json

import sqlalchemy as sa

from alembic import op
from book_tracker.domain.normalization import normalize_text

revision = "0012_creators"
down_revision = "0011_creator_sort_names"
branch_labels = None
depends_on = None

CREATOR_PRIMARY = "json_extract(metadata, '$.creators[0]')"
AUTHOR_PRIMARY = "json_extract(metadata, '$.authors[0]')"


def _rewrite(connection: sa.Connection, source: str, target: str) -> None:
    """Move one metadata key to another, keeping every other key as it was."""
    rows = connection.execute(sa.text("SELECT id, metadata FROM items")).all()
    updates = []
    for identifier, metadata_json in rows:
        decoded = json.loads(metadata_json or "{}")
        if not isinstance(decoded, dict) or source not in decoded:
            updates.append({"id": identifier, "metadata": metadata_json, "normalized": None})
            continue
        moved = {(target if key == source else key): value for key, value in decoded.items()}
        names = moved.get(target)
        first = (
            names[0] if isinstance(names, list) and names and isinstance(names[0], str) else None
        )
        updates.append(
            {
                "id": identifier,
                "metadata": json.dumps(moved, ensure_ascii=False),
                "normalized": normalize_text(first) if first else None,
            }
        )
    if updates:
        connection.execute(
            sa.text(
                "UPDATE items SET metadata = :metadata,"
                " creator_primary_normalized = :normalized WHERE id = :id"
            ),
            updates,
        )


def upgrade() -> None:
    op.drop_index("ix_items_sort_author_id", table_name="items")
    op.execute("ALTER TABLE items DROP COLUMN sort_author")
    op.execute(
        "ALTER TABLE items RENAME COLUMN sort_author_normalized TO creator_primary_normalized"
    )
    _rewrite(op.get_bind(), "authors", "creators")
    op.execute(
        f"ALTER TABLE items ADD COLUMN creator_primary TEXT GENERATED ALWAYS AS ({CREATOR_PRIMARY})"
    )
    op.create_index("ix_items_creator_primary_id", "items", ["creator_primary", "id"])


def downgrade() -> None:
    op.drop_index("ix_items_creator_primary_id", table_name="items")
    op.execute("ALTER TABLE items DROP COLUMN creator_primary")
    op.execute(
        "ALTER TABLE items RENAME COLUMN creator_primary_normalized TO sort_author_normalized"
    )
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, metadata FROM items")).all()
    updates = []
    for identifier, metadata_json in rows:
        decoded = json.loads(metadata_json or "{}")
        if not isinstance(decoded, dict) or "creators" not in decoded:
            continue
        moved = {("authors" if key == "creators" else key): value for key, value in decoded.items()}
        updates.append({"id": identifier, "metadata": json.dumps(moved, ensure_ascii=False)})
    if updates:
        connection.execute(sa.text("UPDATE items SET metadata = :metadata WHERE id = :id"), updates)
    op.execute(
        f"ALTER TABLE items ADD COLUMN sort_author TEXT GENERATED ALWAYS AS ({AUTHOR_PRIMARY})"
    )
    op.create_index("ix_items_sort_author_id", "items", ["sort_author", "id"])
