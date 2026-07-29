"""Chat API response models (Phase 6, Milestone 6, Part 4).

Strongly-typed Pydantic v2 boundary models with `from_domain` mappers. The internal
frozen dataclasses (ChatResponse, Conversation, Attachment, Suggestion, ...) are
translated here so they never leak onto the wire.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Shape produced by the global AppError handler (documented for OpenAPI)."""

    error: str
    message: str
    request_id: str | None = None


# --- chat -------------------------------------------------------------------


class ApiChatMetrics(BaseModel):
    history_messages: int
    included_messages: int
    trimmed_messages: int
    memory_reads: int
    retrieval_hits: int
    graph_nodes: int
    prompt_version: int | None
    total_tokens: int


class ApiChatResponse(BaseModel):
    request_id: str
    conversation_id: str
    ok: bool
    answer: str
    response_type: str
    confidence: float | None
    citations: list[str]
    assistant_message_id: str | None
    provider: str | None
    model: str | None
    error: str | None
    metrics: ApiChatMetrics

    @classmethod
    def from_domain(cls, r) -> "ApiChatResponse":
        m = r.metrics
        return cls(
            request_id=r.request_id, conversation_id=r.conversation_id, ok=r.ok, answer=r.answer,
            response_type=r.response_type, confidence=(float(r.confidence) if r.confidence is not None else None),
            citations=list(r.citations), assistant_message_id=r.assistant_message_id,
            provider=r.trace.provider, model=r.trace.model, error=r.error,
            metrics=ApiChatMetrics(
                history_messages=m.history_messages, included_messages=m.included_messages,
                trimmed_messages=m.trimmed_messages, memory_reads=m.memory_reads,
                retrieval_hits=m.retrieval_hits, graph_nodes=m.graph_nodes,
                prompt_version=m.prompt_version, total_tokens=m.token_usage.total_tokens,
            ),
        )


class StreamingApiResponse(BaseModel):
    """Aggregate view of a completed stream (for docs / a non-SSE collect variant)."""

    request_id: str
    conversation_id: str
    ok: bool
    answer: str
    chunk_count: int
    token_count: int
    completed: bool
    cancelled: bool
    timed_out: bool
    error: str | None

    @classmethod
    def from_domain(cls, r) -> "StreamingApiResponse":
        return cls(
            request_id=r.request_id, conversation_id=r.conversation_id, ok=r.ok, answer=r.answer,
            chunk_count=r.metrics.chunk_count, token_count=r.metrics.token_count,
            completed=r.completed, cancelled=r.cancelled, timed_out=r.timed_out, error=r.error,
        )


# --- conversations ----------------------------------------------------------


class ConversationResponse(BaseModel):
    conversation_id: str
    founder_id: int
    title: str
    status: str
    message_count: int
    unread_count: int
    total_tokens: int
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None

    @classmethod
    def from_domain(cls, c) -> "ConversationResponse":
        return cls(
            conversation_id=c.conversation_id, founder_id=c.founder_id, title=c.title,
            status=c.status.value, message_count=c.message_count, unread_count=c.unread_count,
            total_tokens=c.token_stats.total_tokens, created_at=c.created_at,
            updated_at=c.updated_at, last_message_at=c.last_message_at,
        )


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]
    total: int


# --- attachments ------------------------------------------------------------


class AttachmentResponse(BaseModel):
    attachment_id: str
    conversation_id: str
    founder_id: int
    filename: str
    mime_type: str
    attachment_type: str
    size_bytes: int
    checksum: str
    status: str
    message_id: str | None
    created_at: datetime

    @classmethod
    def from_domain(cls, a) -> "AttachmentResponse":
        return cls(
            attachment_id=a.attachment_id, conversation_id=a.conversation_id, founder_id=a.founder_id,
            filename=a.metadata.filename, mime_type=a.metadata.mime_type.value,
            attachment_type=a.metadata.attachment_type.value, size_bytes=a.metadata.size_bytes,
            checksum=a.metadata.checksum, status=a.status.value, message_id=a.message_id,
            created_at=a.created_at,
        )


class AttachmentListResponse(BaseModel):
    attachments: list[AttachmentResponse]
    total: int


# --- suggestions ------------------------------------------------------------


class SuggestionResponse(BaseModel):
    suggestion_id: str
    conversation_id: str
    founder_id: int
    suggestion_type: str
    title: str
    body: str
    priority: str
    source: str
    reason_code: str
    reason_description: str
    status: str
    feedback: str
    relevance_score: float
    rank: int | None

    @classmethod
    def from_domain(cls, s) -> "SuggestionResponse":
        return cls(
            suggestion_id=s.suggestion_id, conversation_id=s.conversation_id, founder_id=s.founder_id,
            suggestion_type=s.suggestion_type.value, title=s.title, body=s.body,
            priority=s.priority.value, source=s.source.value, reason_code=s.reason.code,
            reason_description=s.reason.description, status=s.status.value, feedback=s.feedback.value,
            relevance_score=s.relevance_score, rank=s.rank,
        )


class SuggestionCollectionResponse(BaseModel):
    conversation_id: str
    founder_id: int
    suggestions: list[SuggestionResponse]
    generated: int
    returned: int
    suppressed: int
    limited: bool

    @classmethod
    def from_domain(cls, collection) -> "SuggestionCollectionResponse":
        return cls(
            conversation_id=collection.conversation_id, founder_id=collection.founder_id,
            suggestions=[SuggestionResponse.from_domain(s) for s in collection.suggestions],
            generated=collection.metrics.generated, returned=collection.metrics.returned,
            suppressed=collection.metrics.suppressed_duplicates, limited=collection.trace.limited,
        )


class FeedbackResponse(BaseModel):
    feedback_id: str
    suggestion_id: str
    feedback_type: str
    created_at: datetime

    @classmethod
    def from_domain(cls, f) -> "FeedbackResponse":
        return cls(feedback_id=f.feedback_id, suggestion_id=f.suggestion_id,
                   feedback_type=f.feedback_type.value, created_at=f.created_at)
