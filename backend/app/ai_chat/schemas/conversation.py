"""Conversation domain entities (Phase 6, Milestone 1).

All immutable frozen dataclasses -- an "update" produces a new instance, so
conversation state is never silently mutated (the same discipline as Founder
Memory). These are pure data; all behaviour lives in the ConversationService.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

DEFAULT_TITLE = "New conversation"


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"          # soft-deleted; recoverable via restore


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass(frozen=True)
class TokenStats:
    """Running token totals for a conversation. Aggregated from message usage;
    observational only (no token counting/estimation happens here -- callers report
    real usage from AI Execution when they have it)."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, prompt: int, completion: int) -> "TokenStats":
        return TokenStats(
            prompt_tokens=self.prompt_tokens + prompt,
            completion_tokens=self.completion_tokens + completion,
            total_tokens=self.total_tokens + prompt + completion,
        )


@dataclass(frozen=True)
class MessageTokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class ConversationMessage:
    """One turn in a conversation. `sequence` is the deterministic 0-based order
    within its conversation, so history is reproducible regardless of timestamp
    resolution. `important` pins a message so context trimming preserves it."""

    message_id: str
    conversation_id: str
    founder_id: int
    role: MessageRole
    content: str
    created_at: datetime
    sequence: int
    token_usage: MessageTokenUsage | None = None
    important: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Conversation:
    """The conversation header -- everything except the message bodies (which live
    in the repository, keyed by conversation_id)."""

    conversation_id: str
    founder_id: int
    title: str
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = None
    message_count: int = 0
    unread_count: int = 0
    token_stats: TokenStats = field(default_factory=TokenStats)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.status == ConversationStatus.ACTIVE

    @property
    def is_archived(self) -> bool:
        return self.status == ConversationStatus.ARCHIVED

    @property
    def is_deleted(self) -> bool:
        return self.status == ConversationStatus.DELETED


@dataclass(frozen=True)
class ConversationSummary:
    """A deterministic digest of a conversation (counts + span + latest founder
    message). NOT an AI summary -- Milestone 1 does no LLM work; this is structured
    metadata a later milestone can replace with a grounded summary."""

    conversation_id: str
    founder_id: int
    summary: str
    message_count: int
    covered_through_sequence: int      # -1 when there are no messages
    generated_at: datetime


@dataclass(frozen=True)
class ConversationContext:
    """A context-window view of a conversation: the messages selected for the next
    turn (recent + preserved-important) plus provenance about what was trimmed.
    Founder-memory injection and summarisation of the trimmed tail are a later
    milestone; this is the deterministic-truncation core."""

    conversation: Conversation
    recent_messages: tuple[ConversationMessage, ...]
    summary: ConversationSummary | None
    total_messages: int
    truncated: bool

    @property
    def is_empty(self) -> bool:
        return self.total_messages == 0
