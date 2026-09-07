"""Open up notification types, and make them switchable without a deploy.

THE PROBLEM. `notifications.type` was pinned by a CHECK constraint listing
exactly eight values. The bell is meant to carry roughly forty kinds of thing --
credits expiring, a task overdue, an account deletion about to complete -- so
under the old constraint every new one cost a migration, and a migration is
enough friction that the notification just does not get added.

THE FIX. A lookup table. `notification_types` holds the vocabulary, and
`notifications.type` references it. Adding a kind is now one INSERT.

WHY THAT IS WORTH A TABLE. `is_active`. A notification that turns out to be
annoying can be switched off in the database, immediately, for everyone --
no deploy, no release, no waiting. That matters because nobody can tell in
advance which of these will be useful and which will be noise, and the cost of
guessing wrong is that founders stop opening the bell at all. The code checks
`is_active` before writing, so a switched-off type simply stops appearing.

`label` and `description` exist so the admin panel can list the vocabulary in
human words rather than showing `daily_actions_pending` to a person.

NOTHING IS LOST. Every one of the original eight is seeded below with the same
spelling, so existing rows stay valid and existing code keeps working.

Revision ID: d3f8b71c02a9
Revises: a7f2c81d94e3
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d3f8b71c02a9"
down_revision = "a7f2c81d94e3"
branch_labels = None
depends_on = None

_CHECK = "notifications_type_check"

#: (type, label, description). Grouped the way a founder would group them, which
#: is also the order the admin list reads best in.
_TYPES: list[tuple[str, str, str]] = [
    # --- diagnosis ---
    ("diagnosis_reminder", "Diagnosis reminder", "Generic diagnosis nudge (original type, kept)."),
    ("diagnosis_incomplete", "Diagnosis unfinished", "Started the diagnosis and stopped partway."),
    ("diagnosis_stale", "Diagnosis untouched", "No diagnosis activity for several days."),
    ("diagnosis_complete", "Diagnosis complete", "The diagnosis finished."),
    ("diagnosis_hypothesis_ready", "Hypothesis ready", "Ally has a hypothesis and wants it confirmed."),
    # --- report ---
    ("report_ready", "Report ready", "The report has been generated (original type, kept)."),
    ("report_pdf_ready", "Report PDF ready", "The PDF finished rendering and can be downloaded."),
    ("report_feedback_request", "Rate your report", "Asks what they thought of the report."),
    ("outcome_checkin", "Outcome check-in", "30 / 60 / 90 days after the report: how did it go?"),
    # --- discovery calls ---
    ("discovery_call_reminder", "Call reminder", "The call is close (original type, kept)."),
    ("discovery_call_requested", "Call requested", "Request received, waiting on the team."),
    ("discovery_call_confirmed", "Call confirmed", "The team confirmed it; joining link available."),
    ("discovery_call_cancelled", "Call cancelled", "Cancelled, with the reason."),
    ("discovery_call_notes_ready", "Call notes ready", "Notes from the call have been written up."),
    ("free_call_available", "Free call available", "Their plan's included call is unused this month."),
    # --- plan, payment, coupons ---
    ("subscription_expiring", "Plan renewing", "Renewal is coming up (original type, kept)."),
    ("subscription_expired", "Plan expired", "The subscription has lapsed."),
    ("payment_failed", "Payment failed", "A payment did not go through (original type, kept)."),
    ("payment_success", "Payment received", "Payment taken; invoice available."),
    ("refund_processed", "Refund processed", "A refund has been issued."),
    ("coupon_applied", "Discount applied", "A coupon was successfully applied."),
    # --- credits and usage ---
    ("token_limit_reached", "Daily limit reached", "Today's allowance is used up (original type, kept)."),
    ("token_limit_warning", "Daily limit close", "Most of today's allowance is used."),
    ("allowance_reset", "Allowance reset", "The daily allowance has refreshed."),
    ("credits_low", "Credits low", "The credit balance is running down."),
    ("credits_expiring", "Credits expiring", "Monthly credits expire soon -- use them or lose them."),
    ("credits_granted", "Credits added", "The team added credits to the account."),
    # --- goals, tasks, plan your day ---
    ("task_due_today", "Task due today", "One or more tasks are due today."),
    ("task_overdue", "Task overdue", "A task is past its due date."),
    ("goal_deadline_near", "Goal deadline near", "A goal's target date is approaching."),
    ("daily_actions_pending", "Today's actions", "Today's actions are not done yet."),
    ("daily_nudge", "Daily nudge", "The reminder at the time the founder chose."),
    ("calendar_sync_broken", "Calendar sync broken", "Calendar connection needs reconnecting."),
    # --- recommendations ---
    ("recommendations_new", "New recommendations", "Fresh recommendations are waiting."),
    ("suggestions_unread", "Unread suggestions", "Suggestions raised but not looked at."),
    ("root_cause_found", "New root cause", "A new top finding was detected."),
    # --- profile ---
    ("profile_incomplete", "Profile incomplete", "Names the exact field that is missing."),
    ("first_impression_ready", "First impression ready", "Ally's first read on them is ready."),
    ("tour_available", "Take the tour", "The product tour has not been seen."),
    # --- privacy, account, security ---
    ("privacy_request_updated", "Privacy request updated", "Status changed: in progress, done or rejected."),
    ("data_export_ready", "Data export ready", "The requested data export can be downloaded."),
    ("account_deletion_grace", "Deletion pending", "The account deletes soon -- last chance to cancel."),
    ("new_device_signin", "New device sign-in", "Signed in from a device not seen before."),
    ("terms_updated", "Terms updated", "Terms or privacy policy changed."),
    # --- other ---
    ("product_update", "Product update", "Something new in Ally (original type, kept)."),
    ("follow_up", "Follow up", "Generic follow-up (original type, kept)."),
    ("memory_expiring", "Saved note expiring", "A saved memory is about to age out."),
    ("framework_stale", "Framework not revisited", "A framework they used has not been opened in a while."),
]


def upgrade() -> None:
    op.create_table(
        "notification_types",
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # The switch. Turning this false stops the type being written, for
        # everyone, immediately -- no deploy. See the module docstring.
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("type", name="notification_types_pkey"),
    )

    op.bulk_insert(
        sa.table(
            "notification_types",
            sa.column("type", sa.String),
            sa.column("label", sa.String),
            sa.column("description", sa.Text),
        ),
        [{"type": t, "label": lbl, "description": d} for t, lbl, d in _TYPES],
    )

    # Order matters: the old CHECK forbids every new value, so it comes off
    # before the foreign key that replaces it goes on.
    op.execute(f'ALTER TABLE public.notifications DROP CONSTRAINT IF EXISTS "{_CHECK}"')
    op.create_foreign_key(
        "notifications_type_fkey", "notifications", "notification_types",
        ["type"], ["type"], onupdate="CASCADE",
    )

    # A dedup key, so a recurring notification ("credits expiring") written by a
    # sweep that runs every few hours does not stack up a fresh copy every run.
    # Nullable: one-off events do not need it and should not be forced to invent
    # one. Unique per founder where present.
    op.add_column("notifications", sa.Column("dedup_key", sa.String(length=200), nullable=True))
    op.create_index(
        "uq_notifications_dedup", "notifications", ["founder_id", "dedup_key"],
        unique=True, postgresql_where=sa.text("dedup_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_notifications_dedup", table_name="notifications")
    op.drop_column("notifications", "dedup_key")
    op.drop_constraint("notifications_type_fkey", "notifications", type_="foreignkey")

    # Rows using a type the old constraint forbids must go, or the CHECK cannot
    # be recreated. Lossy, and only reachable by a deliberate downgrade.
    original = (
        "report_ready", "diagnosis_reminder", "discovery_call_reminder", "follow_up",
        "product_update", "token_limit_reached", "subscription_expiring", "payment_failed",
    )
    values = ", ".join(f"'{t}'" for t in original)
    op.execute(f"DELETE FROM public.notifications WHERE type NOT IN ({values})")
    op.execute(
        f'ALTER TABLE public.notifications ADD CONSTRAINT "{_CHECK}" '
        f"CHECK (type::text = ANY (ARRAY[{', '.join(chr(39)+t+chr(39)+'::character varying' for t in original)}]::text[]))"
    )
    op.drop_table("notification_types")
