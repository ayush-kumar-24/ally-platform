"""Founder Intelligence Database (#13) -- accumulating-dataset read APIs.

Founder-scoped, read-only views over the dataset the diagnosis pipeline
accumulates for each founder: diagnosis reports, detected root causes, and the
confidence/distress trend across sessions.

    GET /intelligence/summary                roll-up: trend + recurring findings
    GET /intelligence/reports                report history (paginated)
    GET /intelligence/reports/latest         the current active report
    GET /intelligence/reports/{report_id}    one report, ids resolved to labels
    GET /intelligence/root-causes            accumulated detected root causes

Ownership is enforced everywhere via `get_founder_record`: every query filters by
the authenticated founder's id, so no founder can read another's intelligence.
The internal consultant report (`internal_intelligence_reports`) is intentionally
NOT exposed here -- it is reviewer/ops-only.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.db.session import get_db
from app.middleware.error_handler import AppError
from app.models import Founder
from app.repositories import intelligence_repository
from app.schemas.intelligence import (
    ConfidencePoint,
    DetectedRootCauseItem,
    DetectedRootCausesPage,
    IntelligenceSummary,
    InterventionRef,
    RecurringRootCause,
    ReportDetail,
    ReportListItem,
    ReportsPage,
    RootCauseRef,
)

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


class ReportNotFoundError(AppError):
    def __init__(self, message: str = "No report was found."):
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND)


# --- helpers ----------------------------------------------------------------


def _as_int_list(value) -> list[int]:
    """Coerce a JSONB id array (or None) into a list of ints."""
    return [int(i) for i in (value or [])]


def _report_detail(db: Session, report) -> ReportDetail:
    """Assemble a founder-facing report, resolving id arrays to labels."""
    top_ids = _as_int_list(report.top_root_cause_ids)
    iv_ids = _as_int_list(report.recommended_intervention_ids)
    rc_labels = intelligence_repository.root_cause_labels(db, top_ids)
    iv_labels = intelligence_repository.intervention_labels(db, iv_ids)

    top_root_causes = [
        RootCauseRef(
            root_cause_id=i,
            name=rc_labels.get(i, (None, None))[0],
            category=rc_labels.get(i, (None, None))[1],
        )
        for i in top_ids
    ]
    recommended = [
        InterventionRef(intervention_id=i, code=iv_labels.get(i)) for i in iv_ids
    ]

    return ReportDetail(
        report_id=report.report_id,
        session_id=report.session_id,
        report_type=report.report_type,
        title=report.title,
        summary=report.summary,
        is_active=report.is_active,
        distress_acknowledged_first=report.distress_acknowledged_first,
        session_state_at_generation=report.session_state_at_generation,
        generated_at=report.generated_at,
        insights=report.insights,
        founder_dna=report.founder_dna,
        business_dna=report.business_dna,
        top_root_causes=top_root_causes,
        recommended_interventions=recommended,
        confirm_actions=list(report.confirm_actions or []),
        solve_actions=list(report.solve_actions or []),
    )


def _report_list_item(report) -> ReportListItem:
    return ReportListItem(
        report_id=report.report_id,
        session_id=report.session_id,
        report_type=report.report_type,
        title=report.title,
        summary=report.summary,
        is_active=report.is_active,
        distress_acknowledged_first=report.distress_acknowledged_first,
        session_state_at_generation=report.session_state_at_generation,
        generated_at=report.generated_at,
        top_root_cause_count=len(report.top_root_cause_ids or []),
        recommended_intervention_count=len(report.recommended_intervention_ids or []),
    )


# --- endpoints --------------------------------------------------------------


@router.get("/summary", response_model=IntelligenceSummary)
async def get_summary(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> IntelligenceSummary:
    """The accumulating-dataset roll-up: session trend + recurring root causes."""
    fid = founder.founder_id
    trend = [
        ConfidencePoint(
            session_id=s.session_id,
            completed_at=s.completed_at,
            overall_confidence_score=s.overall_confidence_score,
            routing_state=s.routing_state,
            distress_mode_triggered=s.distress_mode_triggered,
        )
        for s in intelligence_repository.confidence_trend(db, fid)
    ]
    recurring = [
        RecurringRootCause(**row)
        for row in intelligence_repository.recurring_root_causes(db, fid)
    ]
    latest = intelligence_repository.get_latest_active_report(db, fid)

    return IntelligenceSummary(
        founder_id=fid,
        completed_sessions=intelligence_repository.completed_session_count(db, fid),
        total_reports=intelligence_repository.report_count(db, fid),
        latest_report_id=latest.report_id if latest is not None else None,
        latest_generated_at=latest.generated_at if latest is not None else None,
        distress_session_count=intelligence_repository.distress_session_count(db, fid),
        confidence_trend=trend,
        recurring_root_causes=recurring,
    )


@router.get("/reports", response_model=ReportsPage)
async def list_reports(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    active_only: bool = Query(default=False),
    report_type: str | None = Query(default=None),
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> ReportsPage:
    """The founder's diagnosis report history, newest first."""
    rows, total = intelligence_repository.list_reports(
        db,
        founder.founder_id,
        limit=limit,
        offset=offset,
        active_only=active_only,
        report_type=report_type,
    )
    return ReportsPage(
        total=total,
        limit=limit,
        offset=offset,
        items=[_report_list_item(r) for r in rows],
    )


# Declared before /reports/{report_id} so "latest" is not parsed as an id.
@router.get("/reports/latest", response_model=ReportDetail)
async def get_latest_report(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> ReportDetail:
    """The founder's current active report."""
    report = intelligence_repository.get_latest_active_report(db, founder.founder_id)
    if report is None:
        raise ReportNotFoundError("No active report exists for this founder yet.")
    return _report_detail(db, report)


@router.get("/reports/{report_id}", response_model=ReportDetail)
async def get_report(
    report_id: int,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> ReportDetail:
    """A single report belonging to the founder, with ids resolved to labels."""
    report = intelligence_repository.get_report(db, founder.founder_id, report_id)
    if report is None:
        raise ReportNotFoundError()
    return _report_detail(db, report)


@router.get("/root-causes", response_model=DetectedRootCausesPage)
async def list_detected_root_causes(
    session_id: int | None = Query(default=None),
    top_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> DetectedRootCausesPage:
    """Every root cause detected for this founder across sessions."""
    rows, total = intelligence_repository.list_detections(
        db,
        founder.founder_id,
        session_id=session_id,
        top_only=top_only,
        limit=limit,
        offset=offset,
    )
    labels = intelligence_repository.root_cause_labels(
        db, {r.root_cause_id for r in rows}
    )
    items = [
        DetectedRootCauseItem(
            detection_id=r.detection_id,
            session_id=r.session_id,
            root_cause_id=r.root_cause_id,
            name=labels.get(r.root_cause_id, (None, None))[0],
            category=labels.get(r.root_cause_id, (None, None))[1],
            final_weighted_score=r.final_weighted_score,
            rank=r.rank,
            is_top_finding=r.is_top_finding,
            confirmation_status=r.confirmation_status,
            category_risk_score=r.category_risk_score,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return DetectedRootCausesPage(
        total=total, limit=limit, offset=offset, items=items
    )
