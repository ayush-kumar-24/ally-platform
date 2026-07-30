"""Dashboard display-layer response models (read-only, founder-scoped).

The dashboard is pure aggregation: everything here is read from the database or
computed arithmetically. No LLM, no generation. Founder-facing, so it agrees with
the report -- business health is shown as BANDS, never raw scores, and no
confidence / root-cause / archetype internal number is ever exposed.
"""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel


# Note: the raw-score schemas (BusinessHealthDashboard / PillarHealth) were removed
# in the disclosure-conflict fix. Both founder-facing health surfaces now serve
# BANDS only (BusinessHealthSummary); raw scores live only in the persisted
# business_dna snapshot, read directly by internal consumers.


# ---- dashboard overview ----------------------------------------------------
class DashboardState(str, Enum):
    """The founder's journey state -- the frontend renders a different dashboard
    for each, and 'no data yet' must be distinguishable from 'genuinely zero'."""

    NEW = "new"                               # no profile completed
    PROFILE_DONE = "profile_done"             # profile done, no diagnosis started
    DIAGNOSIS_IN_PROGRESS = "diagnosis_in_progress"
    REPORT_READY = "report_ready"             # first report exists
    RETURNING = "returning"                   # report + prior history


class WelcomeState(BaseModel):
    profile_completed: bool
    show_banner: bool                         # profile complete + tour not yet seen
    show_tour: bool                           # founders.tour_seen_at is null


class StageContext(BaseModel):
    available: bool
    stage_id: int | None = None
    stage_name: str | None = None             # e.g. "Early Traction"
    onboarding_group: str | None = None       # the 3-group label (Stage 0 / 0->1 / 1->10+)


class PillarBand(BaseModel):
    pillar_id: int
    pillar_name: str
    band: str | None = None                   # None = no data (NULL, never 0/Critical Gap)
    red_flag_triggered: bool = False


class BusinessHealthSummary(BaseModel):
    """Bands, NOT numbers -- agrees with the report, which deliberately withholds
    raw scores. `available` is False until a report snapshot exists; when False the
    band is None (not 0), so a brand-new founder is never told they are failing."""

    available: bool
    band: str | None = None                   # headline band, e.g. "Developing"
    fill_pct: int | None = None               # band-derived gauge fill (visual only)
    red_flags: list[str] = []
    pillars: list[PillarBand] = []
    report_id: int | None = None
    generated_at: datetime | None = None


class LatestDiagnosis(BaseModel):
    """Cached prose from the founder's latest report. Never regenerated."""

    available: bool
    report_id: int | None = None
    title: str | None = None
    summary: str | None = None
    generated_at: datetime | None = None


class DashboardMetrics(BaseModel):
    sessions_completed: int = 0
    last_session_at: datetime | None = None
    conversations: int = 0
    reports: int = 0
    root_causes_found: int = 0                 # count only, no confidence
    discovery_calls_booked: int = 0
    discovery_calls_completed: int = 0
    actions_open: int = 0
    actions_completed: int = 0


class ActionItem(BaseModel):
    action_id: int
    title: str
    description: str | None = None
    priority: str | None = None
    due_date: date | None = None
    is_overdue: bool = False


class UpcomingCall(BaseModel):
    available: bool
    call_id: int | None = None
    status: str | None = None
    scheduled_at: datetime | None = None
    duration_minutes: int | None = None
    timezone: str | None = None


class ConversationItem(BaseModel):
    conversation_id: int
    title: str | None = None
    conversation_type: str | None = None
    message_count: int = 0
    last_message_at: datetime | None = None


class ReportListItem(BaseModel):
    report_id: int
    title: str | None = None
    band: str | None = None                    # band, NOT a raw score
    generated_at: datetime | None = None


class DashboardOverview(BaseModel):
    state: DashboardState
    founder_name: str | None = None
    welcome: WelcomeState
    stage: StageContext
    business_health: BusinessHealthSummary
    latest_diagnosis: LatestDiagnosis
    metrics: DashboardMetrics
    upcoming_actions: list[ActionItem] = []
    upcoming_call: UpcomingCall
    recent_conversations: list[ConversationItem] = []
    recent_reports: list[ReportListItem] = []
