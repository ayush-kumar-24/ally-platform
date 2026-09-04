"""Coupons and discounts -- definition, validation, redemption ledger.

A coupon here is a *rule*, not money. This module owns three questions and
nothing else:

    1. What discounts exist?              (the `coupons` table)
    2. May THIS founder use THIS code?    (`CouponService.validate`)
    3. Who has already used it?           (the `coupon_redemptions` ledger)

Applying the discount to an invoice is deliberately out of scope: there is no
payment provider wired into this codebase yet, so a "discount" that pretended to
change what someone is charged would be fiction. When checkout arrives it calls
`validate` and reads `CouponValidation.discount_*` -- the ledger row is written by
`redeem` at the moment the order is accepted, not before.

Two rules the design turns on:

* **Integers only.** `discount_value` is a percentage (1-100), a fixed amount in
  the currency's MINOR unit (paise), a credit count, or a number of free days --
  which one is decided by `discount_type`. Money is never a float here, so a
  discount can never round differently on two machines.

* **The ledger is the count.** `coupons.redeemed_count` is a cached convenience
  column; the truth is the number of rows in `coupon_redemptions`. `redeem`
  re-counts from the ledger inside the same transaction before it accepts, so two
  concurrent redemptions of the last remaining use cannot both win.

Validation fails closed: an unknown code, an expired window, an exhausted cap and
a wrong-plan code all return `valid=False` with a reason a human can act on.
"""

from __future__ import annotations

import abc
import re
import threading
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.admin.errors import AdminError
from app.db.session import Base

#: Codes are stored and compared upper-case so "welcome10" and "WELCOME10" are the
#: same coupon -- a founder typing it out of an email should not be able to miss.
CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,39}$")

MAX_DESCRIPTION = 300


class CouponError(AdminError):
    """Base for coupon failures."""


class InvalidCouponError(CouponError):
    def __init__(self, reason: str):
        super().__init__(f"Invalid coupon: {reason}.", status_code=422)


class CouponNotFoundError(CouponError):
    def __init__(self, code: str):
        super().__init__(f"Coupon '{code}' was not found.", status_code=404)


class DuplicateCouponError(CouponError):
    def __init__(self, code: str):
        super().__init__(f"Coupon '{code}' already exists.", status_code=409)


class CouponRejectedError(CouponError):
    """Redemption refused -- expired, exhausted, already used, wrong plan."""

    def __init__(self, reason: str):
        super().__init__(f"This coupon cannot be used: {reason}.", status_code=409)


class DiscountType(str, Enum):
    #: value is 1-100, applied to the order total.
    PERCENT = "percent"
    #: value is an absolute amount in the currency's minor unit (paise).
    FIXED = "fixed"
    #: value is a number of Ally credits granted on redemption.
    CREDITS = "credits"
    #: value is a number of days of the plan given free.
    FREE_DAYS = "free_days"


@dataclass(frozen=True)
class Coupon:
    code: str
    discount_type: DiscountType
    discount_value: int
    description: str = ""
    #: Empty list means "every plan". Plan codes match `founders.plan_type`.
    applies_to_plans: list[str] = field(default_factory=list)
    #: None means unlimited across all founders.
    max_redemptions: int | None = None
    #: How many times ONE founder may use it. 1 is the sane default for a promo.
    max_per_founder: int = 1
    redeemed_count: int = 0
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    active: bool = True
    created_by: int | None = None
    created_at: datetime | None = None

    def window_contains(self, at: datetime) -> bool:
        if self.starts_at and at < self.starts_at:
            return False
        if self.expires_at and at >= self.expires_at:
            return False
        return True

    def covers_plan(self, plan: str | None) -> bool:
        """Fails closed on an unnamed plan.

        A plan-restricted coupon validated without a plan is a caller that forgot
        to say what is being bought. Answering "valid" there would let a Pro-only
        code through a checkout that never told us it was selling Starter, so an
        absent plan is treated as a plan the coupon does not cover.
        """
        if not self.applies_to_plans:
            return True
        return (plan or "").lower() in {p.lower() for p in self.applies_to_plans}


@dataclass(frozen=True)
class CouponRedemption:
    redemption_id: str
    code: str
    founder_id: int
    redeemed_at: datetime
    #: Where the redemption came from -- "checkout", "beta_invite", "admin".
    context: str = "checkout"


@dataclass(frozen=True)
class CouponValidation:
    """The answer to "may this founder use this code, right now?".

    Carries the discount so a caller never has to re-read the coupon to find out
    what to apply, and carries `reason` so a rejected code can be explained rather
    than just refused.
    """

    valid: bool
    code: str
    reason: str | None = None
    discount_type: DiscountType | None = None
    discount_value: int | None = None
    description: str = ""

    @property
    def label(self) -> str:
        """Human-readable discount, e.g. "20% off" -- for the UI and invite emails."""
        if not self.valid or self.discount_value is None:
            return ""
        return describe_discount(self.discount_type, self.discount_value)


def describe_discount(discount_type: DiscountType | None, value: int | None) -> str:
    if discount_type is None or value is None:
        return ""
    if discount_type is DiscountType.PERCENT:
        return f"{value}% off"
    if discount_type is DiscountType.FIXED:
        # Stored in paise; shown in rupees. Whole rupees when it divides evenly,
        # because "Rs 500.00 off" reads like a rounding artefact.
        rupees = value / 100
        amount = f"{rupees:,.0f}" if value % 100 == 0 else f"{rupees:,.2f}"
        return f"Rs {amount} off"
    if discount_type is DiscountType.CREDITS:
        return f"{value:,} bonus credits"
    return f"{value} days free"


def normalise_code(code: str) -> str:
    return (code or "").strip().upper()


# --- storage ----------------------------------------------------------------

class CouponRow(Base):
    __tablename__ = "coupons"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    discount_type: Mapped[str] = mapped_column(String(20), nullable=False)
    discount_value: Mapped[int] = mapped_column(Integer, nullable=False)
    applies_to_plans: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    max_redemptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_per_founder: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    redeemed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())


class CouponRedemptionRow(Base):
    __tablename__ = "coupon_redemptions"

    redemption_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    code: Mapped[str] = mapped_column(
        String(40), ForeignKey("coupons.code", ondelete="CASCADE"), nullable=False, index=True)
    founder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("founders.founder_id", ondelete="CASCADE"),
        nullable=False, index=True)
    context: Mapped[str] = mapped_column(String(30), nullable=False, server_default="checkout")
    redeemed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())


class CouponRepository(abc.ABC):
    @abc.abstractmethod
    def create(self, coupon: Coupon) -> Coupon: ...

    @abc.abstractmethod
    def get(self, code: str) -> Coupon | None: ...

    @abc.abstractmethod
    def list(self, *, include_inactive: bool = True, limit: int = 100,
             offset: int = 0) -> tuple[list[Coupon], int]: ...

    @abc.abstractmethod
    def update(self, code: str, **changes) -> Coupon | None:
        """Patch the mutable fields. Unknown codes return None rather than raising."""

    @abc.abstractmethod
    def count_redemptions(self, code: str, *, founder_id: int | None = None) -> int:
        """Read the ledger. This -- not `redeemed_count` -- is the authority."""

    @abc.abstractmethod
    def record_redemption(self, redemption: CouponRedemption) -> CouponRedemption: ...

    @abc.abstractmethod
    def list_redemptions(self, code: str, *, limit: int = 100,
                         offset: int = 0) -> tuple[list[CouponRedemption], int]: ...


class InMemoryCouponRepository(CouponRepository):
    def __init__(self, coupons: list[Coupon] | None = None) -> None:
        self._coupons: dict[str, Coupon] = {c.code: c for c in (coupons or [])}
        self._redemptions: list[CouponRedemption] = []
        self._lock = threading.RLock()

    def create(self, coupon: Coupon) -> Coupon:
        with self._lock:
            if coupon.code in self._coupons:
                raise DuplicateCouponError(coupon.code)
            self._coupons[coupon.code] = coupon
            return coupon

    def get(self, code: str) -> Coupon | None:
        with self._lock:
            return self._coupons.get(code)

    def list(self, *, include_inactive=True, limit=100, offset=0):
        with self._lock:
            rows = sorted(self._coupons.values(),
                          key=lambda c: (c.created_at or datetime.min.replace(
                              tzinfo=timezone.utc), c.code), reverse=True)
        if not include_inactive:
            rows = [c for c in rows if c.active]
        return rows[offset:offset + limit], len(rows)

    def update(self, code: str, **changes) -> Coupon | None:
        with self._lock:
            existing = self._coupons.get(code)
            if existing is None:
                return None
            updated = replace(existing, **changes)
            self._coupons[code] = updated
            return updated

    def count_redemptions(self, code: str, *, founder_id: int | None = None) -> int:
        with self._lock:
            return sum(1 for r in self._redemptions
                       if r.code == code
                       and (founder_id is None or r.founder_id == founder_id))

    def record_redemption(self, redemption: CouponRedemption) -> CouponRedemption:
        with self._lock:
            self._redemptions.append(redemption)
            coupon = self._coupons.get(redemption.code)
            if coupon is not None:
                self._coupons[redemption.code] = replace(
                    coupon, redeemed_count=coupon.redeemed_count + 1)
            return redemption

    def list_redemptions(self, code: str, *, limit=100, offset=0):
        with self._lock:
            rows = [r for r in self._redemptions if r.code == code]
        rows.sort(key=lambda r: r.redeemed_at, reverse=True)
        return rows[offset:offset + limit], len(rows)


class SqlAlchemyCouponRepository(CouponRepository):
    def __init__(self, db):
        self.db = db

    def create(self, coupon: Coupon) -> Coupon:
        if self.db.query(CouponRow).filter(CouponRow.code == coupon.code).first():
            raise DuplicateCouponError(coupon.code)
        self.db.add(CouponRow(
            code=coupon.code, description=coupon.description,
            discount_type=coupon.discount_type.value, discount_value=coupon.discount_value,
            applies_to_plans=coupon.applies_to_plans or None,
            max_redemptions=coupon.max_redemptions, max_per_founder=coupon.max_per_founder,
            redeemed_count=coupon.redeemed_count, starts_at=coupon.starts_at,
            expires_at=coupon.expires_at, active=coupon.active,
            created_by=coupon.created_by, created_at=coupon.created_at))
        self.db.commit()
        return coupon

    def get(self, code: str) -> Coupon | None:
        row = self.db.query(CouponRow).filter(CouponRow.code == code).first()
        return _to_coupon(row) if row else None

    def list(self, *, include_inactive=True, limit=100, offset=0):
        q = self.db.query(CouponRow)
        if not include_inactive:
            q = q.filter(CouponRow.active.is_(True))
        total = q.count()
        rows = (q.order_by(CouponRow.created_at.desc(), CouponRow.code.desc())
                 .limit(limit).offset(offset).all())
        return [_to_coupon(r) for r in rows], total

    def update(self, code: str, **changes) -> Coupon | None:
        row = self.db.query(CouponRow).filter(CouponRow.code == code).first()
        if row is None:
            return None
        for key, value in changes.items():
            if key == "discount_type" and value is not None:
                value = value.value
            if key == "applies_to_plans":
                value = value or None
            setattr(row, key, value)
        self.db.commit()
        return _to_coupon(row)

    def count_redemptions(self, code: str, *, founder_id: int | None = None) -> int:
        q = self.db.query(CouponRedemptionRow).filter(CouponRedemptionRow.code == code)
        if founder_id is not None:
            q = q.filter(CouponRedemptionRow.founder_id == founder_id)
        return q.count()

    def record_redemption(self, redemption: CouponRedemption) -> CouponRedemption:
        self.db.add(CouponRedemptionRow(
            redemption_id=redemption.redemption_id, code=redemption.code,
            founder_id=redemption.founder_id, context=redemption.context,
            redeemed_at=redemption.redeemed_at))
        # Keep the cached counter in step with the ledger inside the same
        # transaction. It is a display convenience; `count_redemptions` above
        # is what any limit check actually reads.
        (self.db.query(CouponRow)
             .filter(CouponRow.code == redemption.code)
             .update({CouponRow.redeemed_count: CouponRow.redeemed_count + 1},
                     synchronize_session=False))
        self.db.commit()
        return redemption

    def list_redemptions(self, code: str, *, limit=100, offset=0):
        q = self.db.query(CouponRedemptionRow).filter(CouponRedemptionRow.code == code)
        total = q.count()
        rows = (q.order_by(CouponRedemptionRow.redeemed_at.desc())
                 .limit(limit).offset(offset).all())
        return [CouponRedemption(
            redemption_id=r.redemption_id, code=r.code, founder_id=r.founder_id,
            context=r.context, redeemed_at=r.redeemed_at) for r in rows], total


def _to_coupon(row: CouponRow) -> Coupon:
    return Coupon(
        code=row.code, description=row.description or "",
        discount_type=DiscountType(row.discount_type), discount_value=row.discount_value,
        applies_to_plans=list(row.applies_to_plans or []),
        max_redemptions=row.max_redemptions, max_per_founder=row.max_per_founder,
        redeemed_count=row.redeemed_count, starts_at=row.starts_at,
        expires_at=row.expires_at, active=row.active, created_by=row.created_by,
        created_at=row.created_at)


# --- service ----------------------------------------------------------------

class CouponService:
    def __init__(self, repository: CouponRepository, *, clock=None, id_factory=None):
        self.repository = repository
        self._now = clock or (lambda: datetime.now(timezone.utc))
        self._new_id = id_factory or (lambda: uuid.uuid4().hex)

    # -- authoring ----------------------------------------------------------

    def create(self, *, code: str, discount_type: DiscountType, discount_value: int,
               description: str = "", applies_to_plans: list[str] | None = None,
               max_redemptions: int | None = None, max_per_founder: int = 1,
               starts_at: datetime | None = None, expires_at: datetime | None = None,
               admin_id: int | None = None) -> Coupon:
        code = normalise_code(code)
        if not CODE_PATTERN.match(code):
            raise InvalidCouponError(
                "a code must be 3-40 characters of A-Z, 0-9, hyphen or underscore, "
                "starting with a letter or digit")
        if len(description) > MAX_DESCRIPTION:
            raise InvalidCouponError(
                f"the description may not exceed {MAX_DESCRIPTION} characters")
        _check_value(discount_type, discount_value)
        if max_redemptions is not None and max_redemptions < 1:
            raise InvalidCouponError("max_redemptions must be at least 1 when set")
        if max_per_founder < 1:
            raise InvalidCouponError("max_per_founder must be at least 1")
        if starts_at and expires_at and expires_at <= starts_at:
            raise InvalidCouponError("expires_at must be after starts_at")

        return self.repository.create(Coupon(
            code=code, discount_type=discount_type, discount_value=discount_value,
            description=description.strip(),
            applies_to_plans=[p.strip().lower() for p in (applies_to_plans or []) if p.strip()],
            max_redemptions=max_redemptions, max_per_founder=max_per_founder,
            starts_at=starts_at, expires_at=expires_at, active=True,
            created_by=admin_id, created_at=self._now()))

    def get(self, code: str) -> Coupon | None:
        return self.repository.get(normalise_code(code))

    def list(self, *, include_inactive: bool = True, limit: int = 100,
             offset: int = 0) -> tuple[list[Coupon], int]:
        return self.repository.list(include_inactive=include_inactive,
                                    limit=limit, offset=offset)

    def update(self, code: str, *, active: bool | None = None,
               description: str | None = None, max_redemptions: int | None = None,
               clear_max_redemptions: bool = False,
               expires_at: datetime | None = None,
               clear_expires_at: bool = False) -> Coupon:
        """Patch the safe-to-change fields.

        The discount itself is NOT editable. A code someone already redeemed at
        20% must keep meaning 20%: silently re-pointing it at a different value
        would rewrite what past redemptions were worth. Retire the code and issue
        a new one instead.
        """
        code = normalise_code(code)
        changes: dict = {}
        if active is not None:
            changes["active"] = active
        if description is not None:
            if len(description) > MAX_DESCRIPTION:
                raise InvalidCouponError(
                    f"the description may not exceed {MAX_DESCRIPTION} characters")
            changes["description"] = description.strip()
        if clear_max_redemptions:
            changes["max_redemptions"] = None
        elif max_redemptions is not None:
            if max_redemptions < 1:
                raise InvalidCouponError("max_redemptions must be at least 1 when set")
            changes["max_redemptions"] = max_redemptions
        if clear_expires_at:
            changes["expires_at"] = None
        elif expires_at is not None:
            changes["expires_at"] = expires_at

        updated = self.repository.update(code, **changes) if changes else self.repository.get(code)
        if updated is None:
            raise CouponNotFoundError(code)
        return updated

    # -- use ----------------------------------------------------------------

    def validate(self, code: str, *, founder_id: int | None = None,
                 plan: str | None = None, at: datetime | None = None) -> CouponValidation:
        """Never raises for a bad code -- a rejection is an answer, not an error.

        Callers that need a hard failure (redemption) get one from `redeem`.
        """
        code = normalise_code(code)
        at = at or self._now()
        coupon = self.repository.get(code)
        if coupon is None:
            return CouponValidation(False, code, reason="this code does not exist")
        if not coupon.active:
            return CouponValidation(False, code, reason="this code is no longer active")
        if coupon.starts_at and at < coupon.starts_at:
            return CouponValidation(False, code, reason="this code is not active yet")
        if coupon.expires_at and at >= coupon.expires_at:
            return CouponValidation(False, code, reason="this code has expired")
        if not coupon.covers_plan(plan):
            reason = ("this code does not apply to the selected plan" if plan
                      else "this code only applies to "
                           + ", ".join(sorted(coupon.applies_to_plans)))
            return CouponValidation(False, code, reason=reason)
        if coupon.max_redemptions is not None:
            if self.repository.count_redemptions(code) >= coupon.max_redemptions:
                return CouponValidation(False, code, reason="this code has been fully claimed")
        if founder_id is not None:
            used = self.repository.count_redemptions(code, founder_id=founder_id)
            if used >= coupon.max_per_founder:
                return CouponValidation(False, code, reason="you have already used this code")
        return CouponValidation(
            True, code, discount_type=coupon.discount_type,
            discount_value=coupon.discount_value, description=coupon.description)

    def redeem(self, code: str, founder_id: int, *, plan: str | None = None,
               context: str = "checkout", at: datetime | None = None) -> CouponRedemption:
        """Consume one use. Re-validates first: the gap between a UI's validate call
        and its redeem call is exactly where a last-remaining-use race lives."""
        at = at or self._now()
        result = self.validate(code, founder_id=founder_id, plan=plan, at=at)
        if not result.valid:
            raise CouponRejectedError(result.reason or "it is not valid")
        return self.repository.record_redemption(CouponRedemption(
            redemption_id=self._new_id(), code=result.code, founder_id=founder_id,
            context=context, redeemed_at=at))

    def list_redemptions(self, code: str, *, limit: int = 100,
                         offset: int = 0) -> tuple[list[CouponRedemption], int]:
        return self.repository.list_redemptions(normalise_code(code),
                                                limit=limit, offset=offset)


def _check_value(discount_type: DiscountType, value: int) -> None:
    if value < 1:
        raise InvalidCouponError("the discount value must be at least 1")
    if discount_type is DiscountType.PERCENT and value > 100:
        raise InvalidCouponError("a percentage discount may not exceed 100")
    if discount_type is DiscountType.FREE_DAYS and value > 365:
        raise InvalidCouponError("free days may not exceed 365")


def build_coupon_service(repository: CouponRepository | None = None, *,
                         clock=None, id_factory=None) -> CouponService:
    return CouponService(repository or InMemoryCouponRepository(),
                         clock=clock, id_factory=id_factory)
