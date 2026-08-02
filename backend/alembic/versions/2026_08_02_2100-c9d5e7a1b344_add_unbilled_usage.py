"""add unbilled_usage reconciliation queue

Revision ID: c9d5e7a1b344
Revises: b8c4d6f0a233
Create Date: 2026-08-02 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9d5e7a1b344'
down_revision: Union[str, Sequence[str], None] = 'b8c4d6f0a233'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Usage that was delivered to a founder but never charged.

    Written when metering fails after a successful reply. Rows are marked resolved
    rather than deleted, so "how much went unbilled last week" is still answerable
    once the backlog has been replayed.

    No FK to founders: this must remain writable even while the founders row is
    being modified, and losing the audit of unbilled usage because the user was
    later deleted would defeat the purpose.
    """
    op.create_table(
        "unbilled_usage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("founder_id", sa.Integer(), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=False),
        sa.Column("credits_owed", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="chat"),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_unbilled_usage_founder_id", "unbilled_usage", ["founder_id"])
    op.create_index("ix_unbilled_usage_created_at", "unbilled_usage", ["created_at"])
    # Partial index: the reconciler only ever scans unresolved rows, and this keeps
    # that scan cheap as resolved history accumulates.
    op.create_index("ix_unbilled_usage_pending", "unbilled_usage", ["resolved"],
                    postgresql_where=sa.text("resolved = false"))


def downgrade() -> None:
    op.drop_index("ix_unbilled_usage_pending", table_name="unbilled_usage")
    op.drop_index("ix_unbilled_usage_created_at", table_name="unbilled_usage")
    op.drop_index("ix_unbilled_usage_founder_id", table_name="unbilled_usage")
    op.drop_table("unbilled_usage")
