"""Store the normalized title and first author so text sorts stop calling a UDF.

Sprint 017 measured what DEC-015 deferred. Ordering by `normalize_text(title)`
invokes an application-defined Python function once per candidate row: at 10,000
entries that is 73 ms idle and 312 ms with the job queue draining, against 39 ms
for an indexed column, and the text filter reached 988 ms — over the 500 ms budget
in technical-spec section 1.

The projection cannot be a SQLite generated column: generated columns may only
call built-in deterministic functions, and `normalize_text` is registered per
connection by the application. It is therefore an ordinary column maintained by a
mapper-level event in `infrastructure/models.py`.

The backfill computes values in Python with the domain function rather than
through the connection-level UDF, so this migration does not depend on the
application having registered anything. It does depend on `normalize_text`'s
behaviour as of this revision; changing that function later needs its own
migration to re-backfill, and `test_persistence.py` pins the equivalence.

No index accompanies the columns, and that is a measured choice rather than an
oversight. The list query drives from `entries` and reaches `items` by rowid, so
SQLite builds a temp B-tree for the ORDER BY either way — verified with and
without the null-bucket CASE. The win here is not an index seek; it is deleting
10,000 Python function calls per page.
"""

import json

import sqlalchemy as sa

from alembic import op
from book_tracker.domain.normalization import normalize_text

revision = "0007_normalized_sort_projection"
down_revision = "0006_job_error_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("items", sa.Column("title_normalized", sa.Text(), nullable=True))
    op.add_column("items", sa.Column("sort_author_normalized", sa.Text(), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, title, metadata FROM items")).all()
    updates = []
    for identifier, title, metadata_json in rows:
        # The generated `sort_author` column already forces `metadata` to be
        # valid JSON, but not to be an object with a list of authors.
        decoded = json.loads(metadata_json or "{}")
        authors = decoded.get("authors") if isinstance(decoded, dict) else None
        authors = authors if isinstance(authors, list) else []
        author = authors[0] if authors and isinstance(authors[0], str) else None
        updates.append(
            {
                "id": identifier,
                "title_normalized": normalize_text(title or ""),
                "sort_author_normalized": normalize_text(author) if author else None,
            }
        )
    if updates:
        connection.execute(
            sa.text(
                "UPDATE items SET title_normalized = :title_normalized,"
                " sort_author_normalized = :sort_author_normalized WHERE id = :id"
            ),
            updates,
        )


def downgrade() -> None:
    op.drop_column("items", "sort_author_normalized")
    op.drop_column("items", "title_normalized")
