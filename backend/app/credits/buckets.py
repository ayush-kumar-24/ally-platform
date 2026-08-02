"""Mapping an admin credit operation onto the two buckets.

Pure functions, no I/O. Both repositories (in-memory and SQLAlchemy) route through
here so they cannot drift: a rule proved by the hermetic tests is the same rule the
database path executes.

Bucket policy
-------------
* **Grants** (ADD, BONUS) land in **bonus**. An admin granting credits does not
  expect them to evaporate at the next renewal boundary; only the plan's own monthly
  allowance is use-it-or-lose-it. ADD and BONUS therefore differ only in the `type`
  recorded on the ledger row, which is what reporting reads.
* **Deductions** (REMOVE, CONSUME) drain **monthly first**, matching `expiry.spend`.
  Draining bonus first would let the monthly allowance expire unused.
* **SET** targets a total: raising it adds to bonus, lowering it deducts in spend
  order.

A deduction that spans both buckets yields **two movements**, and callers write one
ledger row per movement. A single row cannot honestly say it took 20 from monthly
and 15 from bonus, and `bucket` would have to lie about one of them.
"""

from __future__ import annotations

from dataclasses import replace

from app.credits.expiry import CreditBucket, CreditState, spend
from app.credits.models import CreditOperation

# Operations that consume credits, in spend order.
_DEDUCTIONS = (CreditOperation.REMOVE, CreditOperation.CONSUME)


def plan_movements(state: CreditState, operation: CreditOperation,
                   requested: int) -> tuple[CreditState, list[tuple[CreditBucket, int]]]:
    """Resolve an operation into signed per-bucket movements.

    Returns the resulting state and `[(bucket, delta), ...]` in application order.
    Raises ValueError when a deduction exceeds the available total -- the caller
    turns that into InsufficientCreditsError with the real numbers.
    """
    if operation in (CreditOperation.ADD, CreditOperation.BONUS):
        return replace(state, bonus=state.bonus + requested), [(CreditBucket.BONUS, requested)]

    if operation in _DEDUCTIONS:
        return _deduct(state, requested)

    if operation is CreditOperation.SET:
        target = requested
        if target >= state.total:
            gain = target - state.total
            if gain == 0:
                return state, []                 # already at target -- no ledger noise
            return replace(state, bonus=state.bonus + gain), [(CreditBucket.BONUS, gain)]
        return _deduct(state, state.total - target)

    raise ValueError(f"unsupported operation {operation!r}")


def _deduct(state: CreditState, amount: int) -> tuple[CreditState, list[tuple[CreditBucket, int]]]:
    if amount > state.total:
        raise ValueError(f"insufficient:{state.total}:{amount}")
    if amount == 0:
        return state, []
    new_state, breakdown = spend(state, amount)
    return new_state, [(bucket, -taken) for bucket, taken in breakdown]
