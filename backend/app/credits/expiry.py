"""Credit lifecycle: monthly credits expire and renew; bonus credits persist.

The model
---------
Two buckets per founder:

* **monthly** — granted by the plan, use-it-or-lose-it, cleared at `expires_at`.
* **bonus**   — goodwill / promotional grants that survive renewal.

Spend order is **monthly first**. If bonus were spent first, a user's monthly
allowance would quietly expire unused while their permanent credits drained — the
worst outcome for them and the one they'd least expect.

Settlement, not scheduling
--------------------------
Expiry is applied *lazily*: any read or write first calls `settle`, which appends
the `expire` (and, if the renewal date has passed, `renew`) ledger rows that are due.

This is deliberate. A nightly cron that expires credits has three failure modes — it
doesn't run, it runs twice, or it runs late — and each leaves the balance wrong in a
way users notice. Settling on access means the balance is correct the moment anyone
looks at it, and correctness doesn't depend on a scheduler existing at all.

Settlement is idempotent: it is driven by comparing timestamps to `now`, so calling
it repeatedly in the same instant produces no extra rows.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum


class CreditBucket(str, Enum):
    MONTHLY = "monthly"
    BONUS = "bonus"


@dataclass(frozen=True)
class CreditState:
    """A founder's credit position at a point in time."""

    monthly: int = 0
    bonus: int = 0
    expires_at: datetime | None = None
    renewal_date: datetime | None = None
    monthly_allowance: int = 0        # what a renewal re-grants

    @property
    def total(self) -> int:
        return self.monthly + self.bonus


@dataclass(frozen=True)
class SettlementStep:
    """One lifecycle movement that settlement decided is due."""

    type: str                  # "expire" | "renew"
    bucket: CreditBucket
    amount: int                # signed delta
    balance_before: int
    balance_after: int
    reason: str
    at: datetime


def add_month(moment: datetime) -> datetime:
    """One calendar month later, clamped to the last valid day.

    Naive +30 days drifts the billing date; naive month+1 explodes on 31 Jan.
    Clamping keeps a 31st-of-the-month renewal on the 28th/30th in short months and
    never raises.
    """
    year, month = moment.year, moment.month
    if month == 12:
        year, month = year + 1, 1
    else:
        month += 1
    day = moment.day
    while day > 0:
        try:
            return moment.replace(year=year, month=month, day=day)
        except ValueError:
            day -= 1        # 31 -> 30 -> 29 -> 28
    return moment           # unreachable for real dates


def settle(state: CreditState, now: datetime) -> tuple[CreditState, list[SettlementStep]]:
    """Apply every lifecycle event that is due at `now`.

    Returns the settled state and the ledger steps that produced it. Loops rather
    than applying one period, so an account untouched for months lands in the right
    place instead of catching up one renewal per visit.
    """
    steps: list[SettlementStep] = []
    guard = 0

    while guard < 120:                       # ~10 years; a backstop, never reached normally
        guard += 1

        expiry_due = state.expires_at is not None and now >= state.expires_at and state.monthly > 0
        renewal_due = state.renewal_date is not None and now >= state.renewal_date

        if not expiry_due and not renewal_due:
            break

        # Expire before renewing: within one period boundary the old allowance
        # lapses and only then is the new one granted. Renewing first would let an
        # unused allowance roll over, which is exactly what "expires" rules out.
        if expiry_due:
            before = state.total
            lost = state.monthly
            state = replace(state, monthly=0)
            steps.append(SettlementStep(
                type="expire", bucket=CreditBucket.MONTHLY, amount=-lost,
                balance_before=before, balance_after=state.total,
                reason="Monthly credits expired at period end", at=state.expires_at or now))
            continue

        # renewal_due
        before = state.total
        granted = state.monthly_allowance
        period_start = state.renewal_date or now
        state = replace(
            state,
            monthly=granted,                       # replaces, never accumulates
            expires_at=add_month(period_start),
            renewal_date=add_month(period_start),
        )
        steps.append(SettlementStep(
            type="renew", bucket=CreditBucket.MONTHLY, amount=granted - 0,
            balance_before=before, balance_after=state.total,
            reason=f"Monthly renewal: {granted} credits granted", at=period_start))

        if granted == 0:
            # Nothing to grant and the dates have advanced; keep looping only if
            # another period has already elapsed.
            continue

    return state, steps


def spend(state: CreditState, amount: int) -> tuple[CreditState, list[tuple[CreditBucket, int]]]:
    """Deduct `amount`, monthly bucket first. Caller must check sufficiency.

    Returns the new state and the per-bucket breakdown, so the ledger can record
    which pool actually paid.
    """
    remaining = amount
    breakdown: list[tuple[CreditBucket, int]] = []

    from_monthly = min(state.monthly, remaining)
    if from_monthly:
        state = replace(state, monthly=state.monthly - from_monthly)
        breakdown.append((CreditBucket.MONTHLY, from_monthly))
        remaining -= from_monthly

    if remaining:
        state = replace(state, bonus=state.bonus - remaining)
        breakdown.append((CreditBucket.BONUS, remaining))

    return state, breakdown


def start_period(state: CreditState, allowance: int, now: datetime) -> CreditState:
    """Begin a fresh monthly period immediately (used when a plan is assigned)."""
    return replace(
        state,
        monthly=allowance,
        monthly_allowance=allowance,
        expires_at=add_month(now),
        renewal_date=add_month(now),
    )
