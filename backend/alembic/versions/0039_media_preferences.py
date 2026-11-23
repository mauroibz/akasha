"""Your media, one list per person (Sprint 143, DEC-193).

The order of a person's media and whether each is in front, kept or off, as one JSON
list. Which media exist is the registry's to say, so the item types are validated
where the list is written and read leniently, never frozen in the schema: a medium the
application no longer registers is ignored on read, and one registered later is
appended.
"""

import sqlalchemy as sa

from alembic import op

revision = "0039_media_preferences"
down_revision = "0038_item_embeddings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_preferences",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("media_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("media_preferences")
