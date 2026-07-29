"""Chat API request models (Pydantic v2). Boundary types only -- the router maps
these to the internal dataclass DTOs; internal DTOs never touch the wire."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000, description="The founder's message.")
    conversation_id: str | None = Field(default=None, max_length=128)
    session_id: int | None = None
    language: str = Field(default="en", max_length=16)
    response_category: str = Field(default="diagnosis_answer", max_length=64)
    request_id: str | None = Field(default=None, max_length=128)


class StreamRequest(MessageRequest):
    max_chunk_size: int = Field(default=120, ge=1, le=2000)
    timeout_seconds: float | None = Field(default=None, gt=0)


class CreateConversationRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class FeedbackRequest(BaseModel):
    feedback: Literal["accepted", "dismissed", "ignored"]
    note: str | None = Field(default=None, max_length=1000)
