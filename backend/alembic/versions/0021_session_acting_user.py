"""Keep an admin's visible acting identity on the server-side session.

The cookie continues to carry only an opaque token. Deleting the target user
ends the mode at the schema boundary, so a stale browser can never point at a
user that no longer exists.
"""

import sqlalchemy as sa

from alembic import op

revision = "0021_session_acting_user"
down_revision = "0020_user_scoped_import_fingerprints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sessions", recreate="always") as batch:
        batch.add_column(sa.Column("acting_as_user_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_sessions_acting_as_user",
            "users",
            ["acting_as_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_sessions_acting_as", ["acting_as_user_id"])


def downgrade() -> None:
    with op.batch_alter_table("sessions", recreate="always") as batch:
        batch.drop_index("ix_sessions_acting_as")
        batch.drop_constraint("fk_sessions_acting_as_user", type_="foreignkey")
        batch.drop_column("acting_as_user_id")
