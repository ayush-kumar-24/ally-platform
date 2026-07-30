"""Ally AI Chat -- Streaming Responses (Phase 6, Milestone 3).

Production-grade deterministic streaming that COMPOSES the existing chat flow: it
wraps ChatExecutionService, chunks the produced answer (sentence-then-word), and
delivers START -> TOKEN* -> COMPLETE with cancellation + timeout support. Assistant
persistence is deferred to post-COMPLETE, so a cancel/timeout never persists a reply.

Not in this milestone (reserved): real provider token streaming, SSE/WebSocket
transport, and any HTTP endpoint.
"""

from app.ai_chat.streaming.errors import StreamingCancelled, StreamingError, StreamingTimeout
from app.ai_chat.streaming.events import EventLog, StreamingEvent, StreamingEventType
from app.ai_chat.streaming.generator import (
    CancelToken,
    StreamingConfig,
    StreamingGenerator,
    chunk_text,
)
from app.ai_chat.streaming.schemas import (
    ChunkType,
    StreamingChatRequest,
    StreamingChunk,
    StreamingMetrics,
    StreamingResponse,
    StreamingTrace,
)
from app.ai_chat.streaming.service import StreamingChatService

__all__ = [
    # service / generator
    "StreamingChatService",
    "StreamingGenerator",
    "StreamingConfig",
    "CancelToken",
    "chunk_text",
    # schemas
    "StreamingChatRequest",
    "StreamingChunk",
    "StreamingResponse",
    "StreamingMetrics",
    "StreamingTrace",
    "ChunkType",
    # events
    "StreamingEvent",
    "StreamingEventType",
    "EventLog",
    # errors
    "StreamingError",
    "StreamingCancelled",
    "StreamingTimeout",
]
