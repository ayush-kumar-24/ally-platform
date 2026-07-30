"""Dashboard overview assembly: pure aggregation, no LLM, no recomputation.

Business health is READ from the founder's latest report snapshot (the output the
existing scorer already persisted) and shown as BANDS. If there is no report the
band is None -- never 0 -- so a brand-new founder is never told they are failing.
The five journey states are derived here so the frontend can tell "no data yet"
apart from "genuinely zero".
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.v1.dashboard.repository import BAND_FILL, dashboard_repository
from app.repositories import intelligence_repository
from app.schemas.dashboard import (
    ActionItem, BusinessHealthSummary, ConversationItem, DashboardMetrics,
    DashboardOverview, DashboardState, LatestDiagnosis, PillarBand, ReportListItem,
    StageContext, UpcomingCall, WelcomeState,
)


def _state(profile_completed, has_report, in_progress, completed, reports_count):
    if not profile_completed:
        return DashboardState.NEW
    if has_report:
        if reports_count > 1 or completed > 1:
            return DashboardState.RETURNING
        return DashboardState.REPORT_READY
    if in_progress > 0:
        return DashboardState.DIAGNOSIS_IN_PROGRESS
    return DashboardState.PROFILE_DONE


def build_overview(db: Session, founder) -> DashboardOverview:
    fid = founder.founder_id

    sess = dashboard_repository.session_stats(db, fid)
    report = intelligence_repository.get_latest_active_report(db, fid)
    counts = dashboard_repository.counts(db, fid)
    stage = dashboard_repository.current_stage(db, fid)

    completed = sess.get("completed") or 0
    in_progress = sess.get("in_progress") or 0
    reports_count = counts.get("reports") or 0
    profile_completed = bool(getattr(founder, "profile_completed", False))
    tour_seen = getattr(founder, "tour_seen_at", None) is not None
    has_report = report is not None

    state = _state(profile_completed, has_report, in_progress, completed, reports_count)

    # --- business health: bands only, from the persisted snapshot (NULL if none) ---
    snap = report.business_dna if report is not None else None
    if snap:
        band = snap.get("band")
        business_health = BusinessHealthSummary(
            available=True,
            band=band,
            fill_pct=BAND_FILL.get(band),
            red_flags=list(snap.get("red_flags") or []),
            pillars=[
                PillarBand(
                    pillar_id=p.get("pillar_id"),
                    pillar_name=p.get("pillar_name"),
                    band=p.get("band"),  # None preserved -> "no data", never 0
                    red_flag_triggered=bool(p.get("red_flag_triggered")),
                )
                for p in (snap.get("pillars") or [])
            ],
            report_id=report.report_id,
            generated_at=report.generated_at,
        )
    else:
        business_health = BusinessHealthSummary(available=False)

    # --- latest diagnosis: cached prose only, never regenerated ---
    if report is not None:
        latest = LatestDiagnosis(
            available=True, report_id=report.report_id, title=report.title,
            summary=report.summary, generated_at=report.generated_at,
        )
        root_causes_found = len(report.top_root_cause_ids or [])
    else:
        latest = LatestDiagnosis(available=False)
        root_causes_found = 0

    metrics = DashboardMetrics(
        sessions_completed=completed,
        last_session_at=sess.get("last_completed_at"),
        conversations=counts.get("conversations") or 0,
        reports=reports_count,
        root_causes_found=root_causes_found,
        discovery_calls_booked=counts.get("calls_booked") or 0,
        discovery_calls_completed=counts.get("calls_completed") or 0,
        actions_open=counts.get("actions_open") or 0,
        actions_completed=counts.get("actions_completed") or 0,
    )

    welcome = WelcomeState(
        profile_completed=profile_completed,
        show_tour=not tour_seen,
        show_banner=profile_completed and not tour_seen,
    )

    stage_ctx = (
        StageContext(
            available=True, stage_id=stage.get("stage_id"),
            stage_name=stage.get("stage_name"), onboarding_group=stage.get("onboarding_label"),
        )
        if stage else StageContext(available=False)
    )

    call = dashboard_repository.upcoming_call(db, fid)
    upcoming_call = UpcomingCall(available=True, **call) if call else UpcomingCall(available=False)

    return DashboardOverview(
        state=state,
        founder_name=getattr(founder, "full_name", None),
        welcome=welcome,
        stage=stage_ctx,
        business_health=business_health,
        latest_diagnosis=latest,
        metrics=metrics,
        upcoming_actions=[ActionItem(**a) for a in dashboard_repository.upcoming_actions(db, fid)],
        upcoming_call=upcoming_call,
        recent_conversations=[ConversationItem(**c) for c in dashboard_repository.recent_conversations(db, fid)],
        recent_reports=[ReportListItem(**r) for r in dashboard_repository.recent_reports(db, fid)],
    )
