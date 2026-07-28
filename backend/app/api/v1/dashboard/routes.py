"""Dashboard display-layer endpoints (read-only, founder-scoped).

Serves pre-computed snapshots for the founder dashboard. The #8 Business Health
tile reads the structured business-health snapshot persisted on the founder's
latest report (`founder_reports.business_dna`) -- no recomputation here.

    GET /dashboard/business-health   overall score + per-pillar breakdown
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.db.session import get_db
from app.models import Founder
from app.repositories import intelligence_repository
from app.schemas.dashboard import BusinessHealthDashboard, PillarHealth

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/business-health", response_model=BusinessHealthDashboard)
async def business_health(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> BusinessHealthDashboard:
    """The founder's current Business Health, from their latest active report.

    Returns `available=False` (empty) until a report with a business-health
    snapshot exists, so the UI can render an empty state without special-casing.
    """
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
