"""A vector of each item's stored text (Sprint 136, DEC-183 point 7, DEC-187).

One row per item: the vector a hosted embedding endpoint gave for the item's text
(title, creator, year and the domain's declared descriptive fields), packed as
little-endian float32 and scaled to unit length, so cosine similarity is a dot
product. `model` names the endpoint, model and size it came from; vectors of two
models are never compared. `text_hash` is the SHA-256 of the text embedded: a
changed text, or a changed model, is embedded again. Items are shared, so a vector
is too; nothing about a person is in it. Deleting an item deletes its vector.
"""

import sqlalchemy as sa

from alembic import op

revision = "0038_item_embeddings"
down_revision = "0037_suggestions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "item_embeddings",
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("dims", sa.Integer(), nullable=False),
        sa.Column("vector", sa.LargeBinary(), nullable=False),
        sa.Column("text_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("item_embeddings")
