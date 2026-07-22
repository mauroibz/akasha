"""Create the complete v1 domain schema."""

import sqlalchemy as sa

from alembic import op

revision = "0002_domain_schema"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None

TIMESTAMPS = (
    sa.Column("created_at", sa.Text(), nullable=False),
    sa.Column("updated_at", sa.Text(), nullable=False),
)


def upgrade() -> None:
    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type", sa.Text(), nullable=False, server_default="book"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("subtitle", sa.Text()),
        sa.Column("year", sa.Integer()),
        sa.Column("cover_path", sa.Text()),
        sa.Column("identifiers", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("metadata", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("sort_author", sa.Text(), sa.Computed("json_extract(metadata, '$.authors[0]')")),
        *TIMESTAMPS,
        sa.CheckConstraint("json_valid(identifiers)", name="ck_items_identifiers_json"),
        sa.CheckConstraint("json_valid(metadata)", name="ck_items_metadata_json"),
    )
    op.create_index("ix_items_title", "items", [sa.text("title COLLATE NOCASE")])
    op.create_table(
        "item_identifiers",
        sa.Column(
            "item_id", sa.Integer(), sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("normalized_value", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        *TIMESTAMPS,
        sa.PrimaryKeyConstraint("item_id", "kind", "normalized_value"),
        sa.UniqueConstraint("kind", "normalized_value", name="uq_item_identifier_identity"),
    )
    op.create_table(
        "item_sources",
        sa.Column(
            "item_id", sa.Integer(), sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("is_primary", sa.Integer(), nullable=False, server_default="0"),
        *TIMESTAMPS,
        sa.PrimaryKeyConstraint("source", "source_id"),
        sa.UniqueConstraint("item_id", "source", name="uq_item_source_per_provider"),
        sa.CheckConstraint("is_primary IN (0, 1)", name="ck_item_sources_primary_boolean"),
    )
    op.create_index(
        "uq_item_sources_one_primary",
        "item_sources",
        ["item_id"],
        unique=True,
        sqlite_where=sa.text("is_primary = 1"),
    )
    op.create_table(
        "entries",
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
        sa.CheckConstraint(
            "status IN ('unsorted','read','reading','to_read','wishlist','dropped')",
            name="ck_entries_status",
        ),
        sa.CheckConstraint(
            "suggested_status IS NULL OR suggested_status IN "
            "('unsorted','read','reading','to_read','wishlist','dropped')",
            name="ck_entries_suggested_status",
        ),
        sa.CheckConstraint("score IS NULL OR score BETWEEN 1 AND 10", name="ck_entries_score"),
        sa.CheckConstraint("reread_count >= 0", name="ck_entries_reread_count"),
        sa.CheckConstraint("score_provisional IN (0, 1)", name="ck_entries_score_provisional"),
    )
    op.create_index("ix_entries_status", "entries", ["user_id", "status"])
    op.create_index("ix_entries_score", "entries", ["user_id", "score"])
    op.create_index("ix_entries_date_added", "entries", ["user_id", "date_added"])
    op.create_table(
        "shelves",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        *TIMESTAMPS,
        sa.UniqueConstraint("user_id", "slug", name="uq_shelves_user_slug"),
    )
    op.create_table(
        "entry_shelves",
        sa.Column(
            "entry_id",
            sa.Integer(),
            sa.ForeignKey("entries.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "shelf_id",
            sa.Integer(),
            sa.ForeignKey("shelves.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("source_descriptor", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("preview_summary", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("counters", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("error", sa.Text()),
        sa.Column("committed_at", sa.Text()),
        sa.Column("undo_expires_at", sa.Text()),
        *TIMESTAMPS,
        sa.UniqueConstraint("kind", "fingerprint", name="uq_import_batch_input"),
        sa.CheckConstraint("kind IN ('goodreads','calibre')", name="ck_import_batches_kind"),
    )
    op.create_table(
        "import_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "batch_id",
            sa.Text(),
            sa.ForeignKey("import_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("normalized_payload", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("matched_item_id", sa.Integer(), sa.ForeignKey("items.id", ondelete="SET NULL")),
        sa.Column(
            "matched_entry_id", sa.Integer(), sa.ForeignKey("entries.id", ondelete="SET NULL")
        ),
        sa.Column("match_kind", sa.Text()),
        sa.Column("planned_action", sa.Text()),
        sa.Column("conflicts", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("validation_errors", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("ambiguity_resolution", sa.Text()),
        *TIMESTAMPS,
        sa.UniqueConstraint("batch_id", "row_number", name="uq_import_record_row"),
    )
    op.create_table(
        "import_effects",
        sa.Column("effect_id", sa.Integer(), primary_key=True),
        sa.Column(
            "batch_id",
            sa.Text(),
            sa.ForeignKey("import_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "record_id",
            sa.Integer(),
            sa.ForeignKey("import_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("effect_type", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("before_values", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("after_values", sa.Text(), nullable=False, server_default="{}"),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("batch_id", sa.Text(), sa.ForeignKey("import_batches.id", ondelete="SET NULL")),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("progress", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("error", sa.Text()),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.Text(), nullable=False),
        sa.Column("heartbeat_at", sa.Text()),
        sa.Column("lease_expires_at", sa.Text()),
        sa.Column("finished_at", sa.Text()),
        *TIMESTAMPS,
        sa.CheckConstraint(
            "state IN ('queued','running','succeeded','failed','cancelled')", name="ck_jobs_state"
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_jobs_attempts"),
    )
    op.create_index("ix_jobs_claim", "jobs", ["state", "available_at"])


def downgrade() -> None:
    for table in (
        "jobs",
        "import_effects",
        "import_records",
        "import_batches",
        "entry_shelves",
        "shelves",
        "entries",
        "item_sources",
        "item_identifiers",
        "items",
    ):
        op.drop_table(table)
