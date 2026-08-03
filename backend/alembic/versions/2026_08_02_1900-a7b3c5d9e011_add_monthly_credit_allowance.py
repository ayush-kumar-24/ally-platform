"""add founders.monthly_credit_allowance (what a renewal re-grants)

Revision ID: a7b3c5d9e011
Revises: f6a2b04d7e53
Create Date: 2026-08-02 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7b3c5d9e011'
down_revision: Union[str, Sequence[str], None] = 'f6a2b04d7e53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """The one column the expiry engine needs that nothing stored yet.

    `CreditState.monthly_allowance` is what a renewal re-grants. It has to be
    persisted rather than derived from the plan: a founder's allowance can be varied
    individually (a negotiated deal, a goodwill uplift), and deriving it from
    `plan_type` would silently overwrite that on the next renewal.

    Additive and defaulted to 0, so existing rows keep working unchanged: an
    allowance of 0 means renewals grant nothing, which is exactly the behaviour of
    every account today. No existing column, constraint or query is altered.
    """
    op.add_column(
        "founders",
        sa.Column("monthly_credit_allowance", sa.Integer(), nullable=False,
                  server_default="0"),
    )
    op.create_check_constraint(
        "founders_allowance_non_negative", "founders", "monthly_credit_allowance >= 0")


def downgrade() -> None:
    op.drop_constraint("founders_allowance_non_negative", "founders", type_="check")
    op.drop_column("founders", "monthly_credit_allowance")
