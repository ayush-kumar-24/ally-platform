"""Structural contract for what a grounded prompt is built from.

M2.1 must ground prompts in artifacts owned by other milestones (M1 context, M6
memory, M3 retrieval, M4 graph) plus the founder's message. The orchestrator's
PipelineContext already holds exactly these. Rather than import that M7 type (which
would invert the layering -- M2 depending on M7), we describe the shape as a
Protocol. M7's PipelineContext satisfies it structurally, so the orchestrator can
pass its PipelineContext directly with zero coupling in either direction.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.api.v1.ally.context.schemas import AllyContext
from app.api.v1.ally.kg.schemas import GraphView
from app.api.v1.ally.memory.schemas import MemoryItem
from app.api.v1.ally.rag.schemas import RetrievalResult


@runtime_checkable
class RequestLike(Protocol):
    """The inbound request fields the grounded manager reads (a subset of
    FounderRequest)."""

    message: str
    language: str
    response_category: str


@runtime_checkable
class GroundingSource(Protocol):
    """Everything needed to build a grounded prompt. FounderRequest's
    PipelineContext is the canonical implementation; tests may supply any object
    with these attributes."""

    request: RequestLike
    ally_context: AllyContext | None
    memory_items: tuple[MemoryItem, ...]
    retrieval: RetrievalResult | None
    graph: GraphView | None
