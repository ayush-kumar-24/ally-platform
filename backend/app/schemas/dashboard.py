"""Dashboard display-layer response models."""

from datetime import datetime

from pydantic import BaseModel


class PillarHealth(BaseModel):
    pillar_id: int
    pillar_name: str
    weight: float
    score: int | None = None                 # 0-100, None if the pillar had no answers
    band: str | None = None
    red_flag_triggered: bool = False
    red_flag_note: str | None = None
    assessed_question_count: int = 0


class BusinessHealthDashboard(BaseModel):
    """The #8 Business Health display payload: overall score + per-pillar breakdown,
    sourced from the founder's latest report. `available` is False until a report
    with a business-health snapshot exists."""

    available: bool
    report_id: int | None = None
    generated_at: datetime | None = None
    overall_score: int | None = None         # weighted 0-100 across assessed pillars
    band: str | None = None
    red_flags: list[str] = []
    pillars: list[PillarHealth] = []
