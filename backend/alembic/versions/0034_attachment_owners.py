"""Whose file an attachment is (Sprint 128, DEC-180 §2, finding F5).

Items are a shared cache (DEC-151): two people who add the same ISBN hold one
item row. `attachments` hung off the item alone, so the second person listed,
downloaded, renamed and deleted the first one's private files. An attachment is
the owner's act, not the cache's, so it now carries `user_id`.

**Backfill, in order of evidence.** An existing row is given

1. the user whose import ledger says it attached the file (`import_effects`
   with `entity_type = 'attachment'` naming the row), else
2. the one user who holds an entry on its item, when exactly one does, else
3. the seeded user 1 — the only user any pre-multi-user install had, and the
   admin who can still see and reassign it on a shared item.

**Shape.** `user_id` is `NOT NULL`, references `users` `ON DELETE CASCADE` (a
person's files go with the person; the blob store is refcounted by digest and
`reclaim` collects a blob nothing references any more), and the uniqueness that
made attaching the same bytes to the same item twice a no-op becomes per person:
`(user_id, item_id, sha256)`. Its index leads with `user_id`, which is the scope
every query now carries. The blob itself stays global and shared by digest.

**Why a hand-built rebuild.** SQLite cannot add a foreign key or change a unique
constraint in place. The table is rebuilt the way every earlier revision that did
this rebuilt one, but spelled out explicitly: create the new shape, copy with the
backfill expression in the SELECT, drop, rename, re-create the two indexes. Nothing
references `attachments`, and `alembic/env.py` never enables the foreign-key pragma
during migrations (DEC-092), so the drop cascades nowhere.
"""

import sqlalchemy as sa

from alembic import op

revision = "0034_attachment_owners"
down_revision = "0033_unknown_fields"
branch_labels = None
depends_on = None

_OWNER = """
COALESCE(
    (SELECT effect.user_id FROM import_effects effect
      WHERE effect.entity_type = 'attachment'
        AND effect.entity_id = CAST(a.id AS TEXT)
      ORDER BY effect.effect_id LIMIT 1),
    (SELECT MIN(entry.user_id) FROM entries entry
      WHERE entry.item_id = a.item_id
     HAVING COUNT(DISTINCT entry.user_id) = 1),
    1
)
"""


def _create(name: str, *, owned: bool) -> None:
    columns: list[sa.Column] = [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("items.id", ondelete="CASCADE"),
            nullable=False,
        ),
    ]
    if owned:
        columns.append(
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            )
        )
    columns += [
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    ]
    unique = (
        sa.UniqueConstraint("user_id", "item_id", "sha256", name="uq_attachments_user_item_sha256")
        if owned
        else sa.UniqueConstraint("item_id", "sha256", name="uq_attachments_item_sha256")
    )
    op.create_table(name, *columns, unique)


def _swap(new: str) -> None:
    op.drop_index("ix_attachments_sha256", table_name="attachments")
    op.drop_index("ix_attachments_item_id", table_name="attachments")
    op.drop_table("attachments")
    op.rename_table(new, "attachments")
    op.create_index("ix_attachments_item_id", "attachments", ["item_id"])
    op.create_index("ix_attachments_sha256", "attachments", ["sha256"])


def upgrade() -> None:
    _create("_attachments_owned", owned=True)
    op.execute(
        sa.text(
            "INSERT INTO _attachments_owned "
            "(id, item_id, user_id, filename, byte_size, sha256, created_at, updated_at) "
            f"SELECT a.id, a.item_id, {_OWNER}, a.filename, a.byte_size, a.sha256, "
            "a.created_at, a.updated_at FROM attachments a"
        )
    )
    _swap("_attachments_owned")


def downgrade() -> None:
    """Ownership is dropped; where two people held the same file on one item, the
    earlier row survives, because the old key allowed only one. The blob is shared
    by digest, so no file is lost — only the second person's name for it."""
    _create("_attachments_shared", owned=False)
    op.execute(
        sa.text(
            "INSERT OR IGNORE INTO _attachments_shared "
            "(id, item_id, filename, byte_size, sha256, created_at, updated_at) "
            "SELECT id, item_id, filename, byte_size, sha256, created_at, updated_at "
            "FROM attachments ORDER BY id"
        )
    )
    _swap("_attachments_shared")
