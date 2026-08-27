"""Errors for plan entitlements.

The status codes are chosen so a client can tell the three "no" cases apart without
parsing text, because each needs a different UI:

    403  the plan does not include this feature  -> show an upgrade prompt
    402  out of credits                          -> show top-up / upgrade
    429  daily token ceiling reached             -> show "try again tomorrow"

Collapsing these into one 403 would leave the frontend guessing whether to sell an
upgrade or tell someone to come back in the morning.
"""

from app.middleware.error_handler import AppError


class PlanError(AppError):
    """Base for entitlement failures."""


class FeatureNotInPlanError(PlanError):
    def __init__(self, feature: str, plan_name: str, required: str | None = None):
        upgrade = f" Upgrade to {required} to use it." if required else ""
        super().__init__(
            f"'{feature}' is not included in the {plan_name} plan.{upgrade}",
            status_code=403,
        )
        self.feature = feature
        self.required_plan = required


class OutOfCreditsError(PlanError):
    """402 Payment Required -- the balance is empty, not the request malformed.

    Distinguishes *spent* from *expired*. Both are 402 and both end in an upgrade,
    but "you used everything up" and "your trial ended" are different facts, and
    telling a founder the wrong one is confusing in a way that costs support time:
    someone whose trial lapsed with 900 credits unused, told they are "out of
    credits", will reasonably think something is broken.
    """

    def __init__(self, balance: int, needed: int, expired_at=None):
        if expired_at is not None:
            message = (
                f"Your free trial ended on {expired_at.day} "
                f"{expired_at:%B}. Upgrade to keep using Ally."
            )
        else:
            message = (
                f"Not enough credits: {needed} needed, {balance} available. "
                f"Top up or upgrade your plan to continue."
            )
        super().__init__(message, status_code=402)
        self.balance = balance
        self.needed = needed
        #: When the trial lapsed, or None when the balance was simply spent.
        self.expired_at = expired_at


class DailyTokenLimitError(PlanError):
    """429 Too Many Requests -- a rate ceiling, and it resets on its own."""

    def __init__(self, used: int, limit: int, resets_at):
        super().__init__(
            f"Daily limit reached ({used:,} of {limit:,} tokens). "
            # %Z, not a hardcoded "UTC": next_daily_reset hands back the moment
            # already in the founder's reset timezone, so this prints the time a
            # clock in the room would show ("00:00 IST"). It previously said UTC
            # unconditionally, which told an Indian founder to wait for midnight
            # when the allowance actually returned at 05:30 their time.
            f"Your allowance resets at {resets_at:%H:%M %Z}.",
            status_code=429,
        )
        self.used = used
        self.limit = limit
        self.resets_at = resets_at


class DiagnosisAlreadyCompletedError(PlanError):
    """429 -- the founder has completed their lifetime allowance of diagnoses.

    A count, not a token ceiling: diagnosis is deliberately unmetered so nobody
    hits a wall halfway through an assessment, which leaves the number of runs as
    the only thing bounding what it costs.

    Lifetime, not monthly: unlike the daily token ceiling this never resets, so
    there is no `resets_at` here -- once the free plan's one diagnosis reaches a
    report, that plan's diagnosis allowance is permanently spent. Resuming an
    in-progress diagnosis is never blocked by this -- only STARTING a new one
    once the founder already has a completed report -- so this can never strand
    someone mid-assessment.
    """

    def __init__(self, used: int, limit: int):
        noun = "diagnosis" if limit == 1 else "diagnoses"
        super().__init__(
            f"You have completed your {limit} free {noun}. You can't start "
            f"another -- take a look at your report instead.",
            status_code=429,
        )
        self.used = used
        self.limit = limit


class NoFreeCallsRemainingError(PlanError):
    """Not an error the user cannot pass -- they can still pay for the call."""

    def __init__(self, used: int, allowance: int, price: int):
        super().__init__(
            f"You have used all {allowance} free call(s) this month. "
            f"Additional calls are Rs {price}.",
            status_code=402,
        )
        self.used = used
        self.allowance = allowance
        self.price = price
