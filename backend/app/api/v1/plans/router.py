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

from fastapi import APIRouter, Depends

from app.api.deps import get_founder_record
from app.api.v1.plans.dependencies import get_entitlement_service
from app.models import Founder
from app.plans.catalog import (
    CALL_PRICE_INR,
    TOKENS_PER_CREDIT,
    TOPUP_CREDITS,
    TOPUP_PRICE_INR,
    Feature,
    all_plans,
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


@router.get("/me", response_model=dict, summary="My plan, limits and usage")
def my_entitlements(founder: Founder = Depends(get_founder_record),
                    service=Depends(get_entitlement_service)) -> dict:
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
