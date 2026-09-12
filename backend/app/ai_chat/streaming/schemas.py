"""Streaming schemas (Phase 6, Milestone 3, Part 1).

Immutable, strongly-typed DTOs. `StreamingChunk` is the delivery unit a consumer
iterates; `StreamingEvent` (events.py) is the lifecycle audit trail. Metrics/trace
are observational.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.ai_chat.schemas.chat import ChatRequest, ConversationExecutionTrace
from app.ai_chat.streaming.events import StreamingEvent

_DEFAULT_MAX_CHUNK = 120


class ChunkType(str, Enum):
    START = "start"
    TOKEN = "token"
    THINKING = "thinking"        # reserved: provider reasoning stream (future)
    PROGRESS = "progress"        # reserved: coarse progress signal (future)
    COMPLETE = "complete"
    ERROR = "error"
    CANCELLED = "cancelled"


TERMINAL_CHUNKS = frozenset({ChunkType.COMPLETE, ChunkType.ERROR, ChunkType.CANCELLED})

#: Prefix on an ERROR chunk's content when the turn was refused for cost rather
#: than broken. The streaming path cannot return a 429 -- START has already gone
#: out by the time the budget is known -- so the code travels in the error text,
#: and the client keys on it to show the founder a quota notice instead of the
#: generic "something went wrong". Bare codes ("timeout", "cancelled") are the
#: convention here; this one carries a message after the colon because the
#: refusal is only legible with its numbers in it.
TOKEN_BUDGET_ERROR_CODE = "token_budget_exceeded"


@dataclass(frozen=True)
class StreamingChatRequest:
    founder_id: int
    message: str
    conversation_id: str | None = None
    session_id: int | None = None
    language: str = "en"
    response_category: str = "general_chat"
    request_id: str | None = None
    actor: str = "founder"
    max_chunk_size: int = _DEFAULT_MAX_CHUNK
    timeout_seconds: float | None = None
    #: Mirrors ChatRequest.knowledge_enabled. Carried here rather than defaulted
    #: in to_chat_request() because /stream is the path the app is moving to --
    #: a flag that stopped at the streaming boundary would make the Rs 999
    #: knowledge entitlement apply to almost nobody.
    knowledge_enabled: bool = True
    #: Mirrors ChatRequest.token_budget, and carried for the same reason as
    #: knowledge_enabled above: /stream is the path the app is moving to, so a
    #: budget that stopped at the streaming boundary would leave the ceiling
    #: unenforced for almost every message that actually gets sent.
    token_budget: int | None = None

    def to_chat_request(self, request_id: str | None = None) -> ChatRequest:
        return ChatRequest(
            founder_id=self.founder_id, message=self.message,
            conversation_id=self.conversation_id, session_id=self.session_id,
            language=self.language, response_category=self.response_category,
            request_id=request_id or self.request_id, actor=self.actor,
            knowledge_enabled=self.knowledge_enabled,
            token_budget=self.token_budget,
        )


@dataclass(frozen=True)
class StreamingChunk:
    chunk_type: ChunkType
    content: str
    index: int
    final: bool = False


@dataclass(frozen=True)
class StreamingMetrics:
    request_id: str
    conversation_id: str
    start_time: datetime
    duration_ms: float
    chunk_count: int
    token_count: int                 # estimated only (whitespace tokens)
    cancelled: bool
    timed_out: bool
    completed: bool


@dataclass(frozen=True)
class StreamingTrace:
    request_id: str
    conversation_id: str
    started_at: datetime
    finished_at: datetime
    duration_ms: float
    events: tuple[StreamingEvent, ...]
    chunk_count: int
    completed: bool
    cancelled: bool
    timed_out: bool
    chat_trace: ConversationExecutionTrace | None = None


@dataclass(frozen=True)
class StreamingResponse:
    request_id: str
    conversation_id: str
    ok: bool
    answer: str
    chunks: tuple[StreamingChunk, ...]
    assistant_message_id: str | None
    metrics: StreamingMetrics
    trace: StreamingTrace
    cancelled: bool = False
    timed_out: bool = False
    completed: bool = False
    error: str | None = None

    @property
    def token_chunks(self) -> tuple[StreamingChunk, ...]:
        return tuple(c for c in self.chunks if c.chunk_type == ChunkType.TOKEN)
