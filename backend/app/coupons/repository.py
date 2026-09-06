"""Raw-SQL reads/writes for coupons -- same style as app/payments/repository.py:
parameterised text() queries, explicit columns, no ORM model for these tables.

The one subtlety worth reading before changing anything here: `count_live_
redemptions` deliberately does NOT count every row. A `pending` row older than
PENDING_TTL_MINUTES is a checkout somebody opened and walked away from, and if
those counted forever a "first 100" code would be exhausted by 100 people who
never paid. Razorpay fires payment.failed for a genuine failure and we release
the row then; this TTL is the backstop for the founder who simply closed the
tab, which the gateway never tells us about.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.coupons.models import Coupon, RedemptionStatus

# Generous on purpose. A founder switching to their banking app, failing 3DS
# once and retrying is well inside this; a tab closed an hour ago is not.
PENDING_TTL_MINUTES = 30

_LIVE_REDEMPTION_PREDICATE = (
    "(status = 'confirmed' "
    " OR (status = 'pending' "
    f"     AND created_at > now() - interval '{PENDING_TTL_MINUTES} minutes'))"
)

_COUPON_COLUMNS = (
    "coupon_id, code, description, discount_type, discount_value, applies_to, "
    "max_redemptions, max_per_founder, valid_from, valid_until, is_active"
)


class CouponRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- reads --------------------------------------------------------------

    def get_by_code(self, code: str) -> Coupon | None:
        row = self.db.execute(
            text(f"SELECT {_COUPON_COLUMNS} FROM coupons WHERE code = :code"),
            {"code": code},
        ).mappings().first()
        return _to_coupon(row)

    def get_by_id(self, coupon_id: int) -> Coupon | None:
        row = self.db.execute(
            text(f"SELECT {_COUPON_COLUMNS} FROM coupons WHERE coupon_id = :cid"),
            {"cid": coupon_id},
        ).mappings().first()
        return _to_coupon(row)

    def count_live_redemptions(self, coupon_id: int) -> int:
        """Confirmed redemptions plus in-flight ones. See the module note."""
        return self.db.execute(
            text(f"SELECT count(*) FROM coupon_redemptions "
                 f"WHERE coupon_id = :cid AND {_LIVE_REDEMPTION_PREDICATE}"),
            {"cid": coupon_id},
        ).scalar() or 0

    def count_live_redemptions_by_founder(self, coupon_id: int, founder_id: int) -> int:
        return self.db.execute(
            text(f"SELECT count(*) FROM coupon_redemptions "
                 f"WHERE coupon_id = :cid AND founder_id = :fid "
                 f"AND {_LIVE_REDEMPTION_PREDICATE}"),
            {"cid": coupon_id, "fid": founder_id},
        ).scalar() or 0

    # --- redemption lifecycle ----------------------------------------------

    def reserve(self, *, coupon_id: int, founder_id: int, payment_id: int,
                discount_inr: int) -> int:
        """Claim a slot, pending payment. Written in the SAME transaction as the
        payment row it points at, so a founder can never hold a slot against a
        payment that does not exist."""
        redemption_id = self.db.execute(
            text("INSERT INTO coupon_redemptions "
                 "(coupon_id, founder_id, payment_id, status, discount_inr) "
                 "VALUES (:cid, :fid, :pid, 'pending', :disc) "
                 "RETURNING redemption_id"),
            {"cid": coupon_id, "fid": founder_id, "pid": payment_id, "disc": discount_inr},
        ).scalar()
        return redemption_id

    def confirm_for_payment(self, payment_id: int, *, at: datetime) -> None:
        """Razorpay captured the payment: the slot is spent for good."""
        self.db.execute(
            text("UPDATE coupon_redemptions SET status = 'confirmed', confirmed_at = :at "
                 "WHERE payment_id = :pid AND status = 'pending'"),
            {"at": at, "pid": payment_id},
        )

    def release_for_payment(self, payment_id: int) -> None:
        """The payment failed: hand the slot back immediately rather than
        waiting out the TTL. On a code with a hard cap that difference is the
        founder behind them getting in."""
        self.db.execute(
            text("UPDATE coupon_redemptions SET status = 'released' "
                 "WHERE payment_id = :pid AND status = 'pending'"),
            {"pid": payment_id},
        )

    # --- admin --------------------------------------------------------------

    def list_with_usage(self, *, include_inactive: bool, limit: int, offset: int) -> list[dict]:
        where = "" if include_inactive else "WHERE c.is_active"
        rows = self.db.execute(
            text(f"""
                SELECT c.coupon_id, c.code, c.description, c.discount_type,
                       c.discount_value, c.applies_to, c.max_redemptions,
                       c.max_per_founder, c.valid_from, c.valid_until, c.is_active,
                       c.created_at,
                       count(r.redemption_id) FILTER (
                           WHERE r.status = 'confirmed') AS confirmed_count,
                       count(r.redemption_id) FILTER (
                           WHERE r.status = 'pending'
                             AND r.created_at > now()
                                 - interval '{PENDING_TTL_MINUTES} minutes'
                       ) AS pending_count,
                       COALESCE(sum(r.discount_inr) FILTER (
                           WHERE r.status = 'confirmed'), 0) AS discount_given_inr
                FROM coupons c
                LEFT JOIN coupon_redemptions r ON r.coupon_id = c.coupon_id
                {where}
                GROUP BY c.coupon_id
                ORDER BY c.created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {"limit": limit, "offset": offset},
        ).mappings().all()
        return [dict(r) for r in rows]

    def create(self, *, code: str, description: str | None, discount_type: str,
               discount_value: int, applies_to: list[str] | None,
               max_redemptions: int | None, max_per_founder: int,
               valid_from: datetime | None, valid_until: datetime,
               admin_id: int) -> int:
        coupon_id = self.db.execute(
            text("INSERT INTO coupons "
                 "(code, description, discount_type, discount_value, applies_to, "
                 " max_redemptions, max_per_founder, valid_from, valid_until, "
                 " created_by_admin_id) "
                 "VALUES (:code, :descr, :dtype, :dval, :applies, :maxr, :maxf, "
                 "        COALESCE(:vfrom, now()), :vuntil, :admin) "
                 "RETURNING coupon_id"),
            {"code": code, "descr": description, "dtype": discount_type,
             "dval": discount_value, "applies": applies_to, "maxr": max_redemptions,
             "maxf": max_per_founder, "vfrom": valid_from, "vuntil": valid_until,
             "admin": admin_id},
        ).scalar()
        self.db.commit()
        return coupon_id

    def update(self, coupon_id: int, **fields) -> bool:
        """Partial update of the few fields it is safe to change after issue.

        Deliberately narrow: the code, the discount and who it applies to are
        fixed once anyone could have seen the coupon. Changing what a code is
        worth after a founder has been told is not an edit, it is a different
        promise.
        """
        allowed = {"description", "max_redemptions", "max_per_founder",
                   "valid_until", "is_active"}
        sets = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not sets:
            return False
        assignments = ", ".join(f"{k} = :{k}" for k in sets)
        result = self.db.execute(
            text(f"UPDATE coupons SET {assignments}, updated_at = now() "
                 f"WHERE coupon_id = :cid"),
            {**sets, "cid": coupon_id},
        )
        self.db.commit()
        return result.rowcount > 0

    def redemptions_for(self, coupon_id: int, *, limit: int) -> list[dict]:
        rows = self.db.execute(
            text("""SELECT r.redemption_id, r.founder_id, f.email, f.full_name,
                           r.payment_id, r.status, r.discount_inr,
                           r.created_at, r.confirmed_at
                    FROM coupon_redemptions r
                    LEFT JOIN founders f ON f.founder_id = r.founder_id
                    WHERE r.coupon_id = :cid
                    ORDER BY r.created_at DESC
                    LIMIT :limit"""),
            {"cid": coupon_id, "limit": limit},
        ).mappings().all()
        return [dict(r) for r in rows]


def _to_coupon(row) -> Coupon | None:
    if row is None:
        return None
    return Coupon(
        coupon_id=row["coupon_id"],
        code=row["code"],
        description=row["description"],
        discount_type=row["discount_type"],
        discount_value=int(row["discount_value"]),
        applies_to=list(row["applies_to"]) if row["applies_to"] else None,
        max_redemptions=row["max_redemptions"],
        max_per_founder=int(row["max_per_founder"]),
        valid_from=row["valid_from"],
        valid_until=row["valid_until"],
        is_active=bool(row["is_active"]),
    )
