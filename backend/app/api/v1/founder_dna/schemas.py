"""Pydantic v2 request/response models for the Founder DNA endpoints.

Mirrors app/api/v1/diagnosis/schemas.py's shape deliberately -- same
start/current/answer contract, so the frontend flow can reuse the same
patterns it already has for diagnosis.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FounderDnaQuestionRead(BaseModel):
    """A single Founder DNA question as presented to the founder.

    `format` drives which control the client renders -- `narrative` and
    `scenario` are free text, `forced_choice` is pick-one from `options`.
    Both fields are carried explicitly because the existing diagnosis client
    (frontend/src/services/diagnosis.js) silently drops `question_type` at its
    normalisation boundary and renders every question as a textarea; a
    forced-choice question sent to that path would look like a text question
    with the choices buried in its wording.
    """

    model_config = ConfigDict(from_attributes=True)

    founder_dna_question_id: int
    dimension_code: str
    format: str
    question_text: str
    options: list[str] | None = None
    is_closing: bool = False


class FounderDnaProgress(BaseModel):
    """Progress summary -- no fixed total, since the flow is adaptive (see
    DiagnosisChat.jsx's existing "no X of N" convention, which this mirrors
    for the same reason: the engine decides when a dimension is done, not a
    precomputed count)."""

    questions_answered: int
    dimensions_resolved: list[str]
    dimensions_remaining: list[str]
    is_complete: bool


class StartFounderDnaResponse(BaseModel):
    progress: FounderDnaProgress
    question: FounderDnaQuestionRead | None = Field(
        default=None,
        description="Null only if the phase is already complete.",
    )


class FounderDnaTurn(BaseModel):
    """One completed question/answer pair, for rebuilding the transcript."""

    question_text: str
    dimension_code: str
    answer_text: str
    answered_at: datetime


class CurrentFounderDnaQuestionResponse(BaseModel):
    progress: FounderDnaProgress
    question: FounderDnaQuestionRead | None = None
    #: Everything already answered, oldest first. Only this endpoint sends it
    #: -- POST /answer has no reason to resend what the client just watched
    #: happen. Without it a reload renders one lone question in an empty
    #: transcript, which reads as the conversation having been lost.
    history: list[FounderDnaTurn] = Field(default_factory=list)


class SubmitFounderDnaAnswerRequest(BaseModel):
    founder_dna_question_id: int = Field(..., gt=0)
    answer_text: str = Field(..., min_length=1, max_length=10_000)

    @field_validator("answer_text")
    @classmethod
    def _strip_and_require_content(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("answer_text cannot be blank.")
        return cleaned


class SubmitFounderDnaAnswerResponse(BaseModel):
    progress: FounderDnaProgress
    next_question: FounderDnaQuestionRead | None = Field(
        default=None,
        description="Null when the phase just completed.",
    )
