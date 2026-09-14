"""Import proposals: what the background search found, offered per row.

A proposal is one provider result for one record of a previewed batch — the
thing the owner confirms or discards before commit (Sprint 083 D2). Several may
exist per record (the merged top-N), ranked by the order the domain's merge
produced; `chosen` is the owner's answer, NULL before anyone has answered,
`true` for the one picked, `false` for every proposal a discard cleared.

`user_id` scopes the rows like every other import row, and `rank` is a small
integer rather than a confidence float: `merge_and_rank`'s output is an order,
and pretending it measured confidence would be the connector guessing — the
thing this sprint exists to stop.
"""

import sqlalchemy as sa

from alembic import op

revision = "0022_import_proposals"
down_revision = "0021_session_acting_user"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "batch_id",
            sa.Text(),
            sa.ForeignKey("import_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "record_id",
            sa.Integer(),
            sa.ForeignKey("import_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        # NULL = not answered; 1 = chosen; 0 = cleared by a discard
        sa.Column("chosen", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "chosen IN (0, 1)", name="ck_import_proposals_chosen_boolean"
        ),
        sa.CheckConstraint("rank >= 0", name="ck_import_proposals_rank_nonnegative"),
        sa.UniqueConstraint(
            "record_id", "source", "source_id", name="uq_import_proposals_identity"
        ),
    )
    op.create_index("ix_import_proposals_batch_record", "import_proposals",
                    ["batch_id", "record_id"])
    op.create_index("ix_import_proposals_user", "import_proposals", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_import_proposals_user", table_name="import_proposals")
    op.drop_index("ix_import_proposals_batch_record", table_name="import_proposals")
    op.drop_table("import_proposals")
