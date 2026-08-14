"""Attached files, addressed by the digest of their contents.

DEC-048. The blob lives at `attachments/{sha256[:2]}/{sha256}` on disk and this
table holds everything else: which item it hangs on, what the owner called it,
and how big it is. The filename is metadata precisely so it never becomes a path
component.

`sha256` is indexed because deletion is refcounted — removing a row asks how many
other rows still point at the same digest before the blob goes. The unique
constraint on (item_id, sha256) makes attaching the same file to the same item
twice a no-op rather than a duplicate row; attaching it to a *different* item is
allowed and costs no additional disk.
"""

import sqlalchemy as sa

from alembic import op

revision = "0010_attachments"
down_revision = "0009_provider_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.UniqueConstraint("item_id", "sha256", name="uq_attachments_item_sha256"),
    )
    op.create_index("ix_attachments_item_id", "attachments", ["item_id"])
    op.create_index("ix_attachments_sha256", "attachments", ["sha256"])


def downgrade() -> None:
    op.drop_index("ix_attachments_sha256", table_name="attachments")
    op.drop_index("ix_attachments_item_id", table_name="attachments")
    op.drop_table("attachments")
