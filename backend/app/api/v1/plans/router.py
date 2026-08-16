"""Plans & entitlements endpoints.

    GET  /plans                  public catalog (pricing page reads this)
    GET  /plans/me               the signed-in founder's limits and usage
    GET  /plans/me/features/{f}  single feature check
    GET  /plans/me/call-quote    what booking a call costs right now

The catalog is served from the backend rather than duplicated in the frontend so
the pricing page and the enforcement gate can never disagree about what a plan
includes.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.api.v1.diagnosis.repository import DiagnosisRepository
from app.db.session import get_db
from app.api.v1.plans.dependencies import _plan_context, get_entitlement_service
from app.models import Founder
from app.plans.catalog import (
    CALL_PRICE_INR,
    TOKENS_PER_CREDIT,
    TOPUP_CREDITS,
    TOPUP_PRICE_INR,
    Feature,
    all_plans,
    get_plan,
)

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=dict, summary="Public plan catalog")
def catalog() -> dict:
    """Unauthenticated: the pricing page needs this before anyone signs in."""
    return {
        "tokens_per_credit": TOKENS_PER_CREDIT,
        "call_price_inr": CALL_PRICE_INR,
        "topup": {"credits": TOPUP_CREDITS, "price_inr": TOPUP_PRICE_INR},
        "plans": [
            {
                "tier": p.tier.value,
                "name": p.name,
                "price_inr": p.price_inr,
                "tagline": p.tagline,
                "monthly_credits": p.monthly_credits,
                "signup_credits": p.signup_credits,
                "daily_token_limit": p.daily_token_limit,
                "free_calls_per_month": p.free_calls_per_month,
                "features": sorted(f.value for f in p.features),
                "is_paid": p.is_paid,
            }
            for p in all_plans()
        ],
    }


#: How close to the end the UI should start warning. Server-side so the warning
#: window is one decision, not one per surface that renders it.
TRIAL_WARNING_DAYS = 3


def _trial_status(expires_at) -> dict | None:
    """The founder's trial position, or None when they are not on one.

    Returned by the server rather than derived in the browser: `days_remaining`
    from a client clock is wrong for anyone whose device time is off or who is not
    in UTC, and "your trial ends in 3 days" appearing a day early is exactly the
    kind of thing that reads as a billing bug.

    `has_expired` is deliberate as well -- an expired trial and a spent balance
    both show 0 credits, and the frontend cannot tell them apart from the number.
    """
    if expires_at is None:
        return None                      # paid tiers and anything unstamped
    now = datetime.now(timezone.utc)
    # Ceiling, not floor: with 0.4 days left a founder has "1 day", not "0 days"
    # while still being able to use the product.
    seconds = (expires_at - now).total_seconds()
    days_remaining = max(0, math.ceil(seconds / 86_400))
    return {
        "expires_at": expires_at.isoformat(),
        "days_remaining": days_remaining,
        "has_expired": seconds <= 0,
        "expiring_soon": 0 < seconds and days_remaining <= TRIAL_WARNING_DAYS,
        "warning_days": TRIAL_WARNING_DAYS,
    }


def _diagnosis_usage(db: Session, founder: Founder) -> dict:
    """This calendar month's diagnosis usage, the same count and limit
    `_check_monthly_diagnosis_limit` (diagnosis/service.py) actually enforces
    -- computed here, not duplicated, so the profile page's usage meter can
    never disagree with what starting a diagnosis would actually do.

    limit <= 0 means unlimited (matches the enforcement side's convention).
    """
    plan = get_plan(getattr(founder, "plan_type", None))
    limit = plan.diagnoses_per_month
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = DiagnosisRepository(db).count_sessions_started_since(founder.founder_id, month_start)
    return {"used": used, "limit": limit if limit > 0 else None}


@router.get("/me", response_model=dict, summary="My plan, limits and usage")
def my_entitlements(founder: Founder = Depends(get_founder_record),
                    service=Depends(get_entitlement_service),
                    db: Session = Depends(get_db)) -> dict:
    # The credit columns are not mapped on the Founder model -- the credits layer
    # reads them with raw SQL -- so the date has to be fetched, not read off the
    # ORM object. `getattr(founder, "credits_expires_at", None)` looks like it
    # works and silently returns None for everyone, which is how this shipped
    # returning trial: null for founders who definitely had an expiry.
    _, trial_expires_at = _plan_context(db, founder.founder_id)
    e = service.entitlements(founder.founder_id, getattr(founder, "plan_type", None))
    return {
        "founder_id": e.founder_id,
        "tier": e.tier.value,
        "plan_name": e.plan_name,
        "features": e.features,
        "credits_balance": e.credits_balance,
        "daily_token_limit": e.daily_token_limit,
        "daily_tokens_used": e.daily_tokens_used,
        "daily_tokens_remaining": e.daily_tokens_remaining,
        "free_calls_allowance": e.free_calls_allowance,
        "free_calls_used": e.free_calls_used,
        "free_calls_remaining": e.free_calls_remaining,
        "call_price_inr": e.call_price_inr,
        "trial": _trial_status(trial_expires_at),
        "diagnosis_usage": _diagnosis_usage(db, founder),
    }


@router.get("/me/features/{feature}", response_model=dict,
            summary="Does my plan include this feature?")
def check_feature(feature: Feature, founder: Founder = Depends(get_founder_record),
                  service=Depends(get_entitlement_service)) -> dict:
    tier = getattr(founder, "plan_type", None)
    return {"feature": feature.value,
            "allowed": service.has_feature(tier, feature),
            "plan": service.plan_for(tier).name}


@router.get("/me/call-quote", response_model=dict,
            summary="What a 30-minute call costs me right now")
def call_quote(founder: Founder = Depends(get_founder_record),
               service=Depends(get_entitlement_service)) -> dict:
    q = service.quote_call(founder.founder_id, getattr(founder, "plan_type", None))
    return {"is_free": q.is_free, "price_inr": q.price_inr,
            "free_remaining": q.free_remaining}
