"""Pydantic v2 models for the Current Problem endpoints.

Same start/current/answer contract as founder_dna and diagnosis, so the
frontend reuses a call pattern it already has. `progress` is a plain
answered/total count rather than a resolved-dimension list: this phase has a
fixed length, so unlike Founder DNA it CAN honestly show "2 of 4".
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CurrentProblemQuestionRead(BaseModel):
    """`is_symptom` is carried to the client so the UI can frame the opening
    question differently -- it is the founder stating the problem in their
    own words, not another probe, and the report quotes it verbatim."""

    model_config = ConfigDict(from_attributes=True)

    current_problem_question_id: int
    question_text: str
    arc_position: int
    is_symptom: bool = False


class CurrentProblemProgress(BaseModel):
    questions_answered: int
    questions_total: int
    is_complete: bool


class CurrentProblemTurn(BaseModel):
    """One completed question/answer pair, for rebuilding the transcript on
    reload -- same reason FounderDnaTurn exists."""

    question_text: str
    answer_text: str
    is_symptom: bool
    answered_at: datetime


class StartCurrentProblemResponse(BaseModel):
    progress: CurrentProblemProgress
    question: CurrentProblemQuestionRead | None = Field(
        default=None, description="Null only if the phase is already complete."
    )


class CurrentCurrentProblemResponse(BaseModel):
    progress: CurrentProblemProgress
    question: CurrentProblemQuestionRead | None = None
    history: list[CurrentProblemTurn] = Field(default_factory=list)


class SubmitCurrentProblemAnswerRequest(BaseModel):
    current_problem_question_id: int = Field(..., gt=0)
    answer_text: str = Field(..., min_length=1, max_length=10_000)

    @field_validator("answer_text")
    @classmethod
    def _strip_and_require_content(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("answer_text cannot be blank.")
        return cleaned


class SubmitCurrentProblemAnswerResponse(BaseModel):
    progress: CurrentProblemProgress
    next_question: CurrentProblemQuestionRead | None = Field(
        default=None, description="Null when the phase just completed."
    )
