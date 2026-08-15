"""The status vocabulary belongs to the domain, not to the schema.

DEC-067 row 1. `ck_entries_status` was rendered from `ALL_STATUSES` **when its
migration was written**, which made it a frozen snapshot rather than a live rule.
The consequence was the worst possible split: a domain declaring a status books
and albums lack passed `validate_status` and was then refused by SQLite, so
adding a domain meant a migration on the shared `entries` table — and two domain
teams working in parallel would both write one, both pointing `down_revision` at
the same head. That is the one class of conflict two diffs side by side cannot
resolve (DEC-068).

**What replaces it is not nothing.** `validate_status` is keyed on the item's own
domain and is strictly stronger than the CHECK ever was: the constraint accepted
`owned` on a book, because it could only hold the union of every domain's values.
The application is the only writer — every path goes through `LibraryService` or
the repositories — so the rule is enforced where the domain is actually known.

The other constraints stay: score, `reread_count` and `score_provisional` are
neutral facts about an entry that no domain gets to redefine.
"""

import sqlalchemy as sa

from alembic import op
from book_tracker.domain.domains import ALL_STATUSES

revision = "0014_status_is_the_domains"
down_revision = "0013_entry_formats"
branch_labels = None
depends_on = None

#: Only for the downgrade, and only from the registry as it stands when the
#: downgrade runs — the same frozen-snapshot problem, which is precisely why up is
#: the direction that removes it.
_STATUS_LIST = ", ".join(f"'{value}'" for value in ALL_STATUSES)

TIMESTAMPS = (
    sa.Column("created_at", sa.Text(), nullable=False),
    sa.Column("updated_at", sa.Text(), nullable=False),
)


def _entries_table(*status_checks: sa.CheckConstraint) -> sa.Table:
    """The `entries` table as it should be, for a batch rebuild.

    Spelled in full because `copy_from` skips reflection — and because SQLAlchemy does
    not reflect SQLite CHECK constraints at all, so a rebuild that relied on reflection
    would silently drop every one of them, including the three that stay.
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
        *status_checks,
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


def upgrade() -> None:
    with op.batch_alter_table("entries", copy_from=_entries_table(), recreate="always"):
        pass


def downgrade() -> None:
    """Restore the snapshot, which is only safe for a library holding no later domain.

    A row whose status no registered domain declared when this ran would fail the
    restored constraint — the correct outcome rather than a silent remap into a status
    that means something else.
    """
    checks = (
        sa.CheckConstraint(f"status IN ({_STATUS_LIST})", name="ck_entries_status"),
        sa.CheckConstraint(
            f"suggested_status IS NULL OR suggested_status IN ({_STATUS_LIST})",
            name="ck_entries_suggested_status",
        ),
    )
    with op.batch_alter_table("entries", copy_from=_entries_table(*checks), recreate="always"):
        pass
