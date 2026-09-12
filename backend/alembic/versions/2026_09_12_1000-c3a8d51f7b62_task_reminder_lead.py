"""Let a founder choose how far ahead of a task they are reminded.

Plan Your Day showed a fixed "Reminder 30 min before" -- a label, not a
control. The 30 came from CALENDAR_REMINDER_MINUTES_BEFORE (the Google popup)
and TASK_REMINDER_MINUTES_BEFORE (the email), both platform-wide. This column
is where the founder's own answer goes, so the picker in the manual-add form
has somewhere to store it and the calendar push and the email reminder can read
the same number rather than a constant.

NULLABLE, WITH NO SERVER DEFAULT, ON PURPOSE. Null means "I never chose, use
the platform default". Every row that exists today is exactly that, so the
deploy changes nobody's reminders -- and if the default is ever moved off 30,
it moves for the founders who never expressed a preference and only them. A
server_default of 30 would freeze today's default into a million rows and make
that impossible to tell apart from a deliberate choice of thirty minutes.

0 is a real value, distinct from null: remind me at the time itself. Code that
reads this column must test for None, not for falsiness.

Additive and nullable, so the deploy is a no-op for anything already running.

Revision ID: c3a8d51f7b62
Revises: b7e4f2a91c58
Create Date: 2026-09-12 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "c3a8d51f7b62"
down_revision = "b7e4f2a91c58"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "planning_tasks",
        sa.Column("reminder_minutes_before", sa.Integer(), nullable=True),
    )
    # No index. Nothing queries tasks BY their reminder lead: the calendar push
    # and the email both already have the task row in hand when they read it.


def downgrade() -> None:
    op.drop_column("planning_tasks", "reminder_minutes_before")
