"""Shapes for the founder's first impression."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# "llm"     -- written by the model from the founder's own answers
# "derived" -- assembled from their answers by rule, because the model was
#              unavailable. Surfaced so the UI (and we) can tell them apart.
ImpressionSource = Literal["llm", "derived"]


class FirstImpression(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # Four short observations, shown one at a time on the "Reading between the
    # lines" screen.
    bullets: list[str] = Field(min_length=1, max_length=6)
    # A short paragraph -- Ally's early read, shown on the summary screen.
    read: str
    # One sentence the founder confirms or corrects ("Did I get you right?").
    instinct: str
    source: ImpressionSource
    generated_at: datetime | None = None


class FirstImpressionEnvelope(BaseModel):
    """What the endpoint returns.

    `available` is false only when there is nothing to read yet -- a founder who
    has not finished onboarding. The UI shows its own empty state rather than a
    fabricated impression.
    """

    available: bool
    impression: FirstImpression | None = None
