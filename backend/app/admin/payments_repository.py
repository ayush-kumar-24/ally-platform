"""Admin-side reads over `payments`.

The table has always been written and never read back. Every checkout inserts a
pending row (`app/payments/repository.py`), the Razorpay webhook marks it
`success` or `failed`, and until now nothing in the Admin Panel selected from it
at all: the dashboard's revenue card summed `subscriptions` instead, and the
user detail page showed a subscription or "No subscription record". So a founder
whose card was declined, or whose payment succeeded at Razorpay but whose
webhook never arrived, left a complete record in the database that nobody
answering their email could see.

Failed and pending rows are the point of this module, not an afterthought. A
successful payment already shows up as a plan the founder is on; the ones worth
a support person's time are exactly the ones that left no other trace.

Same conventions as `users_db_repository.py`: parameterised `text()` queries, an
allowlist for anything that cannot be bound, and a column-availability check so
an environment mid-migration degrades a field instead of failing the request.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text

#: Every status the payment flow writes. Used to validate the filter (a status
#: cannot be bound into `group by`, and an unknown one should be a 422 rather
#: than a silently empty page) and to keep the summary's shape constant even
#: for statuses with no rows yet.
STATUSES = ("pending", "success", "failed", "refunded")

#: Columns added by later migrations. Selecting one the database does not have
#: fails the entire query, so each is emitted as NULL when absent and the row
#: shape stays the same either way.
_OPTIONAL_COLUMNS = ("invoice_url", "invoice_number", "failure_reason", "refunded_at",
                     "coupon_id", "list_amount_inr", "discount_inr", "subscription_id")


def _money(value: Any) -> int | None:
    """Rupees as a whole number. The column is `numeric`, which SQLAlchemy hands
    back as Decimal -- not JSON-serialisable, and not something the UI should be
    formatting itself."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return int(value)
    return int(value)


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


class PaymentsUnavailableError(RuntimeError):
    """The `payments` table could not be read at all.

    Distinct from "no payments yet": the page says "no payments have been
    recorded" for an empty table and "could not read the payments table" for a
    missing one, because those two send an admin looking in completely
    different places.
    """


class AdminPaymentsRepository:
    def __init__(self, db):
        self.db = db
        self._cols: set[str] | None = None

    # --- schema tolerance -------------------------------------------------

    def _available(self) -> set[str]:
        """Column names present on `payments`, cached per request. An empty set
        means the table itself could not be inspected."""
        if self._cols is None:
            try:
                from sqlalchemy import inspect
                self._cols = {c["name"] for c in inspect(self.db.get_bind())
                              .get_columns("payments")}
            except Exception:
                self._cols = set()
        return self._cols

    def _require_table(self) -> set[str]:
        have = self._available()
        if not have:
            raise PaymentsUnavailableError("payments table is not readable")
        return have

    def _select_list(self) -> str:
        have = self._require_table()
        parts = ["p.payment_id", "p.founder_id", "p.amount_inr", "p.currency",
                 "p.status", "p.payment_gateway", "p.gateway_order_id",
                 "p.gateway_payment_id", "p.created_at", "p.paid_at"]
        parts += [f"p.{c}" if c in have else f"null as {c}" for c in _OPTIONAL_COLUMNS]
        return ", ".join(parts)

    # --- helpers ----------------------------------------------------------

    def _filters(self, *, status: str | None, founder_id: int | None, search: str | None,
                 created_after: datetime | None, created_before: datetime | None,
                 ) -> tuple[str, dict]:
        where, params = ["1=1"], {}
        if status:
            if status not in STATUSES:
                raise ValueError(f"unknown payment status: {status}")
            where.append("p.status = :status")
            params["status"] = status
        if founder_id is not None:
            where.append("p.founder_id = :fid")
            params["fid"] = founder_id
        if search:
            term = search.strip()
            # The four things somebody actually pastes into this box: a founder's
            # email or name, or a gateway id off a Razorpay dashboard or a
            # founder's "it says payment failed" screenshot.
            where.append("(f.email ilike :q or f.full_name ilike :q "
                         " or p.gateway_order_id = :q_exact "
                         " or p.gateway_payment_id = :q_exact "
                         " or cast(p.payment_id as text) = :q_exact)")
            params["q"] = f"%{term}%"
            params["q_exact"] = term
        if created_after is not None:
            where.append("p.created_at >= :after")
            params["after"] = created_after
        if created_before is not None:
            where.append("p.created_at <= :before")
            params["before"] = created_before
        return " and ".join(where), params

    def _row(self, r: dict) -> dict:
        """One payment, already shaped for the API.

        `list_amount_inr` / `discount_inr` are NULL on an undiscounted payment
        rather than a copy of the amount (see PaymentRepository.create_pending),
        so a coupon is visible by the fields being set at all.
        """
        return {
            "payment_id": r["payment_id"],
            "founder_id": r["founder_id"],
            "email": r.get("email"),
            "full_name": r.get("full_name"),
            "amount_inr": _money(r["amount_inr"]),
            "list_amount_inr": _money(r.get("list_amount_inr")),
            "discount_inr": _money(r.get("discount_inr")),
            "coupon_code": r.get("coupon_code"),
            "currency": r["currency"],
            "status": r["status"],
            "gateway": r["payment_gateway"],
            "gateway_order_id": r["gateway_order_id"],
            "gateway_payment_id": r["gateway_payment_id"],
            "invoice_number": r.get("invoice_number"),
            "invoice_url": r.get("invoice_url"),
            "failure_reason": r.get("failure_reason"),
            "subscription_id": r.get("subscription_id"),
            "plan_type": r.get("plan_type"),
            "created_at": _iso(r.get("created_at")),
            "paid_at": _iso(r.get("paid_at")),
            "refunded_at": _iso(r.get("refunded_at")),
        }

    # --- reads ------------------------------------------------------------

    def search(self, *, status: str | None = None, founder_id: int | None = None,
               search: str | None = None, created_after: datetime | None = None,
               created_before: datetime | None = None,
               limit: int = 50, offset: int = 0) -> dict:
        # Checked before the first query, not incidentally partway through it:
        # a count against a table that is not there should fail as "cannot
        # read payments", never as a confident zero.
        self._require_table()
        clause, params = self._filters(
            status=status, founder_id=founder_id, search=search,
            created_after=created_after, created_before=created_before)

        total = self.db.execute(
            text("select count(*) from payments p "
                 "left join founders f on f.founder_id = p.founder_id "
                 f"where {clause}"), params).scalar() or 0

        have = self._available()
        # Both joins are LEFT: a payment whose founder row was erased under a
        # DSAR, or which never reached a subscription because it failed, must
        # still appear. An INNER join here would hide precisely the rows this
        # page exists to show.
        coupon_select = "c.code as coupon_code" if "coupon_id" in have else "null as coupon_code"
        coupon_join = ("left join coupons c on c.coupon_id = p.coupon_id"
                       if "coupon_id" in have else "")
        sub_select = "s.plan_type" if "subscription_id" in have else "null as plan_type"
        sub_join = ("left join subscriptions s on s.subscription_id = p.subscription_id"
                    if "subscription_id" in have else "")

        rows = self.db.execute(
            text(f"""select {self._select_list()},
                            f.email, f.full_name, {sub_select}, {coupon_select}
                       from payments p
                       left join founders f on f.founder_id = p.founder_id
                       {sub_join}
                       {coupon_join}
                      where {clause}
                      -- created_at is nullable on this table, so it cannot be
                      -- the sole sort key; payment_id is serial and never null.
                      order by p.created_at desc nulls last, p.payment_id desc
                      limit :limit offset :offset"""),
            {**params, "limit": limit, "offset": offset}).mappings().all()

        return {"total": total, "items": [self._row(dict(r)) for r in rows]}

    def summary(self, *, created_after: datetime | None = None,
                created_before: datetime | None = None) -> dict:
        """Counts and totals per status, plus what discounts cost.

        Every status in `STATUSES` is present in the result even with no rows,
        so "0 failed" renders as a reassuring zero rather than the row simply
        not being there and the reader assuming it was never measured.
        """
        self._require_table()
        clause, params = self._filters(
            status=None, founder_id=None, search=None,
            created_after=created_after, created_before=created_before)

        rows = self.db.execute(
            text(f"""select p.status,
                            count(*) as count,
                            coalesce(sum(p.amount_inr), 0) as amount_inr
                       from payments p
                       left join founders f on f.founder_id = p.founder_id
                      where {clause}
                      group by p.status"""), params).mappings().all()

        # A status this code has never heard of lands in here alongside the
        # known ones rather than being dropped: an unrecognised status in a
        # payments table is a thing to go and look at, not to hide.
        by_status = {s: {"count": 0, "amount_inr": 0} for s in STATUSES}
        for r in rows:
            by_status[r["status"]] = {"count": r["count"],
                                      "amount_inr": _money(r["amount_inr"]) or 0}

        have = self._available()
        discount = 0
        if "discount_inr" in have:
            discount = _money(self.db.execute(
                text(f"""select coalesce(sum(p.discount_inr), 0) from payments p
                          left join founders f on f.founder_id = p.founder_id
                         where {clause} and p.status = 'success'"""),
                params).scalar()) or 0

        return {
            "by_status": by_status,
            "captured_inr": by_status.get("success", {}).get("amount_inr", 0),
            "discount_given_inr": discount,
            "total_payments": sum(v["count"] for v in by_status.values()),
        }

    def for_founder(self, founder_id: int, *, limit: int = 50) -> list[dict]:
        return self.search(founder_id=founder_id, limit=limit)["items"]
