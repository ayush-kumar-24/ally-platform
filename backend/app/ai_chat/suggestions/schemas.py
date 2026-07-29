"""Suggestion domain models (Phase 6, Milestone 5, Part 1).

Immutable, strongly-typed DTOs for deterministic, rule-based suggestions. A
Suggestion is a STRUCTURED PROPOSAL only -- it is never executed, and no LLM is
involved. Ranking assigns `relevance_score` + `rank`; the engine assigns id/time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from app.ai_chat.schemas.chat import ConversationContextWindow
from app.ai_chat.schemas.conversation import Conversation


class SuggestionType(str, Enum):
    FOLLOW_UP = "follow_up"
    CLARIFICATION = "clarification"
    MISSING_INFORMATION = "missing_information"
    SUMMARIZATION = "summarization"
    ATTACHMENT_REVIEW = "attachment_review"
    LINK_DISCUSSION = "link_discussion"
    CONTINUE_CONVERSATION = "continue_conversation"
    GOAL_REMINDER = "goal_reminder"


class SuggestionPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SuggestionStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class SuggestionFeedbackType(str, Enum):
    PENDING = "pending"       # no feedback yet
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    IGNORED = "ignored"


class SuggestionSource(str, Enum):
    CONVERSATION = "conversation"
    AI_RESPONSE = "ai_response"
    ATTACHMENT = "attachment"
    LINK = "link"
    CONTEXT = "context"
    SYSTEM = "system"


# Deterministic ordering weights (used by ranking; never randomness).
PRIORITY_WEIGHT: dict[SuggestionPriority, int] = {
    SuggestionPriority.LOW: 1,
    SuggestionPriority.MEDIUM: 2,
    SuggestionPriority.HIGH: 3,
    SuggestionPriority.CRITICAL: 4,
}
TYPE_ORDER: dict[str, int] = {t.value: i for i, t in enumerate(SuggestionType)}


@dataclass(frozen=True)
class SuggestionReason:
    """Why a suggestion was produced -- deterministic, auditable, human-readable."""

    code: str
    description: str


@dataclass(frozen=True)
class SuggestionDraft:
    """A rule's pure output: a suggestion description with no id/timestamp yet."""

    suggestion_type: SuggestionType
    title: str
    body: str
    priority: SuggestionPriority
    source: SuggestionSource
    reason: SuggestionReason
    dedup_key: str
    base_relevance: float = 0.0


@dataclass(frozen=True)
class Suggestion:
    suggestion_id: str
    conversation_id: str
    founder_id: int
    suggestion_type: SuggestionType
    title: str
    body: str
    priority: SuggestionPriority
    source: SuggestionSource
    reason: SuggestionReason
    dedup_key: str
    created_at: datetime
    updated_at: datetime
    status: SuggestionStatus = SuggestionStatus.ACTIVE
    feedback: SuggestionFeedbackType = SuggestionFeedbackType.PENDING
    relevance_score: float = 0.0
    rank: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.status == SuggestionStatus.ACTIVE

    @property
    def is_archived(self) -> bool:
        return self.status == SuggestionStatus.ARCHIVED

    @property
    def is_deleted(self) -> bool:
        return self.status == SuggestionStatus.DELETED


@dataclass(frozen=True)
class SuggestionFeedback:
    feedback_id: str
    suggestion_id: str
    founder_id: int
    feedback_type: SuggestionFeedbackType
    created_at: datetime
    note: str | None = None


@dataclass(frozen=True)
class SuggestionMetrics:
    generated: int
    suppressed_duplicates: int
    returned: int
    by_type: Mapping[str, int]
    by_priority: Mapping[str, int]


@dataclass(frozen=True)
class SuggestionTrace:
    conversation_id: str
    generated_at: datetime
    rules_fired: tuple[str, ...]
    generated: int
    suppressed: int
    limited: bool


@dataclass(frozen=True)
class SuggestionCollection:
    conversation_id: str
    founder_id: int
    suggestions: tuple[Suggestion, ...]
    generated_at: datetime
    metrics: SuggestionMetrics
    trace: SuggestionTrace

    @property
    def is_empty(self) -> bool:
        return len(self.suggestions) == 0

    @property
    def top(self) -> Suggestion | None:
        return self.suggestions[0] if self.suggestions else None


@dataclass(frozen=True)
class SuggestionContext:
    """The bundled, read-only inputs the engine reasons over. Composed from existing
    artifacts (conversation, context window, AI response, attachments, links)."""

    conversation: Conversation
    context_window: ConversationContextWindow | None = None
    ai_response: Any | None = None          # ChatResponse (duck-typed: reads .ok)
    attachments: tuple[Any, ...] = ()       # Attachment (reads .is_active)
    links: tuple[Any, ...] = ()             # Link (reads .link_type)

    @property
    def founder_id(self) -> int:
        return self.conversation.founder_id
