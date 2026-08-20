"""Framework Usage API request models (Pydantic v2)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FrameworkNoteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # No min_length: an empty note is a deliberate clear (see
    # services/frameworks.js's saveNote() / FrameworkUsageService.save_note).
    note: str = Field(default="", max_length=2000)
