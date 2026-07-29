"""Admin API request models (Pydantic v2). Boundary types only."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StatusChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)


class AnnouncementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    audience: str = Field(default="all", max_length=50)
