"""Growth layer: coupons, discounts, and a beta waitlist that remembers.

Four tables, two features that meet in exactly one place -- a cohort may carry a
coupon code, which then rides along in the invite email.

    coupons                 the discount rules
    coupon_redemptions      who claimed what, and when
    beta_cohorts            one release slot ("Beta round 3", 100 places)
    beta_waitlist_entries   the queue

The column that carries the whole design is `beta_waitlist_entries.times_deferred`.
Every release increments it for everyone still waiting, and the queue reads

    ORDER BY times_deferred DESC, priority DESC, joined_at ASC

so being passed over is what moves you up. Without a stored counter the "the ones
we skipped go first next time" rule would have to be reconstructed by joining
cohort membership against release timestamps -- derivable in principle, wrong in
practice the first time anyone edits a cohort by hand.

`ix_beta_waitlist_queue` matches that ORDER BY column-for-column and direction-for-
direction so the auto-pick is an index scan rather than a sort of the whole list.

Why the redemption ledger is a table and not a counter: `coupons.redeemed_count`
exists for display, but a per-founder limit ("one use each") cannot be enforced
from an aggregate. The unique index on (code, founder_id) is deliberately absent
-- max_per_founder may legitimately be greater than 1 -- so the cap is enforced by
a COUNT inside the redeeming transaction instead.

Revision ID: b7e2d94f1a63
Revises: a3f81c05e6d7
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

revision = "b7e2d94f1a63"
down_revision = "a3f81c05e6d7"
branch_labels = None
depends_on = None

ALLY_APP_ROLE = "ally_app"
INTERNAL_POLICY = "ally_runtime_internal_access_v2"

# All four are backend-internal: only the admin panel and the public join endpoint
# touch them, both through the API. No direct-client (anon/authenticated) policy is
# created, which leaves them closed to Supabase's client SDK by default -- a
# waitlist a browser could read is an email list a browser could scrape.
_TABLES = ("coupons", "coupon_redemptions", "beta_cohorts", "beta_waitlist_entries")

_DISCOUNT_TYPES = ("percent", "fixed", "credits", "free_days")
_ENTRY_STATUSES = ("waiting", "selected", "invited", "accepted", "declined", "removed")
_EMAIL_STATES = ("none", "queued", "sent", "failed", "skipped")
_EMAIL_KINDS = ("invite", "deferred")
_COHORT_STATUSES = ("open", "released")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} in (" + ", ".join(f"'{v}'" for v in values) + ")"


def _ally_app_exists() -> bool:
    return bool(op.get_bind().execute(
        text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
        {"role": ALLY_APP_ROLE}).scalar())


def upgrade() -> None:
    # --- coupons ----------------------------------------------------------
    op.create_table(
        "coupons",
        sa.Column("code", sa.String(length=40), primary_key=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("discount_type", sa.String(length=20), nullable=False),
        # Meaning depends on discount_type: percent 1-100, fixed in PAISE (the
        # minor unit -- money is never a float here), credits as a count, free_days
        # as days. One integer column rather than four nullable ones because
        # exactly one of them is ever populated.
        sa.Column("discount_value", sa.Integer(), nullable=False),
        # NULL means every plan. An empty array would mean the same thing and be a
        # second way to say it, so the service normalises [] to NULL on write.
        sa.Column("applies_to_plans", postgresql.JSONB(), nullable=True),
        sa.Column("max_redemptions", sa.Integer(), nullable=True),
        sa.Column("max_per_founder", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("redeemed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint(_in_list("discount_type", _DISCOUNT_TYPES),
                           name="coupons_discount_type_check"),
        sa.CheckConstraint("discount_value >= 1", name="coupons_discount_value_check"),
        # A percentage over 100 would pay the founder to subscribe. The service
        # rejects it too; this is the copy of the rule the database enforces even
        # if a row is written by hand.
        sa.CheckConstraint("discount_type <> 'percent' or discount_value <= 100",
                           name="coupons_percent_range_check"),
        sa.CheckConstraint("max_redemptions is null or max_redemptions >= 1",
                           name="coupons_max_redemptions_check"),
        sa.CheckConstraint("max_per_founder >= 1", name="coupons_max_per_founder_check"),
        sa.CheckConstraint("redeemed_count >= 0", name="coupons_redeemed_count_check"),
        sa.CheckConstraint("starts_at is null or expires_at is null or expires_at > starts_at",
                           name="coupons_window_check"),
    )
    op.create_index("ix_coupons_active", "coupons", ["active"])

    op.create_table(
        "coupon_redemptions",
        sa.Column("redemption_id", sa.String(length=64), primary_key=True),
        sa.Column("code", sa.String(length=40),
                  sa.ForeignKey("coupons.code", ondelete="CASCADE"), nullable=False),
        sa.Column("founder_id", sa.Integer(),
                  sa.ForeignKey("founders.founder_id", ondelete="CASCADE"), nullable=False),
        sa.Column("context", sa.String(length=30), nullable=False,
                  server_default="checkout"),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    # The per-founder cap is a COUNT over this pair, so it wants its own index.
    op.create_index("ix_coupon_redemptions_code_founder", "coupon_redemptions",
                    ["code", "founder_id"])

    # --- beta cohorts -----------------------------------------------------
    op.create_table(
        "beta_cohorts",
        sa.Column("cohort_id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slot_size", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        # No FK to coupons: retiring a coupon must not cascade into rewriting the
        # history of a cohort that already went out quoting it.
        sa.Column("coupon_code", sa.String(length=40), nullable=True),
        sa.Column("notify_deferred", sa.Boolean(), nullable=False,
                  server_default=sa.text("true")),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invited_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deferred_count", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(_in_list("status", _COHORT_STATUSES),
                           name="beta_cohorts_status_check"),
        sa.CheckConstraint("slot_size >= 1 and slot_size <= 5000",
                           name="beta_cohorts_slot_size_check"),
        # A released cohort without a timestamp would make the audit unanswerable.
        sa.CheckConstraint("status <> 'released' or released_at is not null",
                           name="beta_cohorts_released_at_check"),
    )

    # --- the waitlist -----------------------------------------------------
    op.create_table(
        "beta_waitlist_entries",
        sa.Column("entry_id", sa.String(length=64), primary_key=True),
        # Unique: the email IS the identity here. Someone who signs up twice must
        # not get two places, and -- more importantly -- must not be able to reset
        # their own times_deferred by re-submitting the form.
        sa.Column("email", sa.String(length=200), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=200), nullable=False, server_default=""),
        # Nullable and SET NULL: people join the waitlist before they have an
        # account, and deleting an account must not erase the queue position.
        sa.Column("founder_id", sa.Integer(),
                  sa.ForeignKey("founders.founder_id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="waiting"),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="signup"),
        # The queue's memory. See the module docstring.
        sa.Column("times_deferred", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cohort_id", sa.String(length=64),
                  sa.ForeignKey("beta_cohorts.cohort_id", ondelete="SET NULL"), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("coupon_code", sa.String(length=40), nullable=True),
        sa.Column("email_kind", sa.String(length=20), nullable=True),
        sa.Column("email_state", sa.String(length=20), nullable=False, server_default="none"),
        sa.Column("email_error", sa.Text(), nullable=True),
        sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint(_in_list("status", _ENTRY_STATUSES),
                           name="beta_waitlist_entries_status_check"),
        sa.CheckConstraint(_in_list("email_state", _EMAIL_STATES),
                           name="beta_waitlist_entries_email_state_check"),
        sa.CheckConstraint(f"email_kind is null or {_in_list('email_kind', _EMAIL_KINDS)}",
                           name="beta_waitlist_entries_email_kind_check"),
        sa.CheckConstraint("times_deferred >= 0",
                           name="beta_waitlist_entries_times_deferred_check"),
    )
    op.create_index("ix_beta_waitlist_entries_status", "beta_waitlist_entries", ["status"])
    op.create_index("ix_beta_waitlist_entries_cohort_id", "beta_waitlist_entries",
                    ["cohort_id"])
    op.create_index("ix_beta_waitlist_entries_founder_id", "beta_waitlist_entries",
                    ["founder_id"])
    # Matches the auto-pick ORDER BY exactly, including direction, so selecting the
    # next 100 off a list of thousands never sorts the table.
    op.create_index(
        "ix_beta_waitlist_queue", "beta_waitlist_entries",
        [sa.text("times_deferred DESC"), sa.text("priority DESC"),
         sa.text("joined_at ASC"), sa.text("entry_id ASC")],
        postgresql_where=sa.text("status = 'waiting'"))
    # The mail drain reads exactly this predicate.
    op.create_index("ix_beta_waitlist_pending_email", "beta_waitlist_entries",
                    ["email_state"],
                    postgresql_where=sa.text("email_state in ('queued', 'failed')"))

    _apply_rls()


def _apply_rls() -> None:
    """Lock the new tables to the backend role, matching revisions 4aa/8f6.

    RLS is enabled with NO public policy, so Supabase's anon and authenticated
    roles see nothing. `ally_app` -- the least-privileged role the API connects as
    in production -- gets an explicit permissive policy plus DML grants, because
    the tables are created by the migration role and would otherwise be
    unreachable from the app.

    On a target without `ally_app` (Supabase, local dev) the grants are skipped;
    RLS itself is still enabled, and the owner bypasses it.
    """
    for table in _TABLES:
        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')

    if not _ally_app_exists():
        print(f"WARNING [{revision}]: role {ALLY_APP_ROLE!r} does not exist; "
              "skipping runtime grants and policies.")
        return

    for table in _TABLES:
        op.execute(f'DROP POLICY IF EXISTS "{INTERNAL_POLICY}" ON public."{table}"')
        op.execute(
            f'CREATE POLICY "{INTERNAL_POLICY}" ON public."{table}" '
            f"AS PERMISSIVE FOR ALL TO {ALLY_APP_ROLE} "
            "USING (true) WITH CHECK (true)")
        op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public."{table}" '
                   f"TO {ALLY_APP_ROLE}")


def downgrade() -> None:
    op.drop_index("ix_beta_waitlist_pending_email", table_name="beta_waitlist_entries")
    op.drop_index("ix_beta_waitlist_queue", table_name="beta_waitlist_entries")
    op.drop_index("ix_beta_waitlist_entries_founder_id", table_name="beta_waitlist_entries")
    op.drop_index("ix_beta_waitlist_entries_cohort_id", table_name="beta_waitlist_entries")
    op.drop_index("ix_beta_waitlist_entries_status", table_name="beta_waitlist_entries")
    op.drop_table("beta_waitlist_entries")
    op.drop_table("beta_cohorts")
    op.drop_index("ix_coupon_redemptions_code_founder", table_name="coupon_redemptions")
    op.drop_table("coupon_redemptions")
    op.drop_index("ix_coupons_active", table_name="coupons")
    op.drop_table("coupons")
