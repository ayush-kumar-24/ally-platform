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

    Free     1,431 credits (once)   8,000 chat + 7,700 planning tokens/day
    Starter    180 credits/month    6,000 tokens/day -> 180,000, all reachable
    Pro        240 credits/month    8,000 tokens/day -> 240,000, all reachable

Free grants credits **once**, not monthly: a renewing free tier is an unbounded
recurring cost per signup. It is a one-month trial that ends in a top-up decision.

Free's chat ceiling is 8,000 tokens/day (~32 messages), raised from 4,000 on
2026-08-25 for the team testing phase. 4,000 was ~16 messages, which testers
were exhausting inside a single sitting and reading as "Ally stopped
responding" -- a 429 mid-flow is indistinguishable from a fault when you are
trying to evaluate the product.

Note this deliberately puts Free ABOVE Starter (6,000) and level with Pro
(8,000), which is not a shippable ladder. It is a testing-phase value and has
to come back down when Free is resized for a public launch -- the same moment
the credit grant below is restored (see the PLANS.FREE comment on
PLAN_YOUR_DAY, which has to move at the same time).

The daily ceiling is the binding constraint on chat, not the credit balance:
credits drain far slower than the math below implies, so raising the ceiling
does not strand or overspend the grant. Once the daily limit stops binding,
the NEXT wall a tester hits is the credit balance, which surfaces as a 402
rather than a 429.

Free is currently sized for the TESTING PHASE, not for a public free tier. The
measured per-operation costs it is built from:

    diagnosis   18,900 in + 5,500 out = 24,400   unmetered, lifetime cap of 1
    chat         2,000 in +   400 out =  2,400   x 500 messages = 1,200,000
    planning       800 in +   300 out =  1,100   x 7/day x 30   =   231,000
                                                 total          = 1,431,000

which is 1,431 credits at 1,000 tokens each. At roughly Rs 168 per user per
month this is a funded trial allowance -- shrink it before a public launch.

Diagnosis is deliberately absent from the budget. It is unmetered so a founder can
never hit a wall mid-diagnosis, which is also why it must stay capped by *count*
(one per month) rather than by tokens.

Chat and planning meter SEPARATELY -- they are different features and exhausting
one must not disable the other. That is what the `source` dimension on
daily_token_usage is for. Planning's counter reads zero today: adding a task is
deterministic (no model call) and the task list Ally sees in chat is already
inside chat's own input. The budget exists so reminder/notification LLM work has
somewhere to land without a schema change.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

#: How many LLM tokens one credit represents. Round and explainable on an invoice.
TOKENS_PER_CREDIT = 1_000

#: Metered features. Each keeps its own daily counter (the `source` dimension on
#: daily_token_usage), so chat running out cannot disable planning. Diagnosis is
#: deliberately not here -- it is unmetered and capped by count instead.
SOURCE_CHAT = "chat"
SOURCE_PLANNING = "planning"

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
    #: Granted once at signup, into the `monthly` bucket with an expiry 30 days
    #: out and no renewal_date -- an allowance that lapses once and never returns.
    #: NOT the `bonus` bucket: settle() only ever expires `monthly`, so a grant
    #: written to `bonus` is permanent no matter what date is stamped on it.
    signup_credits: int
    daily_token_limit: int
    free_calls_per_month: int
    features: frozenset[Feature]
    tagline: str
    #: Planning's own daily ceiling, metered separately from chat so exhausting
    #: one feature cannot disable the other. 0 = planning consumes no budget.
    planning_daily_token_limit: int = 0
    #: Diagnoses a founder may ever COMPLETE, for the lifetime of the account --
    #: not a monthly allowance that renews. Diagnosis is unmetered by tokens on
    #: purpose (a founder must never hit a wall mid-assessment), so this count,
    #: not a token ceiling, is what bounds its cost. Only completed diagnoses
    #: count against it: an in-progress session a founder resumes is never
    #: blocked, and never counts, until it reaches a report. 0 = unlimited.
    diagnosis_lifetime_limit: int = 1

    @property
    def is_paid(self) -> bool:
        return self.price_inr > 0

    def daily_limit_for(self, source: str) -> int:
        """The ceiling for one metered feature. Unknown sources fall back to the
        chat limit rather than to unlimited: a source added without a limit here
        must be constrained by something, and the wrong cap is recoverable in a
        way that no cap is not."""
        if source == SOURCE_PLANNING:
            return self.planning_daily_token_limit
        return self.daily_token_limit

    @property
    def reachable_monthly_tokens(self) -> int:
        """Most a founder could consume in a 30-day month under the daily ceilings,
        across every metered feature."""
        return (self.daily_token_limit + self.planning_daily_token_limit) * 30

    def includes(self, feature: Feature) -> bool:
        return feature in self.features


PLANS: dict[PlanTier, Plan] = {
    PlanTier.FREE: Plan(
        tier=PlanTier.FREE,
        name="Free",
        price_inr=0,
        monthly_credits=0,          # one-time grant instead -- see signup_credits
        signup_credits=1_431,       # 1,200 chat + 231 planning; see module docstring
        daily_token_limit=8_000,    # ~32 chat messages/day; testing-phase value, see docstring
        planning_daily_token_limit=7_700,   # 7 planning actions/day at 1,100 each
        free_calls_per_month=0,
        # Plan Your Day is normally paid, but the testing phase includes it: the
        # planning budget above is meaningless without the feature that spends it,
        # and a tester told they get 7 planning actions a day would otherwise hit
        # a 403 on the first one. Move it back to _PAID when Free is resized for
        # a public launch -- the same moment the credit ladder has to be restored.
        features=_UNIVERSAL | frozenset({Feature.PLAN_YOUR_DAY}),
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
