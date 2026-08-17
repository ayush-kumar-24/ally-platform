"""String enums mirroring the CHECK constraints already enforced in Postgres.

The database has no native ENUM types -- every one of these is a `varchar`
column guarded by a CHECK constraint. These classes exist so application code
never has to hardcode a literal that the database would reject at INSERT time.

Values here MUST stay identical to the constraint definitions. If they drift,
the failure surfaces as an IntegrityError at runtime rather than a type error.
"""

from enum import Enum


class StrEnum(str, Enum):
    """`enum.StrEnum` equivalent that also runs on Python 3.10.

    Subclassing `str` keeps these values usable directly as SQLAlchemy bind
    parameters, so `status=SessionStatus.IN_PROGRESS` inserts `'in_progress'`.
    """

    def __str__(self) -> str:
        return str(self.value)


class SessionStatus(StrEnum):
    """sessions_status_check"""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class SessionState(StrEnum):
    """sessions_session_state_check"""

    STABLE = "stable"
    SIGNIFICANTLY_GUARDED = "significantly_guarded"
    HIGH_DISTRESS = "high_distress"


class RoutingState(StrEnum):
    """sessions_routing_state_check"""

    CONTINUE = "continue"
    VALIDATE = "validate"
    GENERATE_REPORT = "generate_report"


class QuestionType(StrEnum):
    """questions_question_type_check"""

    OPEN_TEXT = "open_text"
    RATING_SCALE = "rating_scale"
    YES_NO = "yes_no"
    MULTIPLE_CHOICE = "multiple_choice"


class QuestionPriority(StrEnum):
    """questions_priority_check"""

    CORE = "CORE"
    SUPPLEMENTARY = "SUPPLEMENTARY"


class StageGroup(StrEnum):
    """questions_primary_stage_group_check

    Note the literal U+2192 arrow characters -- they are part of the stored
    values, not decoration. Typing '->' here would silently match nothing.
    """

    STAGE_0 = "Stage 0"
    STAGE_0_TO_1 = "Stage 0→1"
    STAGE_1_TO_10_PLUS = "Stage 1→10+"


class ScoreLabel(StrEnum):
    """answers_score_label_check -- the Green/Amber/Red band of a scored answer."""

    GREEN = "green"
    AMBER = "amber"
    RED = "red"


class FounderDnaDimension(StrEnum):
    """founder_dna_questions_dimension_code_check

    All fourteen dimensions the Founder DNA phase asks about: the thirteen in
    `GoXL_Founder_DNA_Decoding_Journey.docx` Section 2, plus EMOTIONAL_
    INTELLIGENCE, which GoXL added on top of the doc.

    Every dashboard card is now sourced by ASKING. Three of these
    (STRENGTHS_BLIND_SPOTS, STRESS_RESPONSE, COMMUNICATION_PREFERENCE) used
    to be derived instead, by matching detected root causes against the
    blind_spots / behaviour_patterns catalogues -- which hold nothing for the
    psychology-range codes most founders actually score, so those cards came
    out empty on real reports. ORIGIN and VISION also exist as onboarding
    free text; the asked answer wins when both are present.

    ARCHETYPE is asked through the doc's "Identity" questions rather than a
    self-label pick -- app/api/v1/reasoning/engines/archetype.py infers the
    archetype from the founder's own language, so it needs language, not a
    label (and self-rating is what the doc's Section 1 warns against).
    """

    # -- doc Section 2, in its own order --
    ARCHETYPE = "archetype"
    CORE_MOTIVATION = "core_motivation"
    ORIGIN = "origin"
    PURPOSE_MISSION = "purpose_mission"
    VISION = "vision"
    CORE_VALUES = "core_values"
    MINDSET_EXCELLENCE = "mindset_excellence"
    STRENGTHS_BLIND_SPOTS = "strengths_blind_spots"
    ENERGY_PATTERNS = "energy_patterns"
    STRESS_RESPONSE = "stress_response"
    DECISION_STYLE = "decision_style"
    COMMUNICATION_PREFERENCE = "communication_preference"
    FOCUS_ATTENTION = "focus_attention"
    # -- GoXL addition, not in the doc's thirteen --
    EMOTIONAL_INTELLIGENCE = "emotional_intelligence"


class FounderDnaFormat(StrEnum):
    """founder_dna_questions_format_check

    FORCED_CHOICE carries its choices in `founder_dna_questions.options` and
    is rendered as pick-one, not a text box -- the doc's "Mixed formats"
    principle (every dimension should have at least one non-text format).
    The doc's six two-image Visual questions are deliberately not here: v1 is
    text-only, so VISUAL would be a format nothing can render.
    """

    NARRATIVE = "narrative"
    SCENARIO = "scenario"
    FORCED_CHOICE = "forced_choice"


class ConfirmationStatus(StrEnum):
    """answers_confirmation_status_check / detected_root_causes.confirmation_status.

    Drives the confirmation multiplier in the final ranking formula
    (CONFIRMED=1.5x, UNCONFIRMED=1.0x, NOT_TESTED=0.5x -- values sourced from
    scoring_rules, never hardcoded in the engine).
    """

    CONFIRMED = "confirmed"
    UNCONFIRMED = "unconfirmed"
    NOT_TESTED = "not_tested"


class ReportType(StrEnum):
    """founder_reports_report_type_check"""

    FULL_DIAGNOSIS = "full_diagnosis"
    FOUNDER_DNA = "founder_dna"
    BUSINESS_DNA = "business_dna"
