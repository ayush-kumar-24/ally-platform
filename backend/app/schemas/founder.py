from datetime import datetime
from typing import Annotated, Any, Literal
from urllib.parse import urlparse
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

# The eight feelings the founders_emotional_state_check CHECK allows.
Feeling = Literal[
    "excited", "inspired", "confident", "curious",
    "overwhelmed", "stuck", "determined", "hopeful",
]

# --- Controlled vocabularies -------------------------------------------------
#
# Five founders columns carry a CHECK constraint listing their permitted values,
# but FounderUpdate typed them as plain `str` with only a max_length. Anything
# outside the list therefore passed validation, reached Postgres, and raised
# CheckViolation -- an unhandled 500 with the whole profile update lost, exactly
# like the width mismatch that preceded it (migration c8a1f47b93de). Measured on
# a live journey run: business_model="D2C e-commerce" is a perfectly reasonable
# thing to type, is not in the list, and 500'd the save.
#
# Typed as Literal for the same reason `Feeling` above is: it turns the 500 into
# a 422 that names the accepted values, and publishes them in the OpenAPI schema
# so a client can render a select instead of a free-text box.
#
# Kept in step with the database by test_profile_field_widths.py, which reads the
# CHECK definitions out of Postgres and compares them against these.
BusinessModel = Literal["B2B", "B2C", "B2B2C", "marketplace", "D2C", "other"]
CurrentRevenue = Literal[
    "pre_revenue", "under_1L", "1L_5L", "5L_25L", "25L_1Cr", "above_1Cr",
]
ExperienceLevel = Literal[
    "first_time", "one_company", "serial", "investor", "mentor", "executive",
]
TeamSize = Literal["solo", "2_5", "6_10", "11_25", "26_50", "50_plus"]
WorkingRelationship = Literal[
    "coach", "cofounder", "strategist", "accountability", "brainstorm", "research",
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


def _validate_social_url(v: str | None) -> str | None:
    """The onboarding "social handle" field (Instagram or LinkedIn, whichever
    the founder wants to share) -- stored in the existing linkedin_url column,
    which already held a bare unvalidated string. A bare domain like
    "instagram.com/name" (no scheme) is the single most likely thing someone
    actually types here, so it is accepted and normalised to https:// rather
    than rejected -- validating strictly against what people type, not just
    what a browser's address bar would accept.
    """
    if v is None:
        return None
    s = v.strip()
    if not s:
        return None
    if "://" not in s:
        s = f"https://{s}"
    parsed = urlparse(s)
    # urlparse is deliberately lenient -- "https://not a url at all" parses
    # with a non-empty netloc ("not a url at all"), so netloc alone is not
    # enough to reject garbage. A real domain has no whitespace and at least
    # one dot (even a bare "localhost"-style host is not a realistic social
    # handle here).
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or " " in parsed.netloc
        or "." not in parsed.netloc
    ):
        raise ValueError("Enter a real URL, e.g. instagram.com/yourname or linkedin.com/in/yourname.")
    return s


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

# "What's your biggest challenge right now?" -- uncapped as of the 2026-08-17
# onboarding redesign (the old onboarding spec capped it at 3; the new one
# does not), so this now just aliases CleanStrList. current_challenges uses
# CleanStrList directly rather than this name going forward.

SocialUrl = Annotated[str, AfterValidator(_validate_social_url), Field(max_length=500)]


class RealityCheck(BaseModel):
    """One yes/no reality-check block -- 5 fixed questions answered together as
    a single onboarding step, not 5 separately-submitted answers. All 5 are
    required once the block is submitted at all; partial submission is
    rejected rather than silently storing an incomplete read. `founders.
    founder_reality_signals`/`business_reality_signals` themselves stay NULL
    until this whole object is written once -- that NULL is what distinguishes
    "hasn't reached this step yet" (or "not applicable", for Business Reality
    on a Stage 0 founder) from "answered". Defined here (not in sections.py)
    so both that module and FounderUpdate below can use it without a circular
    import -- sections.py already imports CleanStrList from this module."""

    model_config = ConfigDict(extra="forbid")


class FounderRealityCheck(RealityCheck):
    """Shown to both paths. Field names capture the checkbox's own claim, not
    its italic sub-label (that pairing is UI copy, not data)."""

    clear_next_priorities: bool   # "I clearly know my next 3 priorities"
    decisive: bool                # "I take decisions with confidence"
    effort_aligned_to_growth: bool  # "My effort is aligned to growth"
    executes_consistently: bool   # "I execute consistently"
    mentally_clear: bool          # "I feel mentally clear & in control"


class BusinessRealityCheck(RealityCheck):
    """Path 2 only -- there is no business yet to assess structure on for a
    Stage 0 founder, so this block is skipped entirely rather than answered."""

    revenue_predictable: bool     # "Revenue is predictable"
    systems_defined: bool         # "Systems/processes are defined"
    plans_become_execution: bool  # "Plans turn into execution"
    team_independent: bool        # "Team operates without dependency"
    financials_clear: bool        # "Financials are clear -- cost, margin, runway"


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
    # The stage-specific question asked at the end of onboarding. Stored since
    # the flow was built, but missing here, so the whole-profile read never
    # returned it and any screen showing the profile back had a blank row.
    adaptive_reflection: str | None = None

    # Business DNA
    building_summary: str | None = None
    product_description: str | None = None
    problem_statement: str | None = None
    customer_segment: Any | None = None      # multi-select chips
    customer_segment_other: str | None = None
    industry: str | None = None
    stage_id: int | None = None
    stage_name: str | None = None      # resolved from stage_id, see Founder.stage_name
    current_challenges: Any | None = None
    current_challenges_other: str | None = None
    founder_reality_signals: FounderRealityCheck | None = None
    business_reality_signals: BusinessRealityCheck | None = None
    invisible_gaps: Any | None = None
    goal_90_day: str | None = None
    vision_1_year: str | None = None
    team_size: str | None = None
    current_revenue: str | None = None
    business_model: str | None = None

    website: str | None = None
    linkedin_url: str | None = None
    avatar_url: str | None = None
    preferred_language: str | None = None
    notification_preferences: Any | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None


class AvatarUploadResponse(BaseModel):
    avatar_url: str


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
    working_relationship: WorkingRelationship | None = None
    support_preferences: CleanStrList | None = None
    experience_level: ExperienceLevel | None = None
    emotional_state: Feelings | None = None  # multi-select; rejects values outside the allowed 8
    decision_making_style: str | None = Field(default=None, max_length=100)

    building_summary: str | None = Field(default=None, max_length=5000)
    problem_statement: str | None = Field(default=None, max_length=5000)
    customer_segment: CleanStrList | None = None            # multi-select chips
    customer_segment_other: str | None = Field(default=None, max_length=200)
    # industry is String(30) in the database. Bounding it at 100 here let a
    # 31-100 character value pass validation and then fail at the insert.
    industry: str | None = Field(default=None, max_length=30)
    current_challenges: CleanStrList | None = None          # uncapped, see above
    current_challenges_other: str | None = Field(default=None, max_length=200)
    product_description: str | None = Field(default=None, max_length=5000)
    founder_reality_signals: FounderRealityCheck | None = None
    business_reality_signals: BusinessRealityCheck | None = None
    invisible_gaps: CleanStrList | None = None
    goal_90_day: str | None = Field(default=None, max_length=5000)
    vision_1_year: str | None = Field(default=None, max_length=5000)
    team_size: TeamSize | None = None
    current_revenue: CurrentRevenue | None = None
    business_model: BusinessModel | None = None

    website: str | None = Field(default=None, max_length=500)
    # Onboarding's "social handle" (Instagram or LinkedIn) -- validated as a
    # real URL rather than accepted as bare unchecked text.
    linkedin_url: SocialUrl | None = None
    preferred_language: str | None = Field(default=None, max_length=10)
    notification_preferences: dict[str, Any] | None = None
