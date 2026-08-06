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
    """402 Payment Required -- the balance is empty, not the request malformed."""

    def __init__(self, balance: int, needed: int):
        super().__init__(
            f"Not enough credits: {needed} needed, {balance} available. "
            f"Top up or upgrade your plan to continue.",
            status_code=402,
        )
        self.balance = balance
        self.needed = needed


class DailyTokenLimitError(PlanError):
    """429 Too Many Requests -- a rate ceiling, and it resets on its own."""

    def __init__(self, used: int, limit: int, resets_at):
        super().__init__(
            f"Daily limit reached ({used:,} of {limit:,} tokens). "
            f"Your allowance resets at {resets_at:%H:%M UTC}.",
            status_code=429,
        )
        self.used = used
        self.limit = limit
        self.resets_at = resets_at


class MonthlyDiagnosisLimitError(PlanError):
    """429 -- the founder has started their allowance of diagnoses this month.

    A count, not a token ceiling: diagnosis is deliberately unmetered so nobody
    hits a wall halfway through an assessment, which leaves the number of runs as
    the only thing bounding what it costs.

    Resuming an in-progress diagnosis is never blocked by this -- only starting a
    new one -- so this cannot strand a founder mid-assessment.
    """

    def __init__(self, used: int, limit: int, resets_at):
        # %-d is glibc-only and raises on Windows, so build the day number itself.
        when = f"{resets_at.day} {resets_at:%B}"
        noun = "diagnosis" if limit == 1 else "diagnoses"
        super().__init__(
            f"You have used all {limit} {noun} included this month "
            f"({used} of {limit}). Your next one is available from {when}.",
            status_code=429,
        )
        self.used = used
        self.limit = limit
        self.resets_at = resets_at


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
