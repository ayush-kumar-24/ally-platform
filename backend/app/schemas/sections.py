"""Profile section schemas -- the four onboarding/profile sections.

Each section maps to a slice of the `founders` row. Update schemas use
extra="forbid" so a client can't smuggle in a field that belongs to another
section (or a read-only column like email/plan_type). Read schemas mirror what
that section shows.

Field grouping follows the 13 onboarding questions:
  Founder information  Q9-13 (why / support / experience / feeling / reflection) + name
  Business information Q1-6  (stage / building / problem / customer / industry / challenges)
  Goals               Q7-8  (90-day goal / 1-year vision)

Name and email come from the Google/LinkedIn login, so there is no company /
identity-details section here.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.founder import CleanStrList, Feelings

# Mirrors the founders experience_level CHECK, so a bad value is a clean 422
# at the API instead of a 500 from the database.
ExperienceLevel = Literal["first_time", "one_company", "serial", "investor", "mentor", "executive"]


# --- Founder information (Q9-13 + identity) ---------------------------------

class FounderInfoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    full_name: str
    founder_motivation: str | None = None
    support_preferences: Any | None = None
    experience_level: str | None = None
    emotional_state: Any | None = None
    decision_making_style: str | None = None
    adaptive_reflection: str | None = None


class FounderInfoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    founder_motivation: str | None = Field(default=None, max_length=5000)
    support_preferences: CleanStrList | None = None    # multi-select "how should we support you"
    experience_level: ExperienceLevel | None = None    # single-select
    emotional_state: Feelings | None = None             # multi-select feelings
    decision_making_style: str | None = Field(default=None, max_length=100)
    adaptive_reflection: str | None = Field(default=None, max_length=5000)


# --- Business information (Q1-6) --------------------------------------------

class BusinessInfoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stage_id: int | None = None
    building_summary: str | None = None
    problem_statement: str | None = None
    customer_segment: str | None = None
    industry: str | None = None
    current_challenges: Any | None = None


class BusinessInfoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # The client sends a stage name or label ("Validation", "Stage 0->1"); the
    # route resolves it to stage_id. Sending a bad value is a 422.
    stage: str | None = Field(default=None, min_length=1, max_length=50)
    building_summary: str | None = Field(default=None, max_length=5000)
    problem_statement: str | None = Field(default=None, max_length=5000)
    customer_segment: str | None = Field(default=None, max_length=100)
    industry: str | None = Field(default=None, max_length=100)
    current_challenges: CleanStrList | None = None


# --- Goals (Q7-8) -----------------------------------------------------------

class GoalsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    goal_90_day: str | None = None
    vision_1_year: str | None = None


class GoalsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    goal_90_day: str | None = Field(default=None, max_length=5000)
    vision_1_year: str | None = Field(default=None, max_length=5000)
