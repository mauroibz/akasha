"""Reduce descriptions already stored as provider markup to plain text.

`strip_html` now runs at the provider boundary, so records fetched from this
revision onwards arrive as prose. That does nothing for a library imported
earlier, where the markup is already in `items.metadata`: the Sprint 019
walkthrough saw `<p>To stay competitive...` and `<p> <b>` rendered as literal
text on the detail page, because the UI escapes what it renders.

Only `metadata.description` is touched, and only where it actually contains a
tag. A row whose description is already prose is left byte-identical rather than
rewritten through the parser, so this migration is a no-op for most libraries.

There is no downgrade path that restores markup, and inventing one would be
dishonest — the tags are gone once stripped. `downgrade` is deliberately a no-op
rather than a lie. Startup takes a backup before migrating (DEC-039), so the
rollback point exists outside this file.
"""

import json

import sqlalchemy as sa

from alembic import op
from book_tracker.domain.normalization import strip_html

revision = "0008_plain_text_descriptions"
down_revision = "0007_normalized_sort_projection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, metadata FROM items")).all()
    updates = []
    for identifier, metadata_json in rows:
        decoded = json.loads(metadata_json or "{}")
        if not isinstance(decoded, dict):
            continue
        description = decoded.get("description")
        if not isinstance(description, str) or "<" not in description:
            continue
        stripped = strip_html(description)
        if stripped == description:
            continue
        # An all-markup description would otherwise become an empty string, which
        # reads as "this book has a description and it is blank". Drop the key.
        if stripped:
            decoded["description"] = stripped
        else:
            decoded.pop("description")
        updates.append({"id": identifier, "metadata": json.dumps(decoded, ensure_ascii=False)})
    if updates:
        connection.execute(sa.text("UPDATE items SET metadata = :metadata WHERE id = :id"), updates)


def downgrade() -> None:
    """Stripped markup cannot be restored; the pre-migration backup is the way back."""
