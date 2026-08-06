"""meter chat and planning separately

daily_token_usage had one counter per founder per day, so every metered feature
shared a single ceiling. Chat and planning are different features -- a founder who
has spent their chat allowance must still be able to plan their day, and the
reverse -- which one counter cannot express.

Adds `source` to the primary key. A new day was already just a new key rather than
a reset (see usage.py); a new source is the same idea in the other axis.

Existing rows are backfilled to 'chat': everything metered before this point was
chat, since planning has never had a counter. The column is NOT NULL with a server
default so the backfill is exact rather than a guess, and so a writer that predates
this migration still lands somewhere valid instead of failing.

The value is deliberately a plain string, not a Postgres enum: adding a metered
feature should be a catalog change, not another migration and a type alteration.
It is constrained by the catalog's SOURCE_* constants and by the fact that
daily_limit_for() falls back to the chat ceiling for anything unrecognised -- a
source added without a limit is capped by something rather than by nothing.

Revision ID: b8e2d4f60a19
Revises: a7c3f9e21d84
Create Date: 2026-08-05 16:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b8e2d4f60a19'
down_revision: Union[str, Sequence[str], None] = 'a7c3f9e21d84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "daily_token_usage",
        sa.Column("source", sa.String(16), nullable=False, server_default="chat"),
    )
    # Widen the key rather than replace it: (founder_id, usage_date) stays a valid
    # prefix, so the existing lookup by founder+day is still index-served.
    op.drop_constraint("daily_token_usage_pkey", "daily_token_usage", type_="primary")
    op.create_primary_key(
        "daily_token_usage_pkey",
        "daily_token_usage",
        ["founder_id", "usage_date", "source"],
    )


def downgrade() -> None:
    # Collapsing the key would violate uniqueness for any founder-day that has
    # both a chat and a planning row, so fold them into one chat row first. The
    # total is preserved; only the per-feature split is lost, which is exactly
    # what the old shape could not represent anyway.
    # Materialise the totals BEFORE deleting anything -- reading the source table
    # after emptying it would insert nothing and silently discard every counter.
    op.execute("""
        CREATE TEMP TABLE _merged_usage ON COMMIT DROP AS
        SELECT founder_id, usage_date,
               SUM(tokens_used) AS tokens_used,
               MAX(updated_at)  AS updated_at
          FROM daily_token_usage
         GROUP BY founder_id, usage_date
    """)
    op.execute("DELETE FROM daily_token_usage")
    op.execute("""
        INSERT INTO daily_token_usage (founder_id, usage_date, source, tokens_used, updated_at)
        SELECT founder_id, usage_date, 'chat', tokens_used, updated_at
          FROM _merged_usage
    """)
    op.drop_constraint("daily_token_usage_pkey", "daily_token_usage", type_="primary")
    op.create_primary_key(
        "daily_token_usage_pkey",
        "daily_token_usage",
        ["founder_id", "usage_date"],
    )
    op.drop_column("daily_token_usage", "source")
