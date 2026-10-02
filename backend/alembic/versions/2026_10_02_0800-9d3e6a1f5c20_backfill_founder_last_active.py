"""Backfill founders.last_active_at from activity already on record.

Revision ID: 9d3e6a1f5c20
Revises: b48e5c12d709
Create Date: 2026-10-02 08:00:00

WHY. `record_last_active` has existed since 2026-09-22, but in production it
never wrote anything: it ran before the founder's RLS context was bound, so
under `ally_app` the `founders` UPDATE matched zero rows (fixed in #238). Every
founder's `last_active_at` was therefore NULL until that fix deployed, and the
admin dashboard's "Active today" / "Active last 7 days" -- and the lists behind
them -- counted only people seen since.

The activity itself was recorded all along, in the tables below. This sets
each founder's `last_active_at` to their most recent real activity from them.

WHAT COUNTS. Only rows a founder's own action writes:
  * messages        -- role = 'user' (what they typed, not the replies)
  * answers         -- answered_at
  * sessions        -- started_at (a diagnosis they began)
  * conversations   -- created_at (a chat they opened)
  * credit_transactions -- type = 'consume' (a charged chat turn)

Deliberately NOT: any `updated_at` (background jobs and locks touch those),
credit `expire`/`renew` rows (written when an admin merely views a ledger),
llm_call_log (scheduled jobs call the model too), founder_reports (the
reconciliation sweep generates them). Each of those would mark a founder
active when they were not.

SAFE TO RE-RUN. It only ever moves a timestamp forward, never back, and never
past now(). A source table or column missing on this target is skipped.

DOWNGRADE is a no-op: the values replaced were NULL or older than real
activity, and putting the wrong answer back serves nothing.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9d3e6a1f5c20"
down_revision: Union[str, Sequence[str], None] = "b48e5c12d709"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: (table, founder column, timestamp column, extra WHERE or None)
_SOURCES = (
    ("messages", "founder_id", "created_at", "role = 'user'"),
    ("answers", "founder_id", "answered_at", None),
    ("sessions", "founder_id", "started_at", None),
    ("conversations", "founder_id", "created_at", None),
    ("credit_transactions", "user_id", "created_at", "type = 'consume'"),
)


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_columns(table: str, *columns: str) -> bool:
    if not _has_table(table):
        return False
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
    return all(c in cols for c in columns)


def upgrade() -> None:
    if not _has_columns("founders", "founder_id", "last_active_at"):
        return
    bind = op.get_bind()
    # Cross-founder by nature. The migration role owns these tables so RLS
    # does not apply to it, but say so explicitly in case it ever runs as a
    # role that RLS does bind.
    bind.execute(sa.text("SELECT set_config('app.current_admin', 'true', true)"))

    for table, fcol, tcol, where in _SOURCES:
        needed = [fcol, tcol] + (["role"] if table == "messages" else []) \
            + (["type"] if table == "credit_transactions" else [])
        if not _has_columns(table, *needed):
            continue
        extra = f"AND {where}" if where else ""
        # Identifiers come from the constant above, never from input.
        bind.execute(sa.text(f"""
            UPDATE founders f
               SET last_active_at = s.at
              FROM (SELECT {fcol} AS founder_id, max({tcol}) AS at
                      FROM {table}
                     WHERE {tcol} IS NOT NULL
                       AND {tcol} <= now()
                       {extra}
                     GROUP BY {fcol}) s
             WHERE s.founder_id = f.founder_id
               AND (f.last_active_at IS NULL OR f.last_active_at < s.at)
        """))


def downgrade() -> None:
    pass
