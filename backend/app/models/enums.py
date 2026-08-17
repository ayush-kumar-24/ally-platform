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

    The 6 Founder DNA dimensions with no data source before this phase --
    named identically in app/api/v1/reasoning/engines/founder_dna_extras.py's
    docstring, which already anticipated this engine. Archetype, Core
    Motivation, Origin, Vision, Strengths & Blind Spots, Stress Response, and
    Communication Preference are NOT here: they're already resolved by other
    engines (archetype.py, founder_dna_extras.py) and don't need this
    question phase.
    """

    PURPOSE_MISSION = "purpose_mission"
    CORE_VALUES = "core_values"
    MINDSET_EXCELLENCE = "mindset_excellence"
    ENERGY_PATTERNS = "energy_patterns"
    DECISION_STYLE = "decision_style"
    FOCUS_ATTENTION = "focus_attention"


class FounderDnaFormat(StrEnum):
    """founder_dna_questions_format_check"""

    NARRATIVE = "narrative"
    SCENARIO = "scenario"


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
