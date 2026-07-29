"""add planning tables

Revision ID: a182f6ed2ad5
Revises: bb6b29c91ccd
Create Date: 2026-07-29 23:19:45.430040

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a182f6ed2ad5'
down_revision: Union[str, Sequence[str], None] = 'bb6b29c91ccd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create planning tables: plans -> goals -> tasks (Founder Action Plans)."""
    op.create_table(
        "planning_plans",
        sa.Column("plan_id", sa.String(length=64), primary_key=True),
        sa.Column("founder_id", sa.Integer(),
                  sa.ForeignKey("founders.founder_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "planning_goals",
        sa.Column("goal_id", sa.String(length=64), primary_key=True),
        sa.Column("plan_id", sa.String(length=64),
                  sa.ForeignKey("planning_plans.plan_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("founder_id", sa.Integer(), nullable=False, index=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="todo"),
        sa.Column("priority", sa.String(length=10), nullable=False, server_default="medium"),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "planning_tasks",
        sa.Column("task_id", sa.String(length=64), primary_key=True),
        sa.Column("goal_id", sa.String(length=64),
                  sa.ForeignKey("planning_goals.goal_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("plan_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("founder_id", sa.Integer(), nullable=False, index=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="todo"),
        sa.Column("priority", sa.String(length=10), nullable=False, server_default="medium"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("planning_tasks")
    op.drop_table("planning_goals")
    op.drop_table("planning_plans")
