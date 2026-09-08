"""Recurring subscriptions, invoices and billing identity.

WHAT WAS WRONG. Plus (Rs 499) and Pro (Rs 999) were sold as ONE-TIME orders.
`_grant_for_captured` wrote a subscriptions row with `expires_at = now + 30
days` and stopped there: nothing renewed it, nothing enforced it, and no
Razorpay mandate existed to charge a second month. A founder paid Rs 499 once
and kept Plus forever. The catalog said as much in a comment -- "Nothing
enforces that difference... Whoever wires Razorpay owns making the code agree
with it" -- and this migration is the schema half of doing that.

WHAT THIS ADDS.

`razorpay_plans` -- the Rs 499/Rs 999 Razorpay Plan ids, one row per (tier,
mode). NOT a second price list: `amount_inr` here is a recorded copy of what
the plan was created for at Razorpay, and app/plans/catalog.py stays the only
place a price is decided. The mapping is a table rather than an env var
because test and live plan ids differ, a plan's billing amount is immutable
at Razorpay (a price change means a NEW plan id), and an env var cannot keep
the superseded one for the founders still billed on it.

`subscriptions` recurring columns -- the state Razorpay reports and we must
mirror to answer "when is the next charge" and "how long does access last"
without asking the gateway on every page load. `access_until` is the one that
matters: it is what a cancelled-at-period-end subscription keeps paid features
alive on, and what the expiry sweep reads.

`invoices` -- Razorpay raises an invoice per subscription charge, and the
founder needs to see it. Stored as ids and a URL, never as a rendered
document: Razorpay's invoice is the artefact, ours is the index into it.
`tax_amount_inr` is nullable and unbacked by any tax logic on purpose -- GST
treatment is the CA's to confirm (guide step 14), and a number this codebase
invented would be worse than a null.

`business_profiles` -- name/GSTIN/address, needed before a GST invoice can be
correct. One row per founder, separate from `founders` because it is billing
identity, not product identity, and most founders will never have one.

WHAT THIS DELIBERATELY DOES NOT ADD. An `entitlements` table. Access already
has exactly one source of truth in this codebase -- `founders.plan_type`, what
the admin panel writes and every feature gate reads -- and a second table
claiming the same authority is how two surfaces start disagreeing about
whether someone has paid. The entitlement *semantics* the guide asks for
(access_start, access_until, expiry) live on `subscriptions` instead, and the
API presents them under an `entitlement` key.

Revision ID: e8a5c31d7f42
Revises: d7f4c2e91a63
"""

from alembic import op
import sqlalchemy as sa

revision = "e8a5c31d7f42"
down_revision = "d7f4c2e91a63"
branch_labels = None
depends_on = None

# Same policy name and role the rest of the estate uses (migration d91c6e4b72aa,
# and app/db/session.py) -- a new founder-scoped table joins that policy set
# rather than inventing a second convention.
_POLICY = "founder_isolation"
_ALLY_APP = "ally_app"

#: Razorpay's own subscription states, plus the ones this table already had.
#: 'created' and 'authenticated' are pre-payment: a subscription exists and the
#: mandate is signed, but nothing has been charged, so neither grants access.
_SUBSCRIPTION_STATUSES = (
    "created", "authenticated", "active", "pending", "halted",
    "cancelled", "completed", "expired", "paused", "trial",
)


def _ally_app_exists() -> bool:
    return bool(
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": _ALLY_APP})
        .scalar()
    )


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _add_column(table: str, column: sa.Column) -> None:
    if not _has_column(table, column.name):
        op.add_column(table, column)


def _founder_rls(table: str) -> None:
    """Join `table` to the estate-wide founder-isolation policy."""
    if not _ally_app_exists():
        return
    predicate = (
        "(founder_id = public.get_founder_id()) OR "
        "(COALESCE(NULLIF(current_setting('app.current_admin', true), '')::boolean, false))"
    )
    op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'DROP POLICY IF EXISTS "{_POLICY}" ON public."{table}"')
    op.execute(
        f'CREATE POLICY "{_POLICY}" ON public."{table}" '
        f"AS PERMISSIVE FOR ALL TO {_ALLY_APP} "
        f"USING ({predicate}) WITH CHECK ({predicate})"
    )
    op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON public."{table}" TO {_ALLY_APP}')


def upgrade() -> None:
    # --- the Razorpay Plan id map ------------------------------------------
    op.create_table(
        "razorpay_plans",
        sa.Column("plan_map_id", sa.Integer(), autoincrement=True, nullable=False),
        # An app.plans.catalog PlanTier value -- 'starter' is the Rs 499 plan
        # shown as "Plus", 'basic' the Rs 199 one shown as "Starter". See the
        # naming table in catalog.py; getting these two the wrong way round
        # bills a founder Rs 499 for a Rs 199 product.
        sa.Column("tier", sa.String(length=20), nullable=False),
        # 'test' or 'live'. Both coexist so switching RAZORPAY_KEY_ID between
        # modes does not require editing rows -- the wrong-mode plan id is
        # simply not selected.
        sa.Column("mode", sa.String(length=4), nullable=False),
        sa.Column("razorpay_plan_id", sa.String(length=200), nullable=False),
        # A recorded copy of what this plan was created for at Razorpay, for
        # reconciliation only. The price a founder is charged comes from
        # app/plans/catalog.py; a mismatch between the two is an alertable
        # fact, which is why it is stored rather than assumed.
        sa.Column("amount_inr", sa.Numeric(10, 2), nullable=False),
        sa.Column("billing_period", sa.String(length=10), server_default=sa.text("'monthly'"),
                  nullable=False),
        sa.Column("billing_interval", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.CheckConstraint("mode IN ('test', 'live')", name="razorpay_plans_mode_check"),
        sa.CheckConstraint("billing_period IN ('daily', 'weekly', 'monthly', 'yearly')",
                           name="razorpay_plans_billing_period_check"),
        sa.CheckConstraint("billing_interval >= 1", name="razorpay_plans_billing_interval_check"),
        sa.CheckConstraint("amount_inr > 0", name="razorpay_plans_amount_check"),
        sa.PrimaryKeyConstraint("plan_map_id", name="razorpay_plans_pkey"),
        sa.UniqueConstraint("razorpay_plan_id", name="razorpay_plans_razorpay_plan_id_key"),
    )
    # Exactly one ACTIVE plan id per tier per mode. Superseded ids stay in the
    # table with is_active = false, because the founders billed on them still
    # need their subscription resolvable -- a Razorpay plan's amount is
    # immutable, so a price change is a new row, never an UPDATE.
    op.create_index("idx_razorpay_plans_active", "razorpay_plans", ["tier", "mode"],
                    unique=True, postgresql_where=sa.text("is_active"))

    # --- subscriptions: the recurring state --------------------------------
    _add_column("subscriptions", sa.Column("razorpay_plan_id", sa.String(length=200),
                                           nullable=True))
    # How many cycles Razorpay has actually charged. Read straight off the
    # subscription entity rather than counted here: our count would drift the
    # first time a webhook was missed, and Razorpay's is the billing record.
    _add_column("subscriptions", sa.Column("paid_count", sa.Integer(),
                                           server_default=sa.text("0"), nullable=False))
    _add_column("subscriptions", sa.Column("current_period_start",
                                           sa.DateTime(timezone=True), nullable=True))
    _add_column("subscriptions", sa.Column("current_period_end",
                                           sa.DateTime(timezone=True), nullable=True))
    _add_column("subscriptions", sa.Column("next_charge_at",
                                           sa.DateTime(timezone=True), nullable=True))
    _add_column("subscriptions", sa.Column("activated_at",
                                           sa.DateTime(timezone=True), nullable=True))
    _add_column("subscriptions", sa.Column("ended_at",
                                           sa.DateTime(timezone=True), nullable=True))
    _add_column("subscriptions", sa.Column("cancel_at_period_end", sa.Boolean(),
                                           server_default=sa.text("false"), nullable=False))
    # THE ACCESS CLOCK. Paid features stay on until this moment and not one
    # second past it, whatever the subscription's status says -- which is what
    # makes "cancel now, keep what you paid for until the 3rd" expressible.
    # NULL means "no time-bounded access from this row" (a one-time purchase,
    # which buys a deliverable rather than a period).
    _add_column("subscriptions", sa.Column("access_until",
                                           sa.DateTime(timezone=True), nullable=True))

    # One subscriptions row per Razorpay subscription. Without this, a webhook
    # replayed after a partial failure could create a second row for the same
    # mandate and the founder would appear to have two Plus subscriptions.
    op.create_index("idx_subscriptions_gateway_id", "subscriptions", ["gateway_subscription_id"],
                    unique=True, postgresql_where=sa.text("gateway_subscription_id IS NOT NULL"))
    op.create_index("idx_subscriptions_access_until", "subscriptions", ["access_until"],
                    postgresql_where=sa.text("access_until IS NOT NULL"))

    # Razorpay's own states have to be storable or the mirror is a lie: a
    # `halted` subscription that can only be written as 'active' or 'cancelled'
    # forces a choice between over- and under-granting access.
    op.execute("ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS "
               "subscriptions_status_check")
    op.execute(
        "ALTER TABLE subscriptions ADD CONSTRAINT subscriptions_status_check "
        "CHECK (status::text = ANY (ARRAY["
        + ", ".join(f"'{s}'::character varying" for s in _SUBSCRIPTION_STATUSES)
        + "]::text[]))"
    )

    # --- payments: link a charge to its subscription and invoice -----------
    _add_column("payments", sa.Column("gateway_subscription_id", sa.String(length=200),
                                      nullable=True))
    _add_column("payments", sa.Column("gateway_invoice_id", sa.String(length=200),
                                      nullable=True))
    op.create_index("idx_payments_gateway_subscription", "payments", ["gateway_subscription_id"],
                    postgresql_where=sa.text("gateway_subscription_id IS NOT NULL"))
    # The idempotency guard PaymentService already relies on, made a rule rather
    # than a convention: one payments row per Razorpay payment id, so a replayed
    # webhook cannot grant twice even if the service check were bypassed.
    op.create_index("idx_payments_gateway_payment_id", "payments", ["gateway_payment_id"],
                    unique=True, postgresql_where=sa.text("gateway_payment_id IS NOT NULL"))

    # --- invoices ----------------------------------------------------------
    op.create_table(
        "invoices",
        sa.Column("invoice_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("founder_id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=True),
        sa.Column("payment_id", sa.Integer(), nullable=True),
        sa.Column("gateway_invoice_id", sa.String(length=200), nullable=False),
        sa.Column("gateway_order_id", sa.String(length=200), nullable=True),
        sa.Column("gateway_payment_id", sa.String(length=200), nullable=True),
        sa.Column("gateway_subscription_id", sa.String(length=200), nullable=True),
        # Razorpay's own human-readable number, not one we mint. Two systems
        # numbering the same invoice is a reconciliation problem, and theirs is
        # the one printed on the document the founder downloads.
        sa.Column("invoice_number", sa.String(length=50), nullable=True),
        sa.Column("amount_inr", sa.Numeric(10, 2), nullable=False),
        # Nullable and never computed here -- see the module docstring. Filled
        # only from what Razorpay reports, once the CA has confirmed the
        # treatment (guide step 14).
        sa.Column("tax_amount_inr", sa.Numeric(10, 2), nullable=True),
        sa.Column("total_amount_inr", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(length=5), server_default=sa.text("'INR'"),
                  nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("invoice_url", sa.Text(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.CheckConstraint(
            "status IN ('issued', 'partially_paid', 'paid', 'cancelled', 'expired', 'deleted')",
            name="invoices_status_check"),
        sa.ForeignKeyConstraint(["founder_id"], ["founders.founder_id"],
                                name="invoices_founder_id_fkey"),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.subscription_id"],
                                name="invoices_subscription_id_fkey"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.payment_id"],
                                name="invoices_payment_id_fkey"),
        sa.PrimaryKeyConstraint("invoice_id", name="invoices_pkey"),
        # Idempotency for invoice.paid, which Razorpay retries exactly as it
        # retries payment.captured.
        sa.UniqueConstraint("gateway_invoice_id", name="invoices_gateway_invoice_id_key"),
    )
    op.create_index("idx_invoices_founder", "invoices", ["founder_id", "issued_at"])

    # --- business / GST billing identity -----------------------------------
    op.create_table(
        "business_profiles",
        sa.Column("profile_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("founder_id", sa.Integer(), nullable=False),
        sa.Column("customer_type", sa.String(length=10), server_default=sa.text("'individual'"),
                  nullable=False),
        sa.Column("business_name", sa.String(length=200), nullable=True),
        # Stored upper-cased by the application. The CHECK is the real GSTIN
        # shape (2-digit state code, 10-char PAN, entity digit, 'Z', checksum)
        # so a typo is refused at write time rather than discovered on an
        # invoice a customer cannot claim credit against.
        sa.Column("gstin", sa.String(length=15), nullable=True),
        sa.Column("billing_address", sa.Text(), nullable=True),
        sa.Column("billing_city", sa.String(length=100), nullable=True),
        # Place of supply. Kept as its own column, not parsed out of the
        # address, because GST treatment turns on it.
        sa.Column("billing_state", sa.String(length=100), nullable=True),
        sa.Column("billing_pincode", sa.String(length=10), nullable=True),
        sa.Column("billing_country", sa.String(length=2), server_default=sa.text("'IN'"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.CheckConstraint("customer_type IN ('individual', 'business')",
                           name="business_profiles_customer_type_check"),
        sa.CheckConstraint(
            "gstin IS NULL OR gstin ~ '^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'",
            name="business_profiles_gstin_format_check"),
        # A business invoice needs a business name. Enforced here rather than
        # in a validator alone: this is the column the invoice prints from.
        sa.CheckConstraint(
            "customer_type = 'individual' OR business_name IS NOT NULL",
            name="business_profiles_business_name_check"),
        sa.CheckConstraint("billing_pincode IS NULL OR billing_pincode ~ '^[0-9]{6}$'",
                           name="business_profiles_pincode_check"),
        sa.ForeignKeyConstraint(["founder_id"], ["founders.founder_id"], ondelete="CASCADE",
                                name="business_profiles_founder_id_fkey"),
        sa.PrimaryKeyConstraint("profile_id", name="business_profiles_pkey"),
        sa.UniqueConstraint("founder_id", name="business_profiles_founder_id_key"),
    )

    _founder_rls("invoices")
    _founder_rls("business_profiles")
    if _ally_app_exists():
        # razorpay_plans is catalogue data, not founder data -- the same call
        # `coupons` makes. A founder never reads it directly; the backend does,
        # on their behalf, to price a subscription.
        op.execute(f'GRANT SELECT, INSERT, UPDATE ON public."razorpay_plans" TO {_ALLY_APP}')
        op.execute(
            "GRANT USAGE, SELECT ON SEQUENCE razorpay_plans_plan_map_id_seq, "
            f"invoices_invoice_id_seq, business_profiles_profile_id_seq TO {_ALLY_APP}"
        )


def downgrade() -> None:
    op.drop_table("business_profiles")
    op.drop_index("idx_invoices_founder", table_name="invoices")
    op.drop_table("invoices")

    op.drop_index("idx_payments_gateway_payment_id", table_name="payments")
    op.drop_index("idx_payments_gateway_subscription", table_name="payments")
    op.drop_column("payments", "gateway_invoice_id")
    op.drop_column("payments", "gateway_subscription_id")

    op.execute("ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS "
               "subscriptions_status_check")
    op.execute(
        "ALTER TABLE subscriptions ADD CONSTRAINT subscriptions_status_check "
        "CHECK (status::text = ANY (ARRAY['active'::character varying, "
        "'cancelled'::character varying, 'expired'::character varying, "
        "'paused'::character varying, 'trial'::character varying]::text[]))"
    )
    op.drop_index("idx_subscriptions_access_until", table_name="subscriptions")
    op.drop_index("idx_subscriptions_gateway_id", table_name="subscriptions")
    for col in ("access_until", "cancel_at_period_end", "ended_at", "activated_at",
                "next_charge_at", "current_period_end", "current_period_start",
                "paid_count", "razorpay_plan_id"):
        op.drop_column("subscriptions", col)

    op.drop_index("idx_razorpay_plans_active", table_name="razorpay_plans")
    op.drop_table("razorpay_plans")
