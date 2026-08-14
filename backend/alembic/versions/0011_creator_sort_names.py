"""Store the name a creator sorts under, seeded by a heuristic and correctable.

`sort_author` is `json_extract(metadata, '$.authors[0]')` verbatim, so the library
filed "Gabriel García Márquez" under G and "Adolfo Bioy Casares" under A. For a
Spanish-language library that made the author sort unusable.

There is no heuristic that fixes it. Splitting on the last space yields *Márquez*
and *Llosa*, both wrong, and *Rulfo*, right — Spanish double surnames carry no
reliable signal. So the sort name is stored rather than computed on read, seeded by
`creator_sort_name` and overridable by the owner. `creator_sort_override` is the
only column here that is not derived; the Calibre import writes it from that
database's curated `authors.sort`, and the detail page writes it from the edit
dialog.

Backfilled in Python with the domain functions rather than through a
connection-level UDF, exactly as `0007` does, so this migration depends on nothing
the application registers. It therefore pins `creator_sort_name`'s behaviour as of
this revision: changing that function later needs its own migration to re-backfill.

No index, for the reason DEC-036 recorded and measured: the list query drives from
`entries` and reaches `items` by rowid, so SQLite builds a temp B-tree for the
ORDER BY either way. The win was never a seek — it was not calling a Python
function once per candidate row.
"""

import json

import sqlalchemy as sa

from alembic import op
from book_tracker.domain.normalization import creator_sort_name, normalize_text

revision = "0011_creator_sort_names"
down_revision = "0010_attachments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("items", sa.Column("creator_sort_override", sa.Text(), nullable=True))
    op.add_column("items", sa.Column("creator_sort", sa.Text(), nullable=True))
    op.add_column("items", sa.Column("creator_sort_normalized", sa.Text(), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, metadata FROM items")).all()
    updates = []
    for identifier, metadata_json in rows:
        # `metadata` is guaranteed to be valid JSON by the generated column, but
        # not to be an object carrying a list of authors.
        decoded = json.loads(metadata_json or "{}")
        authors = decoded.get("authors") if isinstance(decoded, dict) else None
        authors = authors if isinstance(authors, list) else []
        author = authors[0] if authors and isinstance(authors[0], str) else None
        sort_name = creator_sort_name(author) if author else ""
        updates.append(
            {
                "id": identifier,
                "creator_sort": sort_name or None,
                "creator_sort_normalized": normalize_text(sort_name) if sort_name else None,
            }
        )
    if updates:
        connection.execute(
            sa.text(
                "UPDATE items SET creator_sort = :creator_sort,"
                " creator_sort_normalized = :creator_sort_normalized WHERE id = :id"
            ),
            updates,
        )


def downgrade() -> None:
    op.drop_column("items", "creator_sort_normalized")
    op.drop_column("items", "creator_sort")
    op.drop_column("items", "creator_sort_override")
