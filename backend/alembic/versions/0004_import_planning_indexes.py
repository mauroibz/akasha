"""Add indexes for durable import planning and ordered effect replay."""

from alembic import op

revision = "0004_import_planning_indexes"
down_revision = "0003_list_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_import_records_batch_action",
        "import_records",
        ["batch_id", "planned_action", "row_number"],
    )
    op.create_index(
        "ix_import_effects_batch_effect",
        "import_effects",
        ["batch_id", "effect_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_import_effects_batch_effect", table_name="import_effects")
    op.drop_index("ix_import_records_batch_action", table_name="import_records")
