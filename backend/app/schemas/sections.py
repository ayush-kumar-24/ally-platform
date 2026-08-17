"""Profile section schemas -- the four onboarding/profile sections.

Each section maps to a slice of the `founders` row. Update schemas use
extra="forbid" so a client can't smuggle in a field that belongs to another
section (or a read-only column like email/plan_type). Read schemas mirror what
that section shows.

Field grouping, post 2026-08-17 onboarding redesign (4 sections, Path 1 =
Stage 0/Ideation vs Path 2 = everyone beyond it -- see onboarding-redesign spec):
  Founder information  name, experience
  Business information stage / building / problem / product_description /
                        customer / industry / challenges / reality checks /
                        invisible gaps
  Goals                90-day goal (Path 1) / 1-year vision (Path 2)

Social handle (linkedin_url) is not here -- it goes through the existing
generic PATCH /profile (FounderUpdate), which already carries that field; no
reason to duplicate it into a section schema.

Retired in the redesign: founder_motivation, support_preferences,
emotional_state, decision_making_style, adaptive_reflection are no longer
asked by onboarding and were dropped from these schemas -- the new 4-section
spec has no equivalent question for any of them. The `founders` columns
themselves are untouched (still nullable, still readable via GET /profile's
FounderRead) so historical answers from already-onboarded founders are not
lost; nothing new writes them going forward.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.founder import BusinessRealityCheck, CleanStrList, FounderRealityCheck  # noqa: F401 (re-exported for callers of this module)

# Mirrors the founders experience_level CHECK, so a bad value is a clean 422
# at the API instead of a 500 from the database.
ExperienceLevel = Literal["first_time", "one_company", "serial", "investor", "mentor", "executive"]

# Mirrors founders.current_revenue's existing CHECK -- kept as the existing
# coded bands (pre_revenue / under_1L / 1L_5L / 5L_25L / 25L_1Cr / above_1Cr)
# rather than the onboarding-redesign brief's proposed new bands, per an
# explicit product call: this question is new to onboarding, but the coded
# values it writes into an existing, already-live column stay as they were.
MonthlyRevenue = Literal["pre_revenue", "under_1L", "1L_5L", "5L_25L", "25L_1Cr", "above_1Cr"]

# FounderRealityCheck/BusinessRealityCheck now live in app.schemas.founder
# (imported above) -- FounderUpdate there needs them too, and sections.py
# already depended on founder.py for CleanStrList, so defining them there
# avoids a circular import rather than creating one.


# --- Founder information (name + experience) --------------------------------

class FounderInfoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    full_name: str
    experience_level: str | None = None


class FounderInfoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    experience_level: ExperienceLevel | None = None    # single-select


# --- Business information -----------------------------------------------

class BusinessInfoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stage_id: int | None = None
    building_summary: str | None = None
    product_description: str | None = None
    problem_statement: str | None = None
    current_revenue: str | None = None
    customer_segment: list[str] | None = None
    customer_segment_other: str | None = None
    industry: str | None = None
    current_challenges: list[str] | None = None
    current_challenges_other: str | None = None
    founder_reality_signals: FounderRealityCheck | None = None
    business_reality_signals: BusinessRealityCheck | None = None
    invisible_gaps: list[str] | None = None


class BusinessInfoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # The client sends a stage name or label ("Validation", "Stage 0->1"); the
    # route resolves it to stage_id. Sending a bad value is a 422.
    stage: str | None = Field(default=None, min_length=1, max_length=50)
    building_summary: str | None = Field(default=None, max_length=5000)
    # Path 2's "What is it?" -- distinct from building_summary (the name).
    product_description: str | None = Field(default=None, max_length=5000)
    problem_statement: str | None = Field(default=None, max_length=5000)
    # Conditional: only asked beyond Stage 0. A Stage 0 founder simply never
    # sends this key, and the column stays NULL -- pre-revenue by definition,
    # not a 6th band worth adding just to have something to write.
    current_revenue: MonthlyRevenue | None = None
    customer_segment: CleanStrList | None = None            # multi-select chips
    customer_segment_other: str | None = Field(default=None, max_length=200)
    # Bounded to match the String(30) column rather than overshooting it.
    industry: str | None = Field(default=None, max_length=30)
    # No cap here -- the redesigned biggest-challenge question is an
    # uncapped multi-select, unlike the old "choose up to 3" version.
    current_challenges: CleanStrList | None = None
    current_challenges_other: str | None = Field(default=None, max_length=200)
    founder_reality_signals: FounderRealityCheck | None = None
    business_reality_signals: BusinessRealityCheck | None = None
    invisible_gaps: CleanStrList | None = None


# --- Goals (Q7-8) -----------------------------------------------------------

class GoalsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    goal_90_day: str | None = None
    vision_1_year: str | None = None


class GoalsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    goal_90_day: str | None = Field(default=None, max_length=5000)
    vision_1_year: str | None = Field(default=None, max_length=5000)
