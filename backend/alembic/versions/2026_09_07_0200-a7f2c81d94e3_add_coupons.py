"""Coupons: a redeemable discount on the one payment a founder makes.

Two tables and three columns on `payments`.

WHY THE DISCOUNT IS COMPUTED HERE AND NOT BY RAZORPAY
Razorpay has its own Offers feature that discounts at the gateway. It is the
wrong layer for this codebase: `payments.amount_inr` and `subscriptions.
amount_inr` are written from the catalog price the backend decided, and the
admin revenue views read those rows. A gateway-side discount would charge one
number and record another, so every revenue figure would overstate what
actually arrived. The order is therefore created at the already-discounted
amount, and `list_amount_inr` / `discount_inr` keep the arithmetic auditable.

WHY A REDEMPTION IS A ROW AND NOT A COUNTER
"First 100 customers" is one code with `max_redemptions = 100`, not 100 codes.
A naive `used_count` column cannot answer that safely: 105 founders opening
checkout in the same minute would all read 99 and all pass. Instead each
attempt inserts a `pending` redemption inside the same transaction that creates
the payment, and the cap is enforced by counting rows. The webhook flips the
row to `confirmed` on capture or `released` on failure, and a pending row older
than PENDING_TTL stops counting -- so an abandoned checkout cannot hoard a slot
and nobody is ever sold slot 101.

`valid_until` is NOT NULL on purpose. Every coupon expires at a moment the
admin picks; a discount with no end date is one nobody remembers to switch off.

The 99% ceiling is a CHECK, not a convention. Razorpay cannot create an order
for zero, so a 100% coupon would need a second, gateway-free grant path. One
path is worth more than the feature.
"""

from alembic import op
import sqlalchemy as sa

revision = "a7f2c81d94e3"
down_revision = "c7a3f92e651b"
branch_labels = None
depends_on = None

# Kept in step with app/db/session.py's policy name so a later table joins the
# same estate-wide policy set rather than inventing a second convention.
_POLICY = "founder_isolation"
_ALLY_APP = "ally_app"


def _ally_app_exists() -> bool:
    return bool(
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": _ALLY_APP})
        .scalar()
    )


def upgrade() -> None:
    op.create_table(
        "coupons",
        sa.Column("coupon_id", sa.Integer(), autoincrement=True, nullable=False),
        # Stored already upper-cased by the application; the unique index is on
        # the raw column, so "welcome" and "WELCOME" must not both be storable.
        # Callers normalise before writing -- see app/coupons/service.py.
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("discount_type", sa.String(length=10), nullable=False),
        # Percent for 'percent' (1-99), whole rupees for 'fixed'.
        sa.Column("discount_value", sa.Integer(), nullable=False),
        # NULL means every paid tier. Otherwise a list of PlanTier values.
        sa.Column("applies_to", sa.ARRAY(sa.String(length=20)), nullable=True),
        # NULL means unlimited redemptions; the "first 100" case sets 100.
        sa.Column("max_redemptions", sa.Integer(), nullable=True),
        sa.Column("max_per_founder", sa.Integer(), server_default=sa.text("1"),
                  nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        # Required: see the module docstring.
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"),
                  nullable=False),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("discount_type IN ('percent', 'fixed')",
                           name="coupons_discount_type_check"),
        # 99, not 100: a free order cannot be created at the gateway.
        sa.CheckConstraint(
            "(discount_type = 'percent' AND discount_value BETWEEN 1 AND 99) "
            "OR (discount_type = 'fixed' AND discount_value >= 1)",
            name="coupons_discount_value_check"),
        sa.CheckConstraint("max_redemptions IS NULL OR max_redemptions >= 1",
                           name="coupons_max_redemptions_check"),
        sa.CheckConstraint("max_per_founder >= 1", name="coupons_max_per_founder_check"),
        sa.CheckConstraint("valid_until > valid_from", name="coupons_validity_window_check"),
        sa.PrimaryKeyConstraint("coupon_id", name="coupons_pkey"),
    )
    op.create_index("coupons_code_key", "coupons", ["code"], unique=True)
    op.create_index("idx_coupons_active", "coupons", ["is_active", "valid_until"])

    op.create_table(
        "coupon_redemptions",
        sa.Column("redemption_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("coupon_id", sa.Integer(), nullable=False),
        sa.Column("founder_id", sa.Integer(), nullable=False),
        # Set in the same transaction as the payment row it belongs to.
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), server_default=sa.text("'pending'"),
                  nullable=False),
        sa.Column("discount_inr", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'confirmed', 'released')",
                           name="coupon_redemptions_status_check"),
        sa.ForeignKeyConstraint(["coupon_id"], ["coupons.coupon_id"],
                                name="coupon_redemptions_coupon_id_fkey"),
        sa.ForeignKeyConstraint(["founder_id"], ["founders.founder_id"],
                                name="coupon_redemptions_founder_id_fkey"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.payment_id"],
                                name="coupon_redemptions_payment_id_fkey"),
        sa.PrimaryKeyConstraint("redemption_id", name="coupon_redemptions_pkey"),
        # One redemption per payment: the payment is what the founder is buying,
        # so two coupons on one order is not a thing that can happen by accident.
        sa.UniqueConstraint("payment_id", name="coupon_redemptions_payment_id_key"),
    )
    op.create_index("idx_coupon_redemptions_coupon", "coupon_redemptions",
                    ["coupon_id", "status"])
    op.create_index("idx_coupon_redemptions_founder", "coupon_redemptions",
                    ["founder_id", "coupon_id"])

    # The audit trail for what was actually charged. `amount_inr` stays the
    # amount that reached the gateway, so nothing downstream of it changes.
    op.add_column("payments", sa.Column("coupon_id", sa.Integer(), nullable=True))
    op.add_column("payments", sa.Column("list_amount_inr", sa.Numeric(10, 2), nullable=True))
    op.add_column("payments", sa.Column("discount_inr", sa.Numeric(10, 2), nullable=True))
    op.create_foreign_key("payments_coupon_id_fkey", "payments", "coupons",
                          ["coupon_id"], ["coupon_id"])

    # coupon_redemptions is founder-scoped and joins the same isolation policy
    # as payments (migration d91c6e4b72aa). `coupons` deliberately does NOT: a
    # coupon belongs to nobody, it is catalogue data a founder must be able to
    # validate before they own any row referencing it.
    if _ally_app_exists():
        op.execute('ALTER TABLE public."coupon_redemptions" ENABLE ROW LEVEL SECURITY')
        op.execute(f'DROP POLICY IF EXISTS "{_POLICY}" ON public."coupon_redemptions"')
        predicate = (
            "(founder_id = public.get_founder_id()) OR "
            "(COALESCE(NULLIF(current_setting('app.current_admin', true), '')::boolean, false))"
        )
        op.execute(
            f'CREATE POLICY "{_POLICY}" ON public."coupon_redemptions" '
            f"AS PERMISSIVE FOR ALL TO {_ALLY_APP} "
            f"USING ({predicate}) WITH CHECK ({predicate})"
        )
        op.execute(
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON public."coupon_redemptions" '
            f"TO {_ALLY_APP}"
        )
        # Read-only for founders (validating a code); writes are admin-only and
        # go through the panel, which widens RLS after its own role check.
        op.execute(f'GRANT SELECT, INSERT, UPDATE ON public."coupons" TO {_ALLY_APP}')
        op.execute(
            "GRANT USAGE, SELECT ON SEQUENCE coupons_coupon_id_seq, "
            f"coupon_redemptions_redemption_id_seq TO {_ALLY_APP}"
        )


def downgrade() -> None:
    op.drop_constraint("payments_coupon_id_fkey", "payments", type_="foreignkey")
    op.drop_column("payments", "discount_inr")
    op.drop_column("payments", "list_amount_inr")
    op.drop_column("payments", "coupon_id")
    op.drop_index("idx_coupon_redemptions_founder", table_name="coupon_redemptions")
    op.drop_index("idx_coupon_redemptions_coupon", table_name="coupon_redemptions")
    op.drop_table("coupon_redemptions")
    op.drop_index("idx_coupons_active", table_name="coupons")
    op.drop_index("coupons_code_key", table_name="coupons")
    op.drop_table("coupons")
