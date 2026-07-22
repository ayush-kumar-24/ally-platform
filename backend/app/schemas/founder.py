from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
    emotional_state: str | None = None
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

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=200)

    founder_motivation: str | None = None
    working_relationship: str | None = Field(default=None, max_length=100)
    support_preferences: list[str] | None = None
    experience_level: str | None = Field(default=None, max_length=100)
    emotional_state: str | None = Field(default=None, max_length=100)
    decision_making_style: str | None = Field(default=None, max_length=100)

    building_summary: str | None = None
    problem_statement: str | None = None
    customer_segment: str | None = Field(default=None, max_length=100)
    industry: str | None = Field(default=None, max_length=100)
    current_challenges: list[str] | None = None
    goal_90_day: str | None = None
    vision_1_year: str | None = None
    team_size: str | None = Field(default=None, max_length=50)
    current_revenue: str | None = Field(default=None, max_length=50)
    business_model: str | None = Field(default=None, max_length=100)

    website: str | None = Field(default=None, max_length=500)
    linkedin_url: str | None = Field(default=None, max_length=500)
    preferred_language: str | None = Field(default=None, max_length=10)
    notification_preferences: dict[str, Any] | None = None
