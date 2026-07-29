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


@dataclass(frozen=True)
class StreamingChatRequest:
    founder_id: int
    message: str
    conversation_id: str | None = None
    session_id: int | None = None
    language: str = "en"
    response_category: str = "diagnosis_answer"
    request_id: str | None = None
    actor: str = "founder"
    max_chunk_size: int = _DEFAULT_MAX_CHUNK
    timeout_seconds: float | None = None

    def to_chat_request(self, request_id: str | None = None) -> ChatRequest:
        return ChatRequest(
            founder_id=self.founder_id, message=self.message,
            conversation_id=self.conversation_id, session_id=self.session_id,
            language=self.language, response_category=self.response_category,
            request_id=request_id or self.request_id, actor=self.actor,
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
