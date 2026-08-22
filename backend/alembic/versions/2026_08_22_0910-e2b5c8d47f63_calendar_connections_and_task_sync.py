"""Google Calendar sync: per-founder connections, and sync state on tasks.

Two parts.

**calendar_connections** -- one row per founder per provider, holding the OAuth
tokens for THEIR calendar. Deliberately separate from app/services/calendar.py,
which is a service account acting on GoXL's own calendar to book discovery
calls: different account, different calendar, different auth model. Sharing a
table between them would conflate "GoXL's booking calendar" with "the founder's
personal calendar", which is exactly the sort of thing that leaks one founder's
events into another's view.

`provider` is a column rather than an assumption even though only 'google' works
today, so adding Outlook later is a row, not a schema rebuild. The unique
constraint is (founder_id, provider) -- one connection per provider per founder,
reconnecting updates in place rather than accumulating dead rows.

Tokens are stored ENCRYPTED (see app/calendar_sync/crypto.py). The columns are
Text rather than a fixed width because ciphertext is longer than the plaintext
and Fernet tokens carry their own envelope.

**planning_tasks** gains three columns:

  calendar_event_id     the Google event this task owns, or NULL when it has
                        never synced. This is what makes edits update the same
                        event instead of creating a duplicate on every save.
  calendar_sync_status  pending / synced / failed / skipped -- shown to the
                        founder, because a task that silently did not reach
                        their calendar is worse than one they know did not.
  due_time              optional time of day. Needed because Google expresses
                        reminders as "minutes before start": an all-day event
                        starts at midnight, so a 30-minutes-before popup fires
                        at 23:30 the night before, and a morning-of popup is
                        not expressible at all. A timed event makes the chosen
                        reminder mean what it says.

Revision ID: e2b5c8d47f63
Revises: d5a7c91e2f64
Create Date: 2026-08-22 09:10:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2b5c8d47f63"
down_revision: Union[str, Sequence[str], None] = "d5a7c91e2f64"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "calendar_connections",
        sa.Column("connection_id", sa.String(64), primary_key=True),
        sa.Column("founder_id", sa.Integer,
                  sa.ForeignKey("founders.founder_id", ondelete="CASCADE"),
                  nullable=False, index=True),
        # Not an enum: a new provider should be a value, not a migration.
        sa.Column("provider", sa.String(20), nullable=False, server_default="google"),
        # Which Google account was connected. Shown back to the founder, because
        # it does NOT have to match their Ally login (auth here is email-only,
        # so the two are unrelated) and "connected to which account?" is
        # otherwise unanswerable.
        sa.Column("account_email", sa.String(320), nullable=False, server_default=""),
        sa.Column("access_token_encrypted", sa.Text, nullable=False, server_default=""),
        sa.Column("refresh_token_encrypted", sa.Text, nullable=False, server_default=""),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        # active / revoked / error. 'error' is distinct from 'revoked': a refresh
        # that fails once is not proof the founder withdrew access, and prompting
        # them to reconnect over a transient Google outage trains them to ignore
        # the prompt.
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_error", sa.Text, nullable=False, server_default=""),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("founder_id", "provider", name="uq_calendar_connection_founder_provider"),
    )

    op.add_column("planning_tasks", sa.Column("due_time", sa.Time(), nullable=True))
    op.add_column("planning_tasks", sa.Column("calendar_event_id", sa.String(256), nullable=True))
    op.add_column("planning_tasks",
                  sa.Column("calendar_sync_status", sa.String(20), nullable=False,
                            server_default="skipped"))
    # Deleting a task must delete its event, and the sweep that retries failures
    # looks up exactly these two. Partial index: the overwhelming majority of
    # rows are NULL (never synced) and carry no information worth indexing.
    op.create_index("ix_planning_tasks_calendar_event", "planning_tasks",
                    ["calendar_event_id"], postgresql_where=sa.text("calendar_event_id IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("ix_planning_tasks_calendar_event", table_name="planning_tasks")
    op.drop_column("planning_tasks", "calendar_sync_status")
    op.drop_column("planning_tasks", "calendar_event_id")
    op.drop_column("planning_tasks", "due_time")
    op.drop_table("calendar_connections")
