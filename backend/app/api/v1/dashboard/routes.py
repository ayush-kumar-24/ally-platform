"""Dashboard display-layer endpoints (read-only, founder-scoped).

Pure aggregation: everything is read from the database or computed arithmetically.
NO LLM, NO generation, NO report triggering. The founder is derived from the
authenticated identity (get_founder_record) -- never from a request parameter --
so a founder can only ever see their own dashboard.

    GET /dashboard/overview          the full aggregated dashboard (primary)
    GET /dashboard/business-health   detailed per-pillar health (scores; internal)
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.api.v1.dashboard.service import build_overview
from app.db.session import get_db
from app.models import Founder
from app.repositories import intelligence_repository
from app.schemas.dashboard import (
    BusinessHealthDashboard, DashboardOverview, PillarHealth,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
async def overview(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> DashboardOverview:
    """The founder's whole dashboard in one call. Bands (not raw scores), no
    confidence, empty states distinguished by `state` + per-section `available`."""
    return build_overview(db, founder)


@router.get("/business-health", response_model=BusinessHealthDashboard)
async def business_health(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> BusinessHealthDashboard:
    """Detailed Business Health from the latest report snapshot (no recomputation).
    Returns `available=False` until a snapshot exists. NOTE: this endpoint carries
    raw pillar scores; the founder-facing overview shows bands only."""
    report = intelligence_repository.get_latest_active_report(db, founder.founder_id)
    snapshot = report.business_dna if report is not None else None
    if not snapshot:
        return BusinessHealthDashboard(available=False)

    return BusinessHealthDashboard(
        available=True,
        report_id=report.report_id,
        generated_at=report.generated_at,
        overall_score=snapshot.get("overall_score"),
        band=snapshot.get("band"),
        red_flags=list(snapshot.get("red_flags") or []),
        pillars=[PillarHealth(**p) for p in (snapshot.get("pillars") or [])],
    )
