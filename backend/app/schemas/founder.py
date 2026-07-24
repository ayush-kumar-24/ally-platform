from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

# The eight feelings the founders_emotional_state_check CHECK allows.
Feeling = Literal[
    "excited", "inspired", "confident", "curious",
    "overwhelmed", "stuck", "determined", "hopeful",
]


def _clean_str_list(v: list[str] | None) -> list[str] | None:
    """Strip each entry, drop blanks, de-duplicate (case-insensitive), keep order.

    Turns messy multi-select input -- ['Sales', ' sales ', '', 'Hiring'] -- into
    ['Sales', 'Hiring'] so the stored jsonb array is clean.
    """
    if v is None:
        return None
    seen: set[str] = set()
    out: list[str] = []
    for item in v:
        s = (item or "").strip()
        key = s.lower()
        if s and key not in seen:
            seen.add(key)
            out.append(s)
    return out


def _dedupe(v: list | None) -> list | None:
    """De-duplicate while preserving order (for already-validated enum lists)."""
    if v is None:
        return None
    seen: set = set()
    out: list = []
    for item in v:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# Multi-select field types: capped, cleaned, de-duplicated.
CleanStrList = Annotated[list[str], AfterValidator(_clean_str_list), Field(max_length=30)]
Feelings = Annotated[list[Feeling], AfterValidator(_dedupe), Field(max_length=8)]


class FounderRead(BaseModel):
    """A founder as the frontend sees it.

    Deliberately narrower than the table: retention timestamps, deletion
    scheduling and consent versions are compliance bookkeeping, not profile
    data, and are not exposed here.
    """

    model_config = ConfigDict(from_attributes=True)

    founder_id: int
    user_id: UUID
    full_name: str
    email: str

    plan_type: str
    diagnosis_used: bool
    profile_completed: bool
    onboarding_completed_at: datetime | None = None
    tour_seen_at: datetime | None = None

    # Founder DNA
    founder_motivation: str | None = None
    working_relationship: str | None = None
    support_preferences: Any | None = None
    experience_level: str | None = None
    emotional_state: list[str] | None = None  # multi-select feelings
    decision_making_style: str | None = None

    # Business DNA
    building_summary: str | None = None
    problem_statement: str | None = None
    customer_segment: str | None = None
    industry: str | None = None
    stage_id: int | None = None
    current_challenges: Any | None = None
    goal_90_day: str | None = None
    vision_1_year: str | None = None
    team_size: str | None = None
    current_revenue: str | None = None
    business_model: str | None = None

    website: str | None = None
    linkedin_url: str | None = None
    preferred_language: str | None = None
    notification_preferences: Any | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None


class FounderUpdate(BaseModel):
    """Fields a founder may change about themselves.

    Every field is optional -- this backs a PATCH, so only what is sent is
    written. Omitted fields are left alone; explicitly sending null clears a
    value.

    Not editable here by design: `email` and `user_id` (owned by Supabase Auth),
    `plan_type` and `diagnosis_used` (owned by billing), and anything under
    consent or retention (owned by the DPDP flows).
    """

    # str_strip_whitespace: trims every string, so "  " on a min_length=1 field
    # (full_name) is rejected rather than saved as blank.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    full_name: str | None = Field(default=None, min_length=1, max_length=200)

    founder_motivation: str | None = Field(default=None, max_length=5000)
    working_relationship: str | None = Field(default=None, max_length=100)
    support_preferences: CleanStrList | None = None
    experience_level: str | None = Field(default=None, max_length=100)
    emotional_state: Feelings | None = None  # multi-select; rejects values outside the allowed 8
    decision_making_style: str | None = Field(default=None, max_length=100)

    building_summary: str | None = Field(default=None, max_length=5000)
    problem_statement: str | None = Field(default=None, max_length=5000)
    customer_segment: str | None = Field(default=None, max_length=100)
    industry: str | None = Field(default=None, max_length=100)
    current_challenges: CleanStrList | None = None
    goal_90_day: str | None = Field(default=None, max_length=5000)
    vision_1_year: str | None = Field(default=None, max_length=5000)
    team_size: str | None = Field(default=None, max_length=50)
    current_revenue: str | None = Field(default=None, max_length=50)
    business_model: str | None = Field(default=None, max_length=100)

    website: str | None = Field(default=None, max_length=500)
    linkedin_url: str | None = Field(default=None, max_length=500)
    preferred_language: str | None = Field(default=None, max_length=10)
    notification_preferences: dict[str, Any] | None = None
