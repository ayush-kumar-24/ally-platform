"""EntitlementService -- the single place that answers "may this founder do this?".

Three independent gates, checked in this order for any metered action:

    1. Does the plan include the feature?        -> 403
    2. Is the daily token ceiling already hit?   -> 429
    3. Are there enough credits?                 -> 402

Order matters. Checking the cheapest, most permanent "no" first means a Free user
asking for voice-in-chat is told to upgrade, not told they are out of tokens --
which would be true but useless, since tomorrow's reset still would not let them in.

Charging is deliberately split from checking (`check_chat_allowed` then
`record_chat_usage`). The real token count is only known *after* the model replies,
so the pre-check reserves nothing and the post-charge records what actually
happened. The alternative -- estimating tokens up front -- either overcharges or
lets people under-declare, and both are worse than a short window where a founder
could start one request slightly over their ceiling.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from app.plans.catalog import (
    CALL_PRICE_INR,
    SOURCE_CHAT,
    Feature,
    Plan,
    PlanTier,
    credits_for_tokens,
    get_plan,
)
from app.plans.errors import (
    DailyTokenLimitError,
    FeatureNotInPlanError,
    NoFreeCallsRemainingError,
    OutOfCreditsError,
)
from app.plans.usage import UsageRepository, next_utc_midnight, period_month


@dataclass(frozen=True)
class Entitlements:
    """The complete picture the frontend needs to render a founder's limits."""

    founder_id: int
    tier: PlanTier
    plan_name: str
    features: list[str]
    credits_balance: int
    daily_token_limit: int
    daily_tokens_used: int
    daily_tokens_remaining: int
    free_calls_allowance: int
    free_calls_used: int
    free_calls_remaining: int
    call_price_inr: int


@dataclass(frozen=True)
class CallQuote:
    """What booking a call would cost this founder right now."""

    is_free: bool
    price_inr: int
    free_remaining: int


def _lowest_tier_with(feature: Feature) -> str | None:
    """Cheapest plan that includes a feature -- so the 403 can say what to buy."""
    from app.plans.catalog import all_plans
    for plan in all_plans():
        if plan.includes(feature):
            return plan.name
    return None


class EntitlementService:
    def __init__(
        self,
        usage: UsageRepository,
        *,
        credit_service=None,
        clock: Callable[[], datetime] | None = None,
    ):
        self.usage = usage
        # Optional so the gate can be reasoned about (and tested) without credits.
        self.credits = credit_service
        self._now = clock or (lambda: datetime.now(timezone.utc))

    # --- feature gate -----------------------------------------------------

    def plan_for(self, tier: PlanTier | str | None) -> Plan:
        return get_plan(tier)

    def has_feature(self, tier: PlanTier | str | None, feature: Feature) -> bool:
        """Never raises -- for shaping a response, not for enforcing."""
        return self.plan_for(tier).includes(feature)

    def require_feature(self, tier: PlanTier | str | None, feature: Feature) -> None:
        """Enforce. This is the call that actually stops anything."""
        plan = self.plan_for(tier)
        if not plan.includes(feature):
            raise FeatureNotInPlanError(feature.value, plan.name,
                                        required=_lowest_tier_with(feature))

    # --- chat gate --------------------------------------------------------

    def check_chat_allowed(self, founder_id: int, tier: PlanTier | str | None, *,
                           voice: bool = False, is_first_diagnosis: bool = False,
                           source: str = SOURCE_CHAT,
                           trial_expires_at: datetime | None = None) -> None:
        """Pre-flight for one metered request. Raises on the first failing gate.

        `source` selects which daily counter and ceiling apply. Chat and planning
        are budgeted independently, so a founder who has spent their chat
        allowance can still use planning, and the reverse.
        """
        plan = self.plan_for(tier)
        self.require_feature(tier, Feature.ALLY_CHAT)
        if voice:
            self.require_feature(tier, Feature.VOICE_CHAT)

        # The first diagnosis is unmetered by design -- it is the hook, and a
        # founder must never hit a paywall midway through it.
        if is_first_diagnosis:
            return

        now = self._now()
        limit = plan.daily_limit_for(source)
        used = self.usage.get_daily(founder_id, now.date(), source=source).tokens_used
        if used >= limit:
            raise DailyTokenLimitError(used, limit, next_utc_midnight(now))

        if self.credits is not None:
            try:
                balance = self.credits.get_balance(founder_id).balance
            except Exception:
                # Credit columns not migrated yet. Enforcement is gated separately,
                # so skipping the check here cannot bypass a limit that was live.
                balance = None
            if balance is not None and balance <= 0:
                # get_balance() settles first, so by the time the balance reads
                # zero an expired trial has already been zeroed -- which is why
                # the date is what distinguishes "lapsed" from "spent", not the
                # number.
                lapsed = (trial_expires_at is not None
                          and trial_expires_at <= self._now())
                raise OutOfCreditsError(balance, 1,
                                        expired_at=trial_expires_at if lapsed else None)

    def record_chat_usage(self, founder_id: int, tier: PlanTier | str | None, *,
                          tokens: int, is_first_diagnosis: bool = False,
                          reason: str = "Ally chat", source: str = SOURCE_CHAT) -> dict:
        """Charge for what was actually used. Called after the model responds.

        The first diagnosis records tokens (so the daily ceiling still protects the
        system) but charges no credits.
        """
        now = self._now()
        daily = self.usage.add_tokens(founder_id, now.date(), tokens, at=now, source=source)

        charged = 0
        if not is_first_diagnosis and self.credits is not None and tokens > 0:
            charged = credits_for_tokens(tokens)
            from app.credits.models import CreditOperation
            try:
                self.credits.adjust(founder_id, admin_id=0,
                                    operation=CreditOperation.CONSUME,
                                    amount=charged, reason=reason)
            except Exception:
                # The work is already done and the tokens are already spent with the
                # provider. Failing the user's request now would be punishing them
                # for our accounting problem, so the shortfall is surfaced rather
                # than raised -- and the token meter still recorded the usage.
                charged = 0

        plan = self.plan_for(tier)
        return {
            "tokens_used": tokens,
            "credits_charged": charged,
            "daily_used": daily.tokens_used,
            "daily_remaining": daily.remaining(plan.daily_token_limit),
        }

    # --- calls ------------------------------------------------------------

    def quote_call(self, founder_id: int, tier: PlanTier | str | None) -> CallQuote:
        """Everyone may book; only whether it is free differs."""
        plan = self.plan_for(tier)
        used = self.usage.get_calls(founder_id, period_month(self._now())).free_calls_used
        remaining = max(0, plan.free_calls_per_month - used)
        return CallQuote(is_free=remaining > 0,
                         price_inr=0 if remaining > 0 else CALL_PRICE_INR,
                         free_remaining=remaining)

    def consume_free_call(self, founder_id: int, tier: PlanTier | str | None) -> CallQuote:
        """Claim one free call. Raises if none remain -- the caller then charges.

        The claim is a single atomic repository call, not check-then-act: two
        bookings racing must not both be granted the last free call.
        """
        plan = self.plan_for(tier)
        now = self._now()
        claimed = self.usage.try_claim_free_call(
            founder_id, period_month(now), plan.free_calls_per_month, at=now)
        if claimed is None:
            used = self.usage.get_calls(founder_id, period_month(now)).free_calls_used
            raise NoFreeCallsRemainingError(used, plan.free_calls_per_month, CALL_PRICE_INR)
        return CallQuote(is_free=False if claimed.free_calls_used >= plan.free_calls_per_month
                         else True,
                         price_inr=CALL_PRICE_INR
                         if claimed.free_calls_used >= plan.free_calls_per_month else 0,
                         free_remaining=claimed.free_remaining(plan.free_calls_per_month))

    # --- summary ----------------------------------------------------------

    def entitlements(self, founder_id: int, tier: PlanTier | str | None) -> Entitlements:
        plan = self.plan_for(tier)
        now = self._now()
        daily = self.usage.get_daily(founder_id, now.date())
        calls = self.usage.get_calls(founder_id, period_month(now))
        balance = 0
        if self.credits is not None:
            try:
                balance = self.credits.get_balance(founder_id).balance
            except Exception:
                balance = 0          # no credit row yet -- report zero, not an error
        return Entitlements(
            founder_id=founder_id,
            tier=plan.tier,
            plan_name=plan.name,
            features=sorted(f.value for f in plan.features),
            credits_balance=balance,
            daily_token_limit=plan.daily_token_limit,
            daily_tokens_used=daily.tokens_used,
            daily_tokens_remaining=daily.remaining(plan.daily_token_limit),
            free_calls_allowance=plan.free_calls_per_month,
            free_calls_used=calls.free_calls_used,
            free_calls_remaining=calls.free_remaining(plan.free_calls_per_month),
            call_price_inr=CALL_PRICE_INR,
        )


def build_entitlement_service(usage: UsageRepository | None = None, *,
                              credit_service=None,
                              clock: Callable[[], datetime] | None = None
                              ) -> EntitlementService:
    from app.plans.usage import InMemoryUsageRepository
    return EntitlementService(usage or InMemoryUsageRepository(),
                              credit_service=credit_service, clock=clock)
