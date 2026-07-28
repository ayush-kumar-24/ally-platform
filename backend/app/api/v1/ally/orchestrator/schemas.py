"""DTOs for the Agent Orchestration Layer (Phase 5, Milestone 7).

The composition root's own types. It imports the frozen subsystem DTOs (M1-M6)
to record what each stage produced, but defines no business logic. Everything here
is immutable; the trace/metrics are observational only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.api.v1.ally.context.schemas import AllyContext
from app.api.v1.ally.execution.schemas import AIResponse, TokenUsage
from app.api.v1.ally.kg.schemas import GraphView
from app.api.v1.ally.memory.schemas import MemoryItem
from app.api.v1.ally.prompts.schemas import RenderedPrompt
from app.api.v1.ally.rag.schemas import RetrievalResult


@dataclass(frozen=True)
class FounderRequest:
    """The inbound request. `request_id` is caller-supplied so one AI interaction
    can be correlated end-to-end (it becomes the memory correlation id); the
    orchestrator generates one only if it is absent."""

    founder_id: int
    message: str
    session_id: int | None = None
    request_id: str | None = None
    language: str = "en"
    response_category: str = "diagnosis_answer"
    actor: str = "founder"


@dataclass(frozen=True)
class PipelineContext:
    """A frozen snapshot of every artifact the pipeline produced -- for the
    response and for debugging. Fields are None/empty until their stage runs."""

    request: FounderRequest
    ally_context: AllyContext | None = None
    memory_items: tuple[MemoryItem, ...] = ()
    retrieval: RetrievalResult | None = None
    graph: GraphView | None = None
    rendered_prompt: RenderedPrompt | None = None
    ai_response: AIResponse | None = None


@dataclass(frozen=True)
class PipelineMetrics:
    memory_reads: int = 0
    retrieval_hits: int = 0
    graph_nodes: int = 0
    prompt_version: int | None = None
    token_usage: TokenUsage = field(default_factory=TokenUsage)


@dataclass(frozen=True)
class PipelineTrace:
    """Observational record of one execution: timing, which steps completed, which
    (if any) failed, and the quantitative metrics + provider/model used."""

    request_id: str
    started_at: datetime
    finished_at: datetime
    duration_ms: float
    completed_steps: tuple[str, ...]
    failed_step: str | None
    provider: str | None
    model: str | None
    metrics: PipelineMetrics


@dataclass(frozen=True)
class OrchestratorResponse:
    request_id: str
    ok: bool
    answer: str
    response_type: str
    confidence: Decimal | None
    citations: tuple[str, ...]
    trace: PipelineTrace
    context: PipelineContext
    error: str | None = None

    @property
    def is_empty(self) -> bool:
        return not self.ok or not self.answer
