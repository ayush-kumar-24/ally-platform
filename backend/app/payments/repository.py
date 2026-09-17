"""Raw-SQL reads/writes against payments/subscriptions/founders -- same style
as app/admin/users_db_repository.py: parameterised text() queries, no ORM
model for these tables (schema.py's reflected Payments/Subscriptions classes
exist but this module writes the same defensive, explicit-column way the
rest of the Admin Panel already does)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.payments.models import InvoiceSource, PaymentRecord


class PaymentRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- payments ----------------------------------------------------------

    def create_pending(
        self, *, founder_id: int, amount_inr: int, currency: str, gateway: str,
        gateway_order_id: str, plan_tier: str, coupon_id: int | None = None,
        list_amount_inr: int | None = None, discount_inr: int | None = None,
        buyer_state: str | None = None, commit: bool = True,
    ) -> int:
        """`amount_inr` is always what the gateway was asked to charge.

        `list_amount_inr`/`discount_inr` are the audit trail behind it and are
        NULL on an undiscounted payment rather than a redundant copy -- so
        "was this discounted?" is answerable by the column being set, not by
        comparing two numbers and hoping the catalog has not moved since.

        `commit=False` lets the caller keep the coupon reservation in the same
        transaction as this row: a slot must never be claimed against a payment
        that rolled back. See PaymentService.start_checkout.
        """
        payment_id = self.db.execute(
            text(
                "INSERT INTO payments "
                "(founder_id, amount_inr, currency, status, payment_gateway, "
                " gateway_order_id, plan_tier, coupon_id, list_amount_inr, discount_inr, "
                " buyer_state) "
                "VALUES (:fid, :amt, :cur, 'pending', :gw, :goid, :tier, :cid, :list, :disc, "
                "        :bstate) "
                "RETURNING payment_id"
            ),
            {"fid": founder_id, "amt": amount_inr, "cur": currency, "gw": gateway,
             "goid": gateway_order_id, "tier": plan_tier, "cid": coupon_id,
             "list": list_amount_inr, "disc": discount_inr, "bstate": buyer_state},
        ).scalar()
        if commit:
            self.db.commit()
        return payment_id

    def attach_coupon(self, payment_id: int, *, coupon_id: int, discount_inr: int) -> None:
        """Point the payment at the coupon that discounted it, and commit the
        payment + reservation together. Called only after CouponService.reserve
        has claimed the slot in this same transaction."""
        self.db.execute(
            text("UPDATE payments SET coupon_id = :cid, discount_inr = :disc "
                 "WHERE payment_id = :pid"),
            {"cid": coupon_id, "disc": discount_inr, "pid": payment_id},
        )
        self.db.commit()

    def get_by_gateway_order_id(self, gateway_order_id: str) -> PaymentRecord | None:
        row = self.db.execute(
            text(
                "SELECT payment_id, founder_id, status, gateway_order_id, "
                "       gateway_payment_id, amount_inr, subscription_id, plan_tier "
                "FROM payments WHERE gateway_order_id = :goid"
            ),
            {"goid": gateway_order_id},
        ).mappings().first()
        return _to_record(row)

    def get_by_gateway_payment_id(self, gateway_payment_id: str) -> PaymentRecord | None:
        """The idempotency check: Razorpay retries webhook deliveries, and a
        `gateway_payment_id` already recorded here means this exact payment
        has already been granted -- never grant a plan or credits twice for
        the same payment."""
        row = self.db.execute(
            text(
                "SELECT payment_id, founder_id, status, gateway_order_id, "
                "       gateway_payment_id, amount_inr, subscription_id, plan_tier "
                "FROM payments WHERE gateway_payment_id = :gpid"
            ),
            {"gpid": gateway_payment_id},
        ).mappings().first()
        return _to_record(row)

    def mark_captured(
        self, payment_id: int, *, gateway_payment_id: str, paid_at: datetime,
        subscription_id: int,
    ) -> None:
        self.db.execute(
            text(
                "UPDATE payments SET status = 'success', gateway_payment_id = :gpid, "
                "                    paid_at = :at, subscription_id = :sid "
                "WHERE payment_id = :pid"
            ),
            {"gpid": gateway_payment_id, "at": paid_at, "sid": subscription_id, "pid": payment_id},
        )
        self.db.commit()

    def mark_failed(self, payment_id: int, *, reason: str) -> None:
        self.db.execute(
            text("UPDATE payments SET status = 'failed', failure_reason = :reason "
                 "WHERE payment_id = :pid"),
            {"reason": reason, "pid": payment_id},
        )
        self.db.commit()

    # --- invoices / receipts -----------------------------------------------

    #: One projection, two callers (the list and the single document), so a
    #: receipt can never show a figure the billing history disagrees with.
    #: LEFT JOINs throughout: a payment with no coupon and a payment whose
    #: subscription row is missing must both still produce a document.
    _INVOICE_SELECT = (
        "SELECT p.payment_id, p.founder_id, p.status, p.amount_inr, p.currency, "
        "       p.plan_tier, p.gateway_order_id, p.gateway_payment_id, p.paid_at, "
        "       p.created_at, p.invoice_number, p.list_amount_inr, p.discount_inr, "
        "       p.buyer_state, "
        "       c.code AS coupon_code, s.billing_cycle "
        "FROM payments p "
        "LEFT JOIN coupons c ON c.coupon_id = p.coupon_id "
        "LEFT JOIN subscriptions s ON s.subscription_id = p.subscription_id "
    )

    def list_invoiceable(self, founder_id: int, *, limit: int = 50) -> list[InvoiceSource]:
        """This founder's billing history, newest first.

        Only captured and refunded payments. A pending row is a checkout that
        was abandoned or is still settling, and listing those as billing
        history would show a founder a charge they may never have been made --
        the one thing a payments list must never do.
        """
        rows = self.db.execute(
            text(self._INVOICE_SELECT +
                 "WHERE p.founder_id = :fid AND p.status IN ('success', 'refunded') "
                 "ORDER BY COALESCE(p.paid_at, p.created_at) DESC, p.payment_id DESC "
                 "LIMIT :lim"),
            {"fid": founder_id, "lim": limit},
        ).mappings().all()
        return [_to_invoice_source(r) for r in rows]

    def get_invoice_source(self, payment_id: int, *, founder_id: int) -> InvoiceSource | None:
        """One payment, scoped to its owner IN THE QUERY.

        The founder id is a WHERE clause and not a check the caller is trusted
        to remember: a receipt carries a name, an email and an amount, so a
        route that forgot to compare owners would be handing one founder
        another's billing details. Here that mistake is not reachable.
        """
        row = self.db.execute(
            text(self._INVOICE_SELECT + "WHERE p.payment_id = :pid AND p.founder_id = :fid"),
            {"pid": payment_id, "fid": founder_id},
        ).mappings().first()
        return _to_invoice_source(row) if row else None

    def founder_identity(self, founder_id: int) -> dict:
        """The name and email a receipt is addressed to.

        Falls back to empty strings rather than raising: a founder row that is
        mid-deletion, or one whose name was never captured, must still be able
        to download a receipt for money they actually paid. A receipt with a
        blank name is a small problem; one that 500s is a founder who cannot
        expense a charge.
        """
        row = self.db.execute(
            text("SELECT full_name, email FROM founders WHERE founder_id = :fid"),
            {"fid": founder_id},
        ).mappings().first()
        if row is None:
            return {"full_name": "", "email": ""}
        return {"full_name": row["full_name"] or "", "email": row["email"] or ""}

    def record_invoice_number(self, payment_id: int, *, founder_id: int,
                              number: str) -> None:
        """Write the issued number down, once.

        `WHERE invoice_number IS NULL` makes this first-write-wins: two
        concurrent downloads of the same receipt cannot renumber it, and a
        later change to the derivation rule cannot renumber an invoice a
        founder already holds a copy of.

        The founder id is in the WHERE clause for the same reason it is on the
        read: the database's own founder-isolation policy already covers this
        (migration d91c6e4b72aa), but that policy is scoped to the `ally_app`
        role and is skipped wherever the role does not exist. A write that is
        only safe because of a policy that might not be installed is a write
        worth scoping here too.
        """
        self.db.execute(
            text("UPDATE payments SET invoice_number = :num "
                 "WHERE payment_id = :pid AND founder_id = :fid "
                 "  AND invoice_number IS NULL"),
            {"num": number, "pid": payment_id, "fid": founder_id},
        )
        self.db.commit()

    def record_invoice_url(self, payment_id: int, *, founder_id: int, url: str) -> None:
        """Point the payment at its stored PDF. Best-effort by design: the
        document is correct with or without this, the pointer only makes the
        next download a fetch instead of a render. Scoped by founder for the
        same reason as record_invoice_number above."""
        self.db.execute(
            text("UPDATE payments SET invoice_url = :url "
                 "WHERE payment_id = :pid AND founder_id = :fid"),
            {"url": url, "pid": payment_id, "fid": founder_id},
        )
        self.db.commit()

    def invoice_storage_key(self, payment_id: int, *, founder_id: int) -> str | None:
        row = self.db.execute(
            text("SELECT invoice_url FROM payments "
                 "WHERE payment_id = :pid AND founder_id = :fid"),
            {"pid": payment_id, "fid": founder_id},
        ).mappings().first()
        return row["invoice_url"] if row else None

    # --- subscriptions + the plan itself ------------------------------------

    def create_subscription(
        self, *, founder_id: int, plan_type: str, amount_inr: int, billing_cycle: str,
        expires_at: datetime | None, gateway: str,
    ) -> int:
        subscription_id = self.db.execute(
            text(
                "INSERT INTO subscriptions "
                "(founder_id, plan_type, status, billing_cycle, amount_inr, "
                " expires_at, payment_gateway) "
                "VALUES (:fid, :plan, 'active', :cycle, :amt, :exp, :gw) "
                "RETURNING subscription_id"
            ),
            {"fid": founder_id, "plan": plan_type, "cycle": billing_cycle, "amt": amount_inr,
             "exp": expires_at, "gw": gateway},
        ).scalar()
        self.db.commit()
        return subscription_id

    def grant_plan(self, founder_id: int, plan_type: str) -> None:
        """The actual upgrade -- same column `PATCH /admin/users/{id}/subscription`
        writes, so a founder's entitlements read the same way regardless of
        whether an admin or a real payment put them there."""
        self.db.execute(
            text("UPDATE founders SET plan_type = :plan, updated_at = now() "
                 "WHERE founder_id = :fid"),
            {"plan": plan_type, "fid": founder_id},
        )
        self.db.commit()


def _to_record(row) -> PaymentRecord | None:
    if row is None:
        return None
    return PaymentRecord(
        payment_id=row["payment_id"], founder_id=row["founder_id"], status=row["status"],
        gateway_order_id=row["gateway_order_id"], gateway_payment_id=row["gateway_payment_id"],
        amount_inr=row["amount_inr"], subscription_id=row["subscription_id"],
        plan_tier=row["plan_tier"] if "plan_tier" in row.keys() else None,
    )


def _to_invoice_source(row) -> InvoiceSource:
    return InvoiceSource(
        payment_id=row["payment_id"], founder_id=row["founder_id"], status=row["status"],
        amount_inr=row["amount_inr"], currency=row["currency"], plan_tier=row["plan_tier"],
        gateway_order_id=row["gateway_order_id"],
        gateway_payment_id=row["gateway_payment_id"],
        paid_at=row["paid_at"], created_at=row["created_at"],
        invoice_number=row["invoice_number"],
        list_amount_inr=row["list_amount_inr"], discount_inr=row["discount_inr"],
        coupon_code=row["coupon_code"], billing_cycle=row["billing_cycle"],
        buyer_state=row["buyer_state"],
    )
