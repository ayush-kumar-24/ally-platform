"""Achievements API request models (Pydantic v2)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AchievementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    category: str = Field(default="", max_length=50)
    occurred_on: str = Field(default="", max_length=50)


class AchievementUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    category: str | None = Field(default=None, max_length=50)
    occurred_on: str | None = Field(default=None, max_length=50)
