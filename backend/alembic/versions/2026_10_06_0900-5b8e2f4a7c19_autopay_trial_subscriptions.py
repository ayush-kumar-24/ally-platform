"""Autopay subscriptions with a paid trial (Razorpay Subscriptions).

Revision ID: 5b8e2f4a7c19
Revises: 9d3e6a1f5c20
Create Date: 2026-10-06 09:00:00

Until now every purchase was a single one-time order (app/payments/). This adds
what a recurring, mandate-backed subscription needs, without touching how the
existing one-time checkout works:

  * coupons.trial_days -- a coupon that, instead of discounting a one-time
    order, starts an autopay subscription: the founder pays the discounted
    price up front for `trial_days`, then the plan's full price recurs.
  * subscriptions.status may now be 'halted' -- Razorpay's state when a
    recurring charge keeps failing. Widening only; nothing existing changes.
  * subscriptions.reminder_sent_at -- the "your trial ends soon" email is sent
    once per subscription.
  * A unique index on subscriptions.gateway_subscription_id (the column has
    existed, unused, since the table was created).
  * payments.gateway_subscription_id -- the trial's upfront payment row is
    created before Razorpay has charged anything, and this is how the webhook
    finds it again.
  * gateway_plans -- the Razorpay Plan ids this app created, so one ₹999/month
    plan is created once and reused rather than per subscription.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "5b8e2f4a7c19"
down_revision = "9d3e6a1f5c20"
branch_labels = None
depends_on = None

_STATUS = "subscriptions_status_check"
_STATUS_OLD = ("active", "cancelled", "expired", "paused", "trial")
_STATUS_NEW = ("active", "cancelled", "expired", "paused", "trial", "halted")


ALLY_APP_ROLE = "ally_app"


def _ally_app_exists() -> bool:
    """Whether the RDS-only `ally_app` runtime role exists on this target.
    Duplicated per-migration on purpose -- see the note in 7c4f0f1a9d2e."""
    return bool(op.get_bind().execute(
        text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": ALLY_APP_ROLE}
    ).scalar())


def _swap_status(vals: tuple[str, ...]) -> None:
    values = ", ".join(f"'{v}'::character varying" for v in vals)
    op.execute(f"ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS {_STATUS}")
    op.execute(f"ALTER TABLE subscriptions ADD CONSTRAINT {_STATUS} "
               f"CHECK (status::text = ANY (ARRAY[{values}]::text[]))")


def upgrade() -> None:
    op.add_column("coupons", sa.Column("trial_days", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "coupons_trial_days_check", "coupons",
        "trial_days IS NULL OR (trial_days >= 1 AND trial_days <= 30)")

    _swap_status(_STATUS_NEW)
    op.add_column("subscriptions",
                  sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("subscriptions_gateway_subscription_id_key", "subscriptions",
                    ["gateway_subscription_id"], unique=True,
                    postgresql_where=sa.text("gateway_subscription_id IS NOT NULL"))

    op.add_column("payments",
                  sa.Column("gateway_subscription_id", sa.String(200), nullable=True))
    op.create_index("idx_payments_gateway_subscription_id", "payments",
                    ["gateway_subscription_id"])

    op.create_table(
        "gateway_plans",
        sa.Column("gateway_plan_id", sa.String(200), primary_key=True),
        sa.Column("gateway", sa.String(50), nullable=False),
        sa.Column("plan_tier", sa.String(20), nullable=False),
        sa.Column("amount_inr", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("gateway", "plan_tier", "amount_inr", "period",
                            name="gateway_plans_identity_key"),
    )
    # No founder data in it, so no RLS policy -- the runtime role just needs to
    # read the plan id and record one the first time it is created.
    if _ally_app_exists():
        op.execute(f"GRANT SELECT, INSERT ON public.gateway_plans TO {ALLY_APP_ROLE}")


def downgrade() -> None:
    op.drop_table("gateway_plans")
    op.drop_index("idx_payments_gateway_subscription_id", table_name="payments")
    op.drop_column("payments", "gateway_subscription_id")
    op.drop_index("subscriptions_gateway_subscription_id_key", table_name="subscriptions")
    op.drop_column("subscriptions", "reminder_sent_at")
    op.execute("UPDATE subscriptions SET status = 'paused' WHERE status = 'halted'")
    _swap_status(_STATUS_OLD)
    op.drop_constraint("coupons_trial_days_check", "coupons", type_="check")
    op.drop_column("coupons", "trial_days")
