"""Dashboard display-layer endpoints (founder-scoped).

Read-only aggregation (one small mutation: marking the product tour seen). NO LLM,
NO generation, NO report triggering. The founder is derived from the authenticated
identity (get_founder_record) -- never from a request parameter -- so a founder can
only ever see or touch their own dashboard.

BOTH founder-facing health surfaces (the overview and /business-health) disclose
BANDS, never raw scores -- one consistent disclosure policy.

    GET  /dashboard/overview          the full aggregated dashboard
    GET  /dashboard/business-health   business health as bands (same policy)
    POST /dashboard/tour-seen         mark the product tour seen (stops the banner)
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.api.v1.dashboard.service import build_overview, business_health_from_report
from app.db.session import get_db
from app.models import Founder
from app.repositories import intelligence_repository
from app.schemas.dashboard import BusinessHealthSummary, DashboardOverview, WelcomeState

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
async def overview(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> DashboardOverview:
    """The founder's whole dashboard in one call. Bands (not raw scores), no
    confidence, empty states distinguished by `state` + per-section `available`."""
    return build_overview(db, founder)


@router.get("/business-health", response_model=BusinessHealthSummary)
async def business_health(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> BusinessHealthSummary:
    """Business health from the latest report snapshot (no recomputation), as
    BANDS -- identical disclosure to the overview. `available=False` until a
    snapshot exists. Raw scores live only in the persisted snapshot, read directly
    by internal consumers; they are never served to the founder."""
    report = intelligence_repository.get_latest_active_report(db, founder.founder_id)
    return business_health_from_report(report)


@router.post("/tour-seen", response_model=WelcomeState)
async def mark_tour_seen(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> WelcomeState:
    """Mark the product tour seen, so the welcome banner stops showing. Idempotent:
    only stamps founders.tour_seen_at the first time. Without this, `show_tour`
    stays true forever and the banner never dismisses permanently."""
    if getattr(founder, "tour_seen_at", None) is None:
        db.execute(
            text("update founders set tour_seen_at = :ts where founder_id = :f and tour_seen_at is null"),
            {"ts": datetime.now(timezone.utc), "f": founder.founder_id},
        )
        db.commit()
    return WelcomeState(profile_completed=bool(getattr(founder, "profile_completed", False)),
                        show_tour=False, show_banner=False)
