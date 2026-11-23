"""Suggestions and the rounds that chose them (Sprint 133, DEC-183 points 4-7).

A round is one request to one recommendation source for one person, about one entry
(More like this) or about their taste (no seed). Its candidates are stored before any
provider is asked about them; `enrichment` says whether the domain has found one yet,
and `answer` what the person said. The vocabularies (`status`, `enrichment`, `answer`,
`source`) are the application's, validated where they are written and never frozen
in the schema (Sprints 028 and 041).
"""

import sqlalchemy as sa

from alembic import op

revision = "0037_suggestions"
down_revision = "0036_home_layouts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suggestion_rounds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_type", sa.Text(), nullable=False),
        # A deleted seed leaves its round and suggestions behind, unseeded: what was
        # suggested and answered is still the person's.
        sa.Column(
            "seed_entry_id",
            sa.Integer(),
            sa.ForeignKey("entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("finished_at", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_suggestion_rounds_seed",
        "suggestion_rounds",
        ["user_id", "seed_entry_id", "source", "created_at"],
    )
    op.create_table(
        "suggestions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "round_id",
            sa.Integer(),
            sa.ForeignKey("suggestion_rounds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("creator", sa.Text(), nullable=True),
        sa.Column("external_ids_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_score", sa.Float(), nullable=True),
        sa.Column("display_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("enrichment", sa.Text(), nullable=False, server_default="pending"),
        # The shared item the domain resolved it to. An item pruned from the cache
        # takes the link with it, not the suggestion.
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("answered_at", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_suggestions_user_type_created",
        "suggestions",
        ["user_id", "item_type", "created_at"],
    )
    op.create_index("ix_suggestions_round", "suggestions", ["round_id"])
    op.create_index("ix_suggestions_item", "suggestions", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_suggestions_item", table_name="suggestions")
    op.drop_index("ix_suggestions_round", table_name="suggestions")
    op.drop_index("ix_suggestions_user_type_created", table_name="suggestions")
    op.drop_table("suggestions")
    op.drop_index("ix_suggestion_rounds_seed", table_name="suggestion_rounds")
    op.drop_table("suggestion_rounds")
