"""Streaming lifecycle events (Phase 6, Milestone 3, Part 5).

Fine-grained, observational events recorded as a stream runs. Distinct from the
delivery-level `StreamingChunk` (schemas.py): chunks are what a consumer iterates;
events are the lifecycle audit trail captured in the StreamingTrace.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StreamingEventType(str, Enum):
    START = "start"
    MESSAGE_RECEIVED = "message_received"
    CONTEXT_READY = "context_ready"
    PROMPT_READY = "prompt_ready"
    AI_STARTED = "ai_started"
    TOKEN = "token"
    AI_FINISHED = "ai_finished"
    MESSAGE_PERSISTED = "message_persisted"
    COMPLETE = "complete"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class StreamingEvent:
    event_type: StreamingEventType
    index: int
    detail: str = ""


class EventLog:
    """Ordered, append-only recorder. Deterministic: index is the append order."""

    def __init__(self) -> None:
        self._events: list[StreamingEvent] = []

    def record(self, event_type: StreamingEventType, detail: str = "") -> StreamingEvent:
        event = StreamingEvent(event_type=event_type, index=len(self._events), detail=detail)
        self._events.append(event)
        return event

    @property
    def events(self) -> tuple[StreamingEvent, ...]:
        return tuple(self._events)

    def types(self) -> tuple[StreamingEventType, ...]:
        return tuple(e.event_type for e in self._events)
