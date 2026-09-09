"""Mark which task reminders Ally scheduled and which a founder set by hand.

Auto-reminders are derived state: when a task's due date moves, the reminder
has to move with it, and when the date is cleared the reminder has to go. That
means the sync rewrites and cancels rows freely -- which is only safe if it can
tell its own rows apart from one a founder created through
`POST /tasks/{id}/reminders`. Without this column it cannot, and the first time
somebody edited a due date it would delete a hand-set reminder.

server_default "manual" is the load-bearing half. Every row that already exists
predates auto-scheduling and was, by definition, created by hand; defaulting
them to "manual" leaves them untouched by the sync, which is the conservative
direction. A default of "auto" would hand the worker ownership of reminders it
never created.

Additive and nullable-free via the server default, so the deploy is a no-op for
anything already running.

Revision ID: b7e3a05c9f12
Revises: a1f4c9b73e05
Create Date: 2026-09-09 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "b7e3a05c9f12"
down_revision = "a1f4c9b73e05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "planning_reminders",
        sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
    )
    # No index is added here on purpose. The worker's query is
    # (status, remind_at) across all founders, and
    # `ix_planning_reminders_due` already covers exactly that -- it was created
    # with the table in c3d1f0a2b7e4, for a worker that was then never written.


def downgrade() -> None:
    op.drop_column("planning_reminders", "source")
