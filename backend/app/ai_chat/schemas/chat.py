"""Chat-flow schemas (Phase 6, Milestone 2).

Strongly-typed, immutable DTOs for the AI Chat Flow. `ConversationContextWindow`
is the key composition seam: it carries the conversation context PLUS the four
grounding sources and, by exposing `request/ally_context/memory_items/retrieval/
graph`, it STRUCTURALLY satisfies M2.1's `GroundingSource` protocol -- so it can be
passed straight to `GroundedPromptManager.render_grounded()` with no coupling and
no modification to the frozen prompt layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.ai_chat.schemas.conversation import Conversation, ConversationContext
from app.api.v1.ally.context.schemas import AllyContext
from app.api.v1.ally.execution.schemas import MediaBlock, TokenUsage
from app.api.v1.ally.kg.schemas import GraphView
from app.api.v1.ally.memory.schemas import MemoryItem
from app.api.v1.ally.rag.schemas import RetrievalResult


@dataclass(frozen=True)
class ChatRequest:
    """One inbound chat turn. `conversation_id` None starts a new conversation."""

    founder_id: int
    message: str
    conversation_id: str | None = None
    session_id: int | None = None
    language: str = "en"
    response_category: str = "general_chat"
    request_id: str | None = None
    actor: str = "founder"
    #: Does this founder's plan include discussing the knowledge base with Ally
    #: (Feature.KNOWLEDGE_CHAT, Rs 999)? Set by the route from the plan gate.
    #: True by default so a caller that predates plan gating is unchanged; the
    #: route is what narrows it, and it is never widened here.
    knowledge_enabled: bool = True


@dataclass(frozen=True)
class GroundingRequest:
    """The `request` face of a GroundingSource: the founder-message text (already
    composed with recent history) plus routing dims."""

    message: str
    language: str = "en"
    response_category: str = "general_chat"


@dataclass(frozen=True)
class ConversationContextWindow:
    """The assembled context for one turn. Satisfies `GroundingSource` structurally
    (request/ally_context/memory_items/retrieval/graph) while also carrying the
    conversation provenance and which sources were successfully injected."""

    request: GroundingRequest
    ally_context: AllyContext | None
    memory_items: tuple[MemoryItem, ...]
    retrieval: RetrievalResult | None
    graph: GraphView | None
    # conversation provenance
    conversation_context: ConversationContext
    current_message: str
    # which optional sources were injected (observational)
    memory_injected: bool = False
    retrieval_injected: bool = False
    graph_injected: bool = False
    attachments_injected: bool = False
    # pre-formatted attachments block (read via getattr in grounded_variables,
    # so other GroundingSource implementers without this field stay valid)
    attachments_text: str = ""
    tasks_injected: bool = False
    # pre-formatted tasks block, same getattr convention as attachments_text.
    tasks_text: str = ""
    profile_injected: bool = False
    # What onboarding already established about this founder -- stage, industry,
    # revenue, what they are building, the problem they arrived with. Same
    # pre-formatted/getattr convention as the two above.
    #
    # Chat had every OTHER source (diagnosis, memory, retrieval, graph, files,
    # tasks) and not this one, so Ally told a founder who had completed
    # onboarding: "I don't have your problem statement, your target customer,
    # your market size, or any product details... only the diagnosis came
    # through." All of it was in `founders`, never put in the prompt.
    profile_text: str = ""
    # Attachments the model will SEE rather than read about -- screenshots and
    # scanned PDFs, which have no text to extract. Carried separately from
    # attachments_text because it travels a different road: text becomes part of
    # the prompt string, media rides beside it as its own content blocks (see
    # AIRequest.media). Empty on every text-only turn.
    media: tuple[MediaBlock, ...] = ()

    @property
    def conversation(self) -> Conversation:
        return self.conversation_context.conversation

    @property
    def history_size(self) -> int:
        return self.conversation_context.total_messages

    @property
    def included_size(self) -> int:
        return len(self.conversation_context.recent_messages)

    @property
    def trimmed_size(self) -> int:
        return max(0, self.conversation_context.total_messages - self.included_size)


@dataclass(frozen=True)
class ChatMetrics:
    history_messages: int = 0
    included_messages: int = 0
    trimmed_messages: int = 0
    memory_reads: int = 0
    retrieval_hits: int = 0
    graph_nodes: int = 0
    prompt_version: int | None = None
    token_usage: TokenUsage = field(default_factory=TokenUsage)


@dataclass(frozen=True)
class ConversationExecutionTrace:
    """Observational record of one chat turn: timing, which steps completed, the
    failing step (if any), provider/model, source-injection flags and metrics."""

    request_id: str
    conversation_id: str
    started_at: datetime
    finished_at: datetime
    duration_ms: float
    completed_steps: tuple[str, ...]
    failed_step: str | None
    provider: str | None
    model: str | None
    memory_injected: bool
    retrieval_injected: bool
    graph_injected: bool
    metrics: ChatMetrics


@dataclass(frozen=True)
class ChatResponse:
    request_id: str
    conversation_id: str
    ok: bool
    answer: str
    response_type: str
    confidence: Decimal | None
    citations: tuple[str, ...]
    assistant_message_id: str | None
    trace: ConversationExecutionTrace
    metrics: ChatMetrics
    error: str | None = None
    # The turn the founder actually sent. Needed so anything uploaded before
    # the send (attachments) can be tied to THAT message rather than floating
    # at conversation level forever -- see POST /chat/attachments/{id}/link.
    # None on the idempotent-replay path, which does not re-append.
    user_message_id: str | None = None

    @property
    def is_empty(self) -> bool:
        return not self.ok or not self.answer
