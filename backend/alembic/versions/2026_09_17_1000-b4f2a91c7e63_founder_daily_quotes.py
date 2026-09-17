"""founder daily quotes: the table, and the model routing for choosing them

Revision ID: b4f2a91c7e63
Revises: e9b4d72c5a18
Create Date: 2026-09-17 10:00:00

Two things a founder's daily lines need that code cannot carry: somewhere to
remember what they were shown (so a line does not come back next week), and a
routing row saying which model picks them.

THE ROUTING ROW IS THE FIRST NON-ANTHROPIC ONE in this table. Everything else
routes to Anthropic; this task goes to OpenAI's `gpt-5.4-nano`, because picking
one of forty pre-written lines is the cheapest kind of judgement there is and
does not need a frontier model. `OPENAI_API_KEY` must be set in the backend
environment or the task falls back to the deterministic pick -- which is a
plainer page, not a broken one, so a missing key is not an outage.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4f2a91c7e63"
down_revision: Union[str, Sequence[str], None] = "e9b4d72c5a18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TASK = "daily_quote_selection"


def upgrade() -> None:
    op.create_table(
        "founder_daily_quotes",
        sa.Column("founder_id", sa.Integer(), nullable=False),
        # The IST calendar date the pick belongs to -- not a timestamp. The
        # boundary is local (see plans/usage.py); storing an instant here would
        # invite somebody to compare it against UTC midnight and be 5.5 hours
        # wrong twice a day.
        sa.Column("quote_date", sa.Date(), nullable=False),
        sa.Column("surface", sa.String(length=20), nullable=False),
        # The catalogue id, not the text. The line lives in code and can be
        # corrected by editing one file; a copy of the text in every row would
        # mean a typo survives in production forever.
        sa.Column("quote_id", sa.String(length=64), nullable=False),
        # 'model' or 'fallback'. The cards look identical either way, so this
        # column is the only way to notice the provider has been failing.
        sa.Column("source", sa.String(length=20), nullable=False,
                  server_default=sa.text("'fallback'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["founder_id"], ["founders.founder_id"],
                                ondelete="CASCADE"),
        # One line per founder per day per page, enforced here rather than by
        # the job being careful: the job is not the only writer (a page load
        # fills its own gap) and they can race.
        sa.PrimaryKeyConstraint("founder_id", "quote_date", "surface"),
        sa.CheckConstraint("surface in ('compass', 'plan')",
                           name="founder_daily_quotes_surface_check"),
    )
    # The no-repeat lookup: this founder, the last fortnight. Without it that
    # query is a sequential scan on every page load for a founder with no row.
    op.create_index("ix_founder_daily_quotes_founder_date", "founder_daily_quotes",
                    ["founder_id", "quote_date"])
    # The prune's own predicate, which touches every founder rather than one.
    op.create_index("ix_founder_daily_quotes_date", "founder_daily_quotes",
                    ["quote_date"])

    op.execute(
        sa.text(
            "insert into model_task_routing (task, provider, model_id, is_active, notes) "
            "values (:task, 'openai', 'gpt-5.4-nano', true, "
            "        'Picks two pre-written lines per founder per night. Falls back "
            "to a deterministic pick when unavailable.') "
            "on conflict (task) do nothing"
        ).bindparams(task=_TASK)
    )


def downgrade() -> None:
    op.execute(
        sa.text("delete from model_task_routing where task = :task").bindparams(task=_TASK)
    )
    op.drop_index("ix_founder_daily_quotes_date", table_name="founder_daily_quotes")
    op.drop_index("ix_founder_daily_quotes_founder_date", table_name="founder_daily_quotes")
    op.drop_table("founder_daily_quotes")
