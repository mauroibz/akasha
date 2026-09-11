"""Let two users import the same source without sharing a ledger batch.

The fingerprint is idempotency within one library, not across the install.
Sprint 075 added the owner after the original unique constraint already
existed; Sprint 079 is the first point where its missing leading column can
change behavior.
"""

from alembic import op

revision = "0020_user_scoped_import_fingerprints"
down_revision = "0019_ownership_on_the_import_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("import_batches", recreate="always") as batch:
        batch.drop_constraint("uq_import_batch_input", type_="unique")
        batch.create_unique_constraint(
            "uq_import_batch_user_input", ["user_id", "kind", "fingerprint"]
        )


def downgrade() -> None:
    with op.batch_alter_table("import_batches", recreate="always") as batch:
        batch.drop_constraint("uq_import_batch_user_input", type_="unique")
        batch.create_unique_constraint("uq_import_batch_input", ["kind", "fingerprint"])
