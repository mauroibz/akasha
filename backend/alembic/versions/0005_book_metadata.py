"""Normalize legacy book publisher metadata."""

from alembic import op

revision = "0005_book_metadata"
down_revision = "0004_import_planning_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE items
        SET metadata = json_remove(
            CASE
              WHEN json_type(metadata, '$.publisher') IS NULL
                   AND json_type(metadata, '$.publishers') = 'array'
                   AND json_array_length(metadata, '$.publishers') > 0
              THEN json_set(metadata, '$.publisher', json_extract(metadata, '$.publishers[0]'))
              ELSE metadata
            END,
            '$.publishers'
        )
        WHERE json_type(metadata, '$.publishers') IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE items
        SET metadata = json_set(
            metadata,
            '$.publishers',
            json_array(json_extract(metadata, '$.publisher'))
        )
        WHERE json_type(metadata, '$.publisher') = 'text'
          AND json_type(metadata, '$.publishers') IS NULL
        """
    )
