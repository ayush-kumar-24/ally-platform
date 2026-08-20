"""Vision API request models (Pydantic v2)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class VisionTerritoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statement: str = Field(min_length=1, max_length=1000)
    tag1: str = Field(default="", max_length=100)
    tag2: str = Field(default="", max_length=100)


class VisionSummaryUpdate(BaseModel):
    """All fields optional -- an omitted field keeps its previous value
    (see VisionService.upsert_summary), matching the frontend's one-field-
    at-a-time updateSummary() calls."""
    model_config = ConfigDict(extra="forbid")
    target: str | None = Field(default=None, max_length=100)
    current: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=100)
