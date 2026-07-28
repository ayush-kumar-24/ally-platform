"""HTTP request/response models for the Ally chat endpoint.

Pydantic models at the API boundary -- distinct from the frozen internal dataclass
DTOs (FounderRequest / OrchestratorResponse). The router maps between them, so the
AI foundation's DTOs never leak directly onto the wire.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000, description="The founder's message.")
    # Optional; the authoritative founder is the authenticated token. If supplied it
    # must match the authenticated founder (the router rejects a mismatch) -- it can
    # never be used to read another founder's data.
    founder_id: int | None = None
    request_id: str | None = Field(default=None, max_length=128)
    session_id: int | None = None
    language: str = Field(default="en", max_length=16)
    response_category: str = Field(default="diagnosis_answer", max_length=64)


class ChatResponse(BaseModel):
    """Founder-facing response. Deliberately excludes the confidence score
    (scores are never shown to the founder during a session) and all internal
    orchestration detail (provider/model, memory/retrieval/graph counts, token
    usage, pipeline steps) -- those stay server-side (logs), never on the wire."""

    request_id: str
    ok: bool
    answer: str
    response_type: str
    citations: list[str]
    error: str | None
