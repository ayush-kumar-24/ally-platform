"""Register the bell's name for a Plan Your Day task reminder.

Every founder is reminded about a task they planned; only the CHANNEL is sold.
Email is the Pro delivery, and everyone else gets the same nudge in the bell at
the same moment -- a founder on Starter has still planned their day.

`notifications.type` is validated against this table by
`app/notifications/writer.py`, whose `_is_active` check is the one-UPDATE kill
switch for a type. Without this row the writer refuses every task reminder and
non-Pro founders are silently reminded of nothing, which is exactly the failure
mode this whole change exists to end.

Idempotent: ON CONFLICT DO NOTHING, so re-running against a database that
already has the row is a no-op.

Revision ID: d4b9e63a08f7
Revises: c3a8d51f7b62
Create Date: 2026-09-12 14:00:00.000000
"""

from alembic import op

revision = "d4b9e63a08f7"
down_revision = "c3a8d51f7b62"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO notification_types (type, label, description, is_active)
        VALUES (
            'task_reminder',
            'Task reminder',
            'A planned task is coming up, at the offset the founder chose.',
            true
        )
        ON CONFLICT (type) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM notification_types WHERE type = 'task_reminder';")
