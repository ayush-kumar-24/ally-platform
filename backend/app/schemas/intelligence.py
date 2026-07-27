"""Response models for the Founder Intelligence Database (#13).

Read-only projections over the accumulating founder dataset: diagnosis reports
(`founder_reports`), detected root causes (`detected_root_causes`) and the
sessions that produced them. Everything here is founder-scoped -- a founder only
ever sees their own accumulated intelligence.

Numeric DB columns (Numeric/Decimal) are exposed as `float` to keep the JSON
clean, matching the convention already used in `schemas/knowledge.py`.
"""

from datetime import datetime

from pydantic import BaseModel

# --- shared reference shapes ------------------------------------------------


class RootCauseRef(BaseModel):
    """A root cause resolved to its human-readable label."""

    root_cause_id: int
    name: str | None = None
    category: str | None = None


class InterventionRef(BaseModel):
    """An intervention resolved to its code."""

    intervention_id: int
    code: str | None = None


# --- reports ----------------------------------------------------------------


class ReportListItem(BaseModel):
    """One row in the founder's report history."""

    report_id: int
    session_id: int
    report_type: str
    title: str | None = None
    summary: str | None = None
    is_active: bool
    distress_acknowledged_first: bool
    session_state_at_generation: str | None = None
    generated_at: datetime
    top_root_cause_count: int = 0
    recommended_intervention_count: int = 0


class ReportsPage(BaseModel):
    """Paginated report history."""

    total: int
    limit: int
    offset: int
    items: list[ReportListItem]


class ReportDetail(BaseModel):
    """A single founder-facing diagnosis report, with ids resolved to labels.

    Only founder-facing content is exposed. The internal consultant report
    (`internal_intelligence_reports`) is deliberately NOT surfaced here -- it is
    reviewer/ops-only and would leak internal notes to the founder.
    """

    report_id: int
    session_id: int
    report_type: str
    title: str | None = None
    summary: str | None = None
    is_active: bool
    distress_acknowledged_first: bool
    session_state_at_generation: str | None = None
    generated_at: datetime

    insights: list | dict | None = None
    top_root_causes: list[RootCauseRef]
    recommended_interventions: list[InterventionRef]
    confirm_actions: list = []
    solve_actions: list = []


# --- detected root causes (accumulating findings) ---------------------------


class DetectedRootCauseItem(BaseModel):
    """One detected root cause from one session."""

    detection_id: int
    session_id: int
    root_cause_id: int
    name: str | None = None
    category: str | None = None
    final_weighted_score: float
    rank: int | None = None
    is_top_finding: bool
    confirmation_status: str | None = None
    category_risk_score: float | None = None
    created_at: datetime


class DetectedRootCausesPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[DetectedRootCauseItem]


# --- accumulating summary ---------------------------------------------------


class ConfidencePoint(BaseModel):
    """One completed session's headline signals -- the confidence/distress trend."""

    session_id: int
    completed_at: datetime | None = None
    overall_confidence_score: float | None = None
    routing_state: str | None = None
    distress_mode_triggered: bool = False


class RecurringRootCause(BaseModel):
    """A root cause seen across the founder's sessions, with how often."""

    root_cause_id: int
    name: str | None = None
    category: str | None = None
    occurrences: int
    times_top_finding: int
    best_final_weighted_score: float | None = None


class IntelligenceSummary(BaseModel):
    """The accumulating-dataset roll-up for one founder."""

    founder_id: int
    completed_sessions: int
    total_reports: int
    latest_report_id: int | None = None
    latest_generated_at: datetime | None = None
    distress_session_count: int
    confidence_trend: list[ConfidencePoint]
    recurring_root_causes: list[RecurringRootCause]
