"""add planning_reminders

Revision ID: c3d1f0a2b7e4
Revises: a182f6ed2ad5
Create Date: 2026-07-30 05:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d1f0a2b7e4'
down_revision: Union[str, Sequence[str], None] = 'a182f6ed2ad5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Task reminders (scheduled nudges). Delivery is a worker's job; this table is
    the schedule + its status (scheduled / sent / cancelled)."""
    op.create_table(
        "planning_reminders",
        sa.Column("reminder_id", sa.String(length=64), primary_key=True),
        sa.Column("task_id", sa.String(length=64),
                  sa.ForeignKey("planning_tasks.task_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("plan_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("founder_id", sa.Integer(), nullable=False, index=True),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("channel", sa.String(length=20), nullable=False, server_default="in_app"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="scheduled", index=True),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    # The worker's poll: scheduled reminders whose time has arrived.
    op.create_index(
        "ix_planning_reminders_due", "planning_reminders", ["status", "remind_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_planning_reminders_due", table_name="planning_reminders")
    op.drop_table("planning_reminders")
