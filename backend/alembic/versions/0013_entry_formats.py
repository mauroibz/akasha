"""How a copy is held, and the statuses a domain is allowed to have.

DEC-059. Ownership is neither a status nor a shelf. It hangs on the **entry**
because an album's `format` from MusicBrainz describes a *release* — that Kind of
Blue was pressed on 12" vinyl in 1959 — while your copy might be a reissue, a CD
or a stream. Items hold shared edition facts; entries hold what is true for you.

Multi-valued from the start, because owning a record on vinyl *and* digital is
ordinary (vinyl frequently ships with a download code) and turning one column
into many later is a migration nobody wants to run twice.

The value is stored rather than joined to a vocabulary table: unlike a shelf,
which the owner invents, the vocabulary is closed and declared on `Domain`. That
is exactly the boundary the owner drew — shelves are "work" and "fiction", and
formats are not that.
"""

import sqlalchemy as sa

from alembic import op

revision = "0013_entry_formats"
down_revision = "0012_creators"
branch_labels = None
depends_on = None


#: **Frozen, not read from the registry.** This migration used to import
#: `ALL_STATUSES`, so two installs running it a month apart could build different
#: constraints from the same revision — a migration is history and must not change
#: behaviour when the registry does. 0014 drops these constraints entirely
#: (DEC-067 row 1); the list is kept literal here so the revision still describes
#: what it actually did.
_STATUS_LIST = "'unsorted', 'read', 'reading', 'to_read', 'wishlist', 'dropped', 'pending', 'owned'"
_BOOK_STATUS_LIST = "'unsorted','read','reading','to_read','wishlist','dropped'"

TIMESTAMPS = (
    sa.Column("created_at", sa.Text(), nullable=False),
    sa.Column("updated_at", sa.Text(), nullable=False),
)


def _entries_table(status_list: str) -> sa.Table:
    """The `entries` table as it should be, for a batch rebuild.

    Spelled in full because `copy_from` skips reflection — and because SQLAlchemy does
    not reflect SQLite CHECK constraints at all, so a rebuild that relied on reflection
    would silently drop every one of them.
    """
    return sa.Table(
        "entries",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "item_id", sa.Integer(), sa.ForeignKey("items.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer()),
        sa.Column("notes", sa.Text()),
        sa.Column("date_added", sa.Text(), nullable=False),
        sa.Column("date_started", sa.Text()),
        sa.Column("date_finished", sa.Text()),
        sa.Column("reread_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score_provisional", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suggested_status", sa.Text()),
        *TIMESTAMPS,
        sa.UniqueConstraint("user_id", "item_id", name="uq_entries_user_item"),
        sa.CheckConstraint(f"status IN ({status_list})", name="ck_entries_status"),
        sa.CheckConstraint(
            f"suggested_status IS NULL OR suggested_status IN ({status_list})",
            name="ck_entries_suggested_status",
        ),
        sa.CheckConstraint("score IS NULL OR score BETWEEN 1 AND 10", name="ck_entries_score"),
        sa.CheckConstraint("reread_count >= 0", name="ck_entries_reread_count"),
        sa.CheckConstraint("score_provisional IN (0, 1)", name="ck_entries_score_provisional"),
        sa.Index("ix_entries_status", "user_id", "status"),
        sa.Index("ix_entries_score", "user_id", "score"),
        sa.Index("ix_entries_date_added", "user_id", "date_added"),
        sa.Index("ix_entries_user_status_date_id", "user_id", "status", "date_added", "id"),
        sa.Index("ix_entries_user_status_score_id", "user_id", "status", "score", "id"),
        sa.Index("ix_entries_user_finished_id", "user_id", "date_finished", "id"),
    )


def _rebuild_entries(status_list: str) -> None:
    with op.batch_alter_table("entries", copy_from=_entries_table(status_list), recreate="always"):
        pass


def upgrade() -> None:
    _rebuild_entries(_STATUS_LIST)
    op.create_table(
        "entry_formats",
        sa.Column(
            "entry_id",
            sa.Integer(),
            sa.ForeignKey("entries.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("format", sa.Text(), primary_key=True),
    )
    # The filter reads by format across the whole library, the way the shelf filter
    # reads by slug.
    op.create_index("ix_entry_formats_format", "entry_formats", ["format"])


def downgrade() -> None:
    op.drop_index("ix_entry_formats_format", table_name="entry_formats")
    op.drop_table("entry_formats")
    # Down is only safe for a library holding no album entry; an `owned` row would
    # fail the narrowed constraint, which is the correct outcome rather than a silent
    # remap into a status that means something else.
    _rebuild_entries(_BOOK_STATUS_LIST)
