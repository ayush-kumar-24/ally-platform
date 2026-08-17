"""Pydantic v2 request/response models for the diagnosis endpoints.

These are the API contract and are intentionally decoupled from the ORM: the
`questions` table carries diagnostic metadata (red/green flag patterns,
root_cause_id, problem_id) that must never reach the founder, because it would
telegraph what the engine is looking for and bias the answer.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QuestionRead(BaseModel):
    """A single question as presented to the founder.

    Deliberately omits `red_flag_pattern`, `green_flag_pattern`,
    `root_cause_id` and `problem_id` -- see module docstring.
    """

    model_config = ConfigDict(from_attributes=True)

    question_id: int
    question_code: str
    category: str
    question_text: str
    question_type: str
    difficulty_level: int


class SessionProgress(BaseModel):
    """Progress counters for the founder-facing progress indicator."""

    model_config = ConfigDict(from_attributes=True)

    questions_answered: int
    current_category: str | None = None


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    founder_id: int
    status: str
    questions_answered_count: int
    current_category: str | None = None
    current_question_id: int | None = None
    started_at: datetime
    completed_at: datetime | None = None


class StartSessionResponse(BaseModel):
    """Returned by POST /diagnosis/start."""

    session: SessionRead
    question: QuestionRead | None = Field(
        default=None,
        description="First question. Null only if the question bank yields no "
        "match for this founder, in which case the session is already complete.",
    )
    resumed: bool = Field(
        default=False,
        description="True when an in-progress session already existed and was "
        "returned instead of creating a second one.",
    )


class AnsweredQA(BaseModel):
    """One already-answered turn, for rebuilding the transcript on resume.

    Deliberately just the founder-facing text -- no score_label/score, same
    "never leak what the engine is scoring on" rule QuestionRead follows.
    """

    question_text: str
    category: str
    answer_text: str
    answered_at: datetime


class CurrentQuestionResponse(BaseModel):
    """Returned by GET /diagnosis/current."""

    session: SessionRead
    question: QuestionRead | None = None
    history: list[AnsweredQA] = Field(
        default_factory=list,
        description="Every turn already answered this session, oldest-first -- "
        "lets a resumed session rebuild its own transcript instead of only "
        "showing the current question with no visible prior context.",
    )


class SubmitAnswerRequest(BaseModel):
    """Body of POST /diagnosis/answer."""

    question_id: int = Field(
        ...,
        gt=0,
        description="Must match the session's current_question_id. Sent "
        "explicitly so a late or duplicated submission cannot be misapplied to "
        "whichever question happens to be current when it arrives.",
    )
    answer_text: str = Field(..., min_length=1, max_length=10_000)

    @field_validator("answer_text")
    @classmethod
    def _strip_and_require_content(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("answer_text cannot be blank.")
        return cleaned


class SubmitAnswerResponse(BaseModel):
    """Returned by POST /diagnosis/answer."""

    session: SessionRead
    next_question: QuestionRead | None = Field(
        default=None,
        description="Null when no questions remain; the session status will "
        "then be 'completed'.",
    )
    is_complete: bool
