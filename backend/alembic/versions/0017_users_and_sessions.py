"""The schema learns there is a person on the other side of it.

Sprint 075 (DEC-146): `entries.user_id` and `shelves.user_id` have pointed at the
number 1 since migration `0002` without anything existing for that number to mean.
This revision creates what it means — a `users` table and the session store its
login will fill in Sprint 077 — and seeds exactly one row into it: the first user,
`id = 1`, the owner of every row that already said `user_id = 1` by implication.

Nothing else moves. The library tables are untouched here; the foreign keys land in
the next revision (SQLite cannot attach a constraint in place). This migration is
the one that turns "1" from a convention into a reference.

Shapes are the proposal's §2.2, frozen here rather than read from anything live:

- `username` is stored normalized — stripped and case-folded — and unique on that
  stored form. Sprint 079 creates a second user, and uniqueness decided after the
  fact would be a data migration; decided now it is a column definition. The typed
  form rides along as `display_name` when it differs; the seed has no typed form
  yet, so its `display_name` is NULL until the setup screen in Sprint 077 asks.
- Credentials are nullable on purpose. The seeded user has no password: this
  sprint is forbidden authentication, and the setup screen that Sprint 077 adds is
  what gives the first user one. A `NOT NULL` password column would have had to
  invent a credential nobody chose.
- `is_admin` is an integer, not a boolean column, because SQLite has no boolean
  type and the project's other flags (`score_provisional`) are spelled this way.
- Sessions store only the token's hash — a session row is the revocation mechanism,
  and a revocation mechanism that holds the credential it revokes is a worse one.
  `ON DELETE CASCADE` because a deleted user taking its sessions with it is the
  only safe direction for a credential table; a RESTRICT here would refuse the
  delete instead of cleaning up after it. The product decision about what deleting
  a user means at all belongs to Sprint 079; the constraint states what it would
  do if asked.
- `last_seen_at` is NOT NULL: a session is touched into existence with its first
  sighting already known, and an untouched session is one that expired unseen —
  a state the sweep wants to answer without a NULL check.

The seed row's username is a placeholder the owner will meet and may rename when
Sprint 077's setup screen asks for the real one. It is a data decision made here
because the revision cannot create a row with no name in the only column that is
an identity.
"""

from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision = "0017_users_and_sessions"
down_revision = "0016_import_kind_is_the_registrys"
branch_labels = None
depends_on = None

#: Placeholder identity for the seeded first user. Sprint 077's setup screen is
#: where the owner chooses the real one; until then the migration needs *some*
#: normalized-by-construction value in the one identity column it has. `owner`
#: landed with the sprint and the owner renamed it to `admin` on close day,
#: taking the in-place revision DEC-147 priced (still cheap before Sprint 078).
_SEED_USERNAME = "admin"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        # Stored normalized: stripped and case-folded. Uniqueness belongs to the
        # stored form, so two typographic variants of one name are one user.
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("password_salt", sa.Text(), nullable=True),
        sa.Column("is_admin", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_table(
        "sessions",
        # Opaque: a uuid chosen by the code that creates the row, never a sequence.
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("last_seen_at", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Text(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
    )
    # The lookup (session check on every request) rides the unique constraint's
    # index; the sweep (which of this user's sessions expired?) wants the pair.
    # Not unique: a user holds many live sessions.
    op.create_index("ix_sessions_user_expires", "sessions", ["user_id", "expires_at"])

    # Exactly one row: the user every existing `user_id = 1` already belonged to by
    # convention. Admin because the plan's first user is the owner; credential-less
    # because Sprint 077, not a migration, decides what a password is.
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    op.bulk_insert(
        sa.table(
            "users",
            sa.column("id", sa.Integer()),
            sa.column("username", sa.Text()),
            sa.column("display_name", sa.Text()),
            sa.column("password_hash", sa.Text()),
            sa.column("password_salt", sa.Text()),
            sa.column("is_admin", sa.Integer()),
            sa.column("created_at", sa.Text()),
            sa.column("updated_at", sa.Text()),
        ),
        [
            {
                "id": 1,
                "username": _SEED_USERNAME,
                "display_name": None,
                "password_hash": None,
                "password_salt": None,
                "is_admin": 1,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    # Sessions first: they reference `users`, and while migration connections
    # deliberately do not enforce foreign keys (DEC-092), order is still how a
    # downgrade says what it means.
    op.drop_index("ix_sessions_user_expires", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
