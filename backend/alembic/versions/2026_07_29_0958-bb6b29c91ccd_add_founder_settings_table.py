"""add founder_settings table

Revision ID: bb6b29c91ccd
Revises: 0210ac55cd12
Create Date: 2026-07-29 09:58:49.357133

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb6b29c91ccd'
down_revision: Union[str, Sequence[str], None] = '0210ac55cd12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create founder_settings (one row per founder; Phase 11)."""
    op.create_table(
        "founder_settings",
        sa.Column("founder_id", sa.Integer(),
                  sa.ForeignKey("founders.founder_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("daily_reminders", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("reminder_time", sa.String(length=5), nullable=False, server_default=sa.text("'09:00'")),
        sa.Column("task_reminders", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("meeting_reminders", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("goal_reminders", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("session_timeout_minutes", sa.Integer(), nullable=False, server_default=sa.text("60")),
        sa.Column("login_notifications", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_table("founder_settings")
