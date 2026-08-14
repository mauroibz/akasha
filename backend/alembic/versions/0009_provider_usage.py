"""Count provider requests per day, so a metered provider can be guarded.

DEC-045. Google Books allows roughly 1,000 requests a day and DEC-044 measured a
5,000-book import needing about 1,333 of them, so a single large import exhausts
the free tier and silently loses enrichment on the remainder.

Nothing in this table names a provider. Google Books is the only metered one
today, but the roadmap adds MusicBrainz, IGDB and TMDB, and the owner asked for
this to be built provider-agnostic so a new one is a configuration entry rather
than a patch. Limits live in `Settings.provider_daily_limits`; this table only
records what was spent.

`day` is a UTC date string. Google resets on Pacific time, so the default limit
sits deliberately below the real one rather than the boundary being made exact.
"""

import sqlalchemy as sa

from alembic import op

revision = "0009_provider_usage"
down_revision = "0008_plain_text_descriptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_usage",
        sa.Column("provider", sa.Text(), primary_key=True),
        sa.Column("day", sa.Text(), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("provider_usage")
