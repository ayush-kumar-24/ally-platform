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

#: Price of one discovery call once a founder's free allowance is used up.
CALL_PRICE_INR = 300

#: How far ahead a founder can see bookable slots, by whether they hold
#: Feature.PRIORITY_CALL. Pro sees the grid from tomorrow; everyone else waits
#: two more days, so the Rs 999 tier gets first pick of every slot rather than a
#: separate pool of them. Expressed as lead time and not as reserved slots on
#: purpose: reserving would leave the calendar empty when no Pro founder books,
#: while a lead only ever changes WHO books a slot first.
PRIORITY_CALL_LEAD_DAYS = 1
STANDARD_CALL_LEAD_DAYS = 3

#: Call length lives in settings.DISCOVERY_CALL_DURATION_MINUTES, which is what
#: the calendar service and the booking path both read. Not duplicated here --
#: two constants for one number is how they end up disagreeing.

#: Price of a credit top-up pack (the Free tier's path once the trial ends).
TOPUP_PRICE_INR = 300
TOPUP_CREDITS = 120


class PlanTier(str, Enum):
    """Internal tier ids. Deliberately NOT the founder-facing names -- those live
    in `Plan.name` and change with marketing. Renaming a member here means
    migrating every `founders.plan_type` row and the CHECK constraint on it, for
    no founder-visible benefit."""

    FREE = "free"
    BASIC = "basic"          # Rs 199 / month
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
    GOALS = "goals"
    VISION = "vision"
    RECOMMENDATIONS = "recommendations"
    KNOWLEDGE_CHAT = "knowledge_chat"
    EMAIL_NOTIFICATIONS = "email_notifications"
    PRIORITY_CALL = "priority_call"


#: What every tier gets, paid or not. This is the Rs 199 plan's whole surface:
#: run the assessment, read the report, work the next three steps, and keep
#: daily goals against them. Ally does not talk back and does not suggest --
#: that starts at Rs 450 (chat) and Rs 999 (recommendations).
_BASE = frozenset({
    Feature.DIAGNOSIS,
    Feature.VOICE_DIAGNOSIS,     # voice works in diagnosis for everyone
    Feature.FOUNDER_DNA,
    Feature.BUSINESS_DNA,
    Feature.REPORTS,
    Feature.NEXT_STEPS,
    Feature.CALL_BOOKING,        # everyone may book; only the free allowance differs
    Feature.GOALS,
    Feature.PLAN_YOUR_DAY,       # daily plans against those goals
})

#: Added at Rs 450: Ally starts answering.
_CHAT = frozenset({
    Feature.ALLY_CHAT,
    Feature.VOICE_CHAT,          # voice inside Ally Chat
})

#: Added at Rs 999: Ally starts initiating. Everything here is Ally acting on
#: its own -- proposing next moves, reasoning over the knowledge base, reaching
#: into the founder's inbox, and jumping the call queue.
_ADVISOR = frozenset({
    Feature.VISION,
    Feature.RECOMMENDATIONS,
    Feature.KNOWLEDGE_CHAT,
    Feature.EMAIL_NOTIFICATIONS,
    Feature.PRIORITY_CALL,
    Feature.KNOW_MY_ENERGY,
})


@dataclass(frozen=True)
class Plan:
    tier: PlanTier
    name: str
    #: What the founder actually pays.
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
    #: List price, shown struck through next to `price_inr` on the pricing page.
    #: 0 means "no offer, show one price". Never set this equal to `price_inr` --
    #: a strikethrough that saves nothing is a false claim, and `has_offer` below
    #: is what the API and the pricing page read, not the raw number.
    mrp_inr: int = 0

    @property
    def has_offer(self) -> bool:
        return self.mrp_inr > self.price_inr > 0

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
        # Free out-grants Rs 450 on three features, and only for the testing
        # phase: Vision, recommendations and the knowledge base were ungated
        # before paid tiers existed, so gating them here would take away what
        # our own testers are currently using. It stops short of voice chat and
        # Know My Energy (paid on purpose since before this change) and of the
        # two Rs 999 perks that are scarce rather than merely paid -- an inbox
        # we send to, and a place ahead of paying founders in the call queue.
        # Resize this to `_BASE` at public launch, the same moment the credit
        # ladder in the module docstring has to be restored.
        features=_BASE | frozenset({
            Feature.ALLY_CHAT,
            Feature.VISION,
            Feature.RECOMMENDATIONS,
            Feature.KNOWLEDGE_CHAT,
        }),
        tagline="One month free. See what Ally finds.",
    ),
    PlanTier.BASIC: Plan(
        tier=PlanTier.BASIC,
        name="Basic",
        price_inr=199,
        mrp_inr=300,
        # No chat, so no chat credits and no chat ceiling. The daily limits are
        # zero rather than small: a founder on this tier never reaches a metered
        # surface, and a non-zero budget here would read as an allowance they
        # could spend somewhere.
        monthly_credits=0,
        signup_credits=0,
        daily_token_limit=0,
        planning_daily_token_limit=0,
        free_calls_per_month=0,
        features=_BASE,
        tagline="One diagnosis, one report, three clear next steps.",
    ),
    PlanTier.STARTER: Plan(
        tier=PlanTier.STARTER,
        name="Starter",
        price_inr=450,
        mrp_inr=600,
        monthly_credits=180,
        signup_credits=0,
        daily_token_limit=6_000,
        free_calls_per_month=1,
        features=_BASE | _CHAT,
        tagline="For founders working on the business weekly.",
    ),
    PlanTier.PRO: Plan(
        tier=PlanTier.PRO,
        name="Pro",
        price_inr=999,
        mrp_inr=1_200,
        monthly_credits=240,
        signup_credits=0,
        daily_token_limit=8_000,
        free_calls_per_month=2,
        # Know My Energy is declared here so the gate and the pricing page are
        # already correct; its founder-facing implementation is still to be built.
        features=_BASE | _CHAT | _ADVISOR,
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
    return [PLANS[t] for t in (PlanTier.FREE, PlanTier.BASIC,
                               PlanTier.STARTER, PlanTier.PRO)]


def credits_for_tokens(tokens: int) -> int:
    """Credits a token count costs, rounded UP.

    Rounding up means a 1-token overflow costs a whole credit rather than being
    free. Rounding down would let many small requests consume tokens without ever
    debiting anything -- unlimited usage through the gaps.
    """
    if tokens <= 0:
        return 0
    return -(-tokens // TOKENS_PER_CREDIT)      # ceil division, no float rounding
