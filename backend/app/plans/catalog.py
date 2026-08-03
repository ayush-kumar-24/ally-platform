"""The plan catalog -- one source of truth for what each tier includes.

Everything that differs between Free / Starter / Pro is declared here: price,
credits, the daily token ceiling, the feature set and the free-call allowance.
Nothing else in the codebase should hard-code a tier's limits; it should ask this
module. That is what stops the pricing page, the backend gate and the admin panel
drifting apart and telling a founder three different things.

The numbers
-----------
Credits are sized so a tier's monthly allowance is actually *reachable* under its
own daily ceiling -- 30 days x daily_tokens / TOKENS_PER_CREDIT. A plan that grants
more credits than its daily limit allows anyone to spend would strand the remainder
every month, which is a refund request waiting to happen.

    Free     120 credits (once)   4,000 tokens/day  -> 30 days of trial
    Starter  180 credits/month    6,000 tokens/day  -> 180,000 tokens, all reachable
    Pro      240 credits/month    8,000 tokens/day  -> 240,000 tokens, all reachable

Free grants credits **once**, not monthly: a renewing free tier is an unbounded
recurring cost per signup. It is a one-month trial that ends in a top-up decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

#: How many LLM tokens one credit represents. Round and explainable on an invoice.
TOKENS_PER_CREDIT = 1_000

#: Price of a 30-minute call once a founder's free allowance is used up.
CALL_PRICE_INR = 300

#: Price of a credit top-up pack (the Free tier's path once the trial ends).
TOPUP_PRICE_INR = 300
TOPUP_CREDITS = 120


class PlanTier(str, Enum):
    FREE = "free"
    STARTER = "starter"      # Rs 450 / month
    PRO = "pro"              # Rs 999 / month


class Feature(str, Enum):
    """Everything a plan can gate. Checked server-side; the UI only mirrors it."""

    ALLY_CHAT = "ally_chat"
    DIAGNOSIS = "diagnosis"
    VOICE_DIAGNOSIS = "voice_diagnosis"
    VOICE_CHAT = "voice_chat"
    PLAN_YOUR_DAY = "plan_your_day"
    KNOW_MY_ENERGY = "know_my_energy"
    FOUNDER_DNA = "founder_dna"
    BUSINESS_DNA = "business_dna"
    REPORTS = "reports"
    NEXT_STEPS = "next_steps"
    CALL_BOOKING = "call_booking"


#: Available on every tier, including Free.
_UNIVERSAL = frozenset({
    Feature.ALLY_CHAT,
    Feature.DIAGNOSIS,
    Feature.VOICE_DIAGNOSIS,     # voice works in diagnosis for everyone
    Feature.FOUNDER_DNA,
    Feature.BUSINESS_DNA,
    Feature.REPORTS,
    Feature.NEXT_STEPS,
    Feature.CALL_BOOKING,        # everyone may book; only the free allowance differs
})

#: Added by any paid tier.
_PAID = frozenset({
    Feature.VOICE_CHAT,          # voice inside Ally Chat is a paid upgrade
    Feature.PLAN_YOUR_DAY,
})


@dataclass(frozen=True)
class Plan:
    tier: PlanTier
    name: str
    price_inr: int
    #: Granted every month and expiring at period end (the `monthly` credit bucket).
    monthly_credits: int
    #: Granted once at signup and never expiring (the `bonus` bucket).
    signup_credits: int
    daily_token_limit: int
    free_calls_per_month: int
    features: frozenset[Feature]
    tagline: str

    @property
    def is_paid(self) -> bool:
        return self.price_inr > 0

    @property
    def reachable_monthly_tokens(self) -> int:
        """Most a founder could consume in a 30-day month under the daily ceiling."""
        return self.daily_token_limit * 30

    def includes(self, feature: Feature) -> bool:
        return feature in self.features


PLANS: dict[PlanTier, Plan] = {
    PlanTier.FREE: Plan(
        tier=PlanTier.FREE,
        name="Free",
        price_inr=0,
        monthly_credits=0,          # one-time grant instead -- see signup_credits
        signup_credits=120,
        daily_token_limit=4_000,
        free_calls_per_month=0,
        features=_UNIVERSAL,
        tagline="One month free. See what Ally finds.",
    ),
    PlanTier.STARTER: Plan(
        tier=PlanTier.STARTER,
        name="Starter",
        price_inr=450,
        monthly_credits=180,
        signup_credits=0,
        daily_token_limit=6_000,
        free_calls_per_month=1,
        features=_UNIVERSAL | _PAID,
        tagline="For founders working on the business weekly.",
    ),
    PlanTier.PRO: Plan(
        tier=PlanTier.PRO,
        name="Pro",
        price_inr=999,
        monthly_credits=240,
        signup_credits=0,
        daily_token_limit=8_000,
        free_calls_per_month=2,
        # Know My Energy is Pro-only. The feature is declared here so the gate and
        # the pricing page are already correct; the founder-facing implementation
        # is still to be built.
        features=_UNIVERSAL | _PAID | frozenset({Feature.KNOW_MY_ENERGY}),
        tagline="Ally as your standing advisor.",
    ),
}

DEFAULT_TIER = PlanTier.FREE


def get_plan(tier: PlanTier | str | None) -> Plan:
    """Resolve a tier to its Plan. Unknown or missing values fall back to Free.

    Fails *closed* on purpose: an unrecognised `plan_type` in the database must
    grant the least, never the most. A typo should not hand someone the Pro tier.
    """
    if tier is None:
        return PLANS[DEFAULT_TIER]
    try:
        return PLANS[PlanTier(tier)]
    except (ValueError, KeyError):
        return PLANS[DEFAULT_TIER]


def all_plans() -> list[Plan]:
    """Catalog order: cheapest first, which is also the pricing-page order."""
    return [PLANS[t] for t in (PlanTier.FREE, PlanTier.STARTER, PlanTier.PRO)]


def credits_for_tokens(tokens: int) -> int:
    """Credits a token count costs, rounded UP.

    Rounding up means a 1-token overflow costs a whole credit rather than being
    free. Rounding down would let many small requests consume tokens without ever
    debiting anything -- unlimited usage through the gaps.
    """
    if tokens <= 0:
        return 0
    return -(-tokens // TOKENS_PER_CREDIT)      # ceil division, no float rounding
