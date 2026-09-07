"""Founder Goals API request models (Pydantic v2)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FounderGoalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    subtitle: str = Field(default="", max_length=500)


class FounderGoalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=200)
    subtitle: str | None = Field(default=None, max_length=500)
    #: Reached, or reopened. Handled separately from the text fields in the
    #: router -- completing is a state change with a side effect (it writes an
    #: achievement), not another attribute to overwrite.
    completed: bool | None = None
