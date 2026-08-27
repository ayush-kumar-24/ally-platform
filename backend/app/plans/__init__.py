"""Plans & entitlements -- what each tier includes, and enforcement of it.

Public surface (import from here, not from submodules):

    PlanTier / Feature / Plan / PLANS / all_plans() / get_plan()   the catalog
    EntitlementService / build_entitlement_service()               the gate
    UsageRepository / InMemoryUsageRepository                      the meters
    errors                                                          -> 402 / 403 / 429

Every tier limit lives in `catalog.py`. Nothing else should hard-code a plan's
credits, token ceiling or feature set -- that is how the pricing page, the backend
gate and the admin panel end up disagreeing.
"""

from app.plans.catalog import (
    CALL_PRICE_INR,
    DEFAULT_TIER,
    PLANS,
    TOKENS_PER_CREDIT,
    TOPUP_CREDITS,
    TOPUP_PRICE_INR,
    Feature,
    Plan,
    PlanTier,
    all_plans,
    credits_for_tokens,
    get_plan,
)
from app.plans.errors import (
    DailyTokenLimitError,
    FeatureNotInPlanError,
    NoFreeCallsRemainingError,
    OutOfCreditsError,
    PlanError,
)
from app.plans.service import (
    CallQuote,
    Entitlements,
    EntitlementService,
    build_entitlement_service,
)
from app.plans.usage import (
    CallUsage,
    DailyUsage,
    InMemoryUsageRepository,
    SqlAlchemyUsageRepository,
    UsageRepository,
    next_daily_reset,
    next_utc_midnight,
    usage_day,
    period_month,
)

__all__ = [
    "CALL_PRICE_INR",
    "DEFAULT_TIER",
    "PLANS",
    "TOKENS_PER_CREDIT",
    "TOPUP_CREDITS",
    "TOPUP_PRICE_INR",
    "CallQuote",
    "CallUsage",
    "DailyTokenLimitError",
    "DailyUsage",
    "EntitlementService",
    "Entitlements",
    "Feature",
    "FeatureNotInPlanError",
    "InMemoryUsageRepository",
    "NoFreeCallsRemainingError",
    "OutOfCreditsError",
    "Plan",
    "PlanError",
    "PlanTier",
    "SqlAlchemyUsageRepository",
    "UsageRepository",
    "all_plans",
    "build_entitlement_service",
    "credits_for_tokens",
    "get_plan",
    "next_daily_reset",
    "next_utc_midnight",
    "usage_day",
    "period_month",
]
