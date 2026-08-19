"""Feedback request/response shapes."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Only the types the product actually collects. The table's CHECK allows the
# outcome_* types too, but those are for the 30/60/90-day follow-ups the
# learning engine will write, not something a founder submits from a dialog.
FeedbackType = Literal["diagnosis_rating", "report_rating", "general"]


class FeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    feedback_type: FeedbackType
    # Optional now: a free-text "send us a note" (feedback_type="general") has
    # no star rating at all -- it used to go out as a mailto: link that only
    # worked if the founder's own mail client happened to be configured, which
    # silently did nothing for anyone else. It now posts here instead, so
    # rating must not be required for that case. Still mirrors
    # founder_feedback_rating_check (1-5) whenever it IS provided.
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)

    # What the rating is about. Which one is expected depends on the type.
    session_id: int | None = None
    report_id: int | None = None

    @model_validator(mode="after")
    def _target_matches_type(self):
        """A rating with nothing attached to it cannot be acted on later -- you
        can see the score but never what earned it."""
        if self.feedback_type == "report_rating" and self.report_id is None:
            raise ValueError("report_rating requires report_id")
        if self.feedback_type == "diagnosis_rating" and self.session_id is None:
            raise ValueError("diagnosis_rating requires session_id")
        if self.feedback_type in ("report_rating", "diagnosis_rating") and self.rating is None:
            raise ValueError(f"{self.feedback_type} requires a rating")
        if self.rating is None and not (self.comment or "").strip():
            raise ValueError("provide a rating, a comment, or both")
        return self


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feedback_id: int
    feedback_type: str
    rating: int | None = None
    comment: str | None = None
    session_id: int | None = None
    report_id: int | None = None
    collected_at: datetime | None = None


class FeedbackList(BaseModel):
    """Everything this founder has told us.

    The client reads this to decide whether to prompt: a founder who has already
    rated a report should not be asked about it again every time they open it.
    """

    items: list[FeedbackRead]
