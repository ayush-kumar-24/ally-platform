"""add daily token usage and monthly free-call usage

Revision ID: b8c4d6f0a233
Revises: a7b3c5d9e011
Create Date: 2026-08-02 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8c4d6f0a233'
down_revision: Union[str, Sequence[str], None] = 'a7b3c5d9e011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Two period-keyed counters.

    Both are keyed by (founder, period) rather than being reset in place, so a new
    day or month is simply a new row. Nothing depends on a scheduled reset having
    run, and the history stays queryable -- "how many tokens did this founder use
    last Tuesday" has an answer.
    """
    op.create_table(
        "daily_token_usage",
        sa.Column("founder_id", sa.Integer(),
                  sa.ForeignKey("founders.founder_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("usage_date", sa.Date(), primary_key=True),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint("tokens_used >= 0", name="daily_token_usage_non_negative"),
    )
    op.create_index("ix_daily_token_usage_date", "daily_token_usage", ["usage_date"])

    op.create_table(
        "plan_call_usage",
        sa.Column("founder_id", sa.Integer(),
                  sa.ForeignKey("founders.founder_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("period", sa.String(length=7), primary_key=True),          # 'YYYY-MM'
        sa.Column("free_calls_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint("free_calls_used >= 0", name="plan_call_usage_non_negative"),
    )


def downgrade() -> None:
    op.drop_table("plan_call_usage")
    op.drop_index("ix_daily_token_usage_date", table_name="daily_token_usage")
    op.drop_table("daily_token_usage")
