"""StreamingGenerator (Phase 6, Milestone 3, Parts 2/4/6/7).

Wraps a ChatExecutionService: runs the normal chat flow (with assistant persistence
DEFERRED), converts the produced answer into deterministic chunks, and yields them
with cancellation + timeout checks between chunks. The assistant message is persisted
(via the M1 ConversationService) ONLY after all tokens stream and immediately before
COMPLETE -- so a cancel/timeout mid-stream never leaves an assistant reply behind.

No business logic is duplicated: generation is entirely `chat_service.send_message`;
this layer only controls delivery, chunking and persistence timing.

Chunking (Part 4): deterministic, provider-independent. Split by sentence; any
sentence longer than `max_chunk_size` falls back to word accumulation. Identical
input + config -> identical chunks.
"""

from __future__ import annotations

import re
import uuid
from typing import AsyncIterator, Callable, Iterator

from app.ai_chat.clock import Clock, SystemClock
from app.ai_chat.schemas.conversation import MessageRole, MessageTokenUsage
from app.ai_chat.streaming.events import EventLog, StreamingEventType
from app.ai_chat.streaming.schemas import (
    ChunkType,
    StreamingChunk,
    StreamingChatRequest,
    StreamingMetrics,
    StreamingResponse,
    StreamingTrace,
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
# One word plus whatever whitespace trails it, so a word-level split keeps the
# separators instead of discarding them -- see chunk_text.
_WORD_WITH_TRAILING_SPACE = re.compile(r"\S+\s*")


# --- deterministic chunking -------------------------------------------------


def _split_sentences(text: str) -> list[str]:
    """Sentences, each carrying the whitespace that FOLLOWED it.

    Slices the original string rather than splitting into stripped pieces,
    because the separators are content: a client's only way to rebuild the
    answer is to concatenate what it receives. See chunk_text below.
    """
    pieces: list[str] = []
    pos = 0
    for match in _SENTENCE_SPLIT.finditer(text):
        pieces.append(text[pos:match.end()])
        pos = match.end()
    if pos < len(text):
        pieces.append(text[pos:])
    return [p for p in pieces if p]


def _split_words(segment: str, max_chunk_size: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    # Each word together with the whitespace after it, so nothing is dropped at
    # a word boundary either.
    for word in _WORD_WITH_TRAILING_SPACE.findall(segment):
        if current and len(current) + len(word) > max_chunk_size:
            chunks.append(current)
            current = word            # an indivisible word longer than max stands alone
        else:
            current += word
    if current:
        chunks.append(current)
    return chunks


def chunk_text(text: str, max_chunk_size: int) -> list[str]:
    """Deterministic sentence-then-word chunking.

    Guarantees `"".join(chunk_text(t, n)) == t.strip()` -- the chunks are a
    partition of the answer, not a tidied-up version of it.

    That guarantee is the whole point and it was missing. Every piece used to be
    `.strip()`ed and every word `.split()`, so all whitespace BETWEEN chunks was
    silently discarded: a client concatenating the stream got sentences run
    together with no space, and -- far worse for this product -- every blank
    line gone. Ally answers in markdown, so losing the blank lines does not cost
    a space here and there, it collapses headings, paragraphs and list items
    into one unreadable run. Measured on a real reply: 451 characters in, 445
    out, one lost at each of the six chunk boundaries.
    """
    text = (text or "").strip()
    if not text:
        return []
    size = max(1, max_chunk_size)
    out: list[str] = []
    for sentence in _split_sentences(text):
        if len(sentence) <= size:
            out.append(sentence)
        else:
            out.extend(_split_words(sentence, size))
    return out


# --- cancellation + config --------------------------------------------------


class CancelToken:
    """Cooperative cancellation. `cancel()` from client disconnect or manual stop;
    the generator checks it between chunks."""

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled


class StreamingConfig:
    def __init__(self, *, default_max_chunk_size: int = 120, default_timeout_seconds: float | None = None):
        self.default_max_chunk_size = default_max_chunk_size
        self.default_timeout_seconds = default_timeout_seconds


# --- generator --------------------------------------------------------------


class StreamingGenerator:
    def __init__(
        self,
        *,
        chat_service,
        conversation_service,
        clock: Clock | None = None,
        id_factory: Callable[[], str] | None = None,
        config: StreamingConfig | None = None,
    ):
        self.chat_service = chat_service
        self.conversation_service = conversation_service
        self.clock = clock or SystemClock()
        self._new_id = id_factory or (lambda: uuid.uuid4().hex)
        self.config = config or StreamingConfig()

    # --- public: iterators ------------------------------------------------

    def stream(self, request: StreamingChatRequest, *, cancel: CancelToken | None = None,
               sink: list | None = None) -> Iterator[StreamingChunk]:
        return self._generate(request, cancel or CancelToken(), sink if sink is not None else [])

    def collect(self, request: StreamingChatRequest, *, cancel: CancelToken | None = None) -> StreamingResponse:
        sink: list[StreamingResponse] = []
        for _ in self._generate(request, cancel or CancelToken(), sink):
            pass
        return sink[0]

    async def astream(self, request: StreamingChatRequest, *, cancel: CancelToken | None = None,
                      sink: list | None = None) -> AsyncIterator[StreamingChunk]:
        for chunk in self._generate(request, cancel or CancelToken(), sink if sink is not None else []):
            yield chunk

    async def acollect(self, request: StreamingChatRequest, *, cancel: CancelToken | None = None) -> StreamingResponse:
        sink: list[StreamingResponse] = []
        async for _ in self.astream(request, cancel=cancel, sink=sink):
            pass
        return sink[0]

    # --- core generator ---------------------------------------------------

    def _generate(self, request: StreamingChatRequest, cancel: CancelToken,
                  sink: list) -> Iterator[StreamingChunk]:
        start = self.clock.now()
        request_id = request.request_id or self._new_id()
        events = EventLog()
        emitted: list[StreamingChunk] = []
        timeout = request.timeout_seconds if request.timeout_seconds is not None else self.config.default_timeout_seconds
        max_chunk = request.max_chunk_size or self.config.default_max_chunk_size
        state = {"conversation_id": request.conversation_id or "", "answer": "", "assistant_id": None, "chat_trace": None}

        def emit(chunk_type: ChunkType, content: str = "") -> StreamingChunk:
            chunk = StreamingChunk(chunk_type=chunk_type, content=content, index=len(emitted),
                                   final=chunk_type in {ChunkType.COMPLETE, ChunkType.ERROR, ChunkType.CANCELLED})
            emitted.append(chunk)
            return chunk

        def respond(*, completed: bool, cancelled: bool, timed_out: bool, ok: bool, error: str | None) -> None:
            finished = self.clock.now()
            duration = round((finished - start).total_seconds() * 1000, 3)
            metrics = StreamingMetrics(
                request_id=request_id, conversation_id=state["conversation_id"], start_time=start,
                duration_ms=duration, chunk_count=len(emitted),
                token_count=len(state["answer"].split()), cancelled=cancelled,
                timed_out=timed_out, completed=completed,
            )
            trace = StreamingTrace(
                request_id=request_id, conversation_id=state["conversation_id"], started_at=start,
                finished_at=finished, duration_ms=duration, events=events.events,
                chunk_count=len(emitted), completed=completed, cancelled=cancelled,
                timed_out=timed_out, chat_trace=state["chat_trace"],
            )
            sink.append(StreamingResponse(
                request_id=request_id, conversation_id=state["conversation_id"], ok=ok,
                answer=state["answer"], chunks=tuple(emitted), assistant_message_id=state["assistant_id"],
                metrics=metrics, trace=trace, cancelled=cancelled, timed_out=timed_out,
                completed=completed, error=error,
            ))

        # START
        events.record(StreamingEventType.START)
        yield emit(ChunkType.START)
        events.record(StreamingEventType.MESSAGE_RECEIVED)

        # Pre-generation cancel / timeout (nothing generated, nothing persisted).
        if cancel.cancelled:
            events.record(StreamingEventType.CANCELLED)
            yield emit(ChunkType.CANCELLED)
            respond(completed=False, cancelled=True, timed_out=False, ok=False, error="cancelled")
            return
        if self._over_deadline(start, timeout):
            events.record(StreamingEventType.ERROR, "timeout")
            yield emit(ChunkType.ERROR, "timeout")
            respond(completed=False, cancelled=False, timed_out=True, ok=False, error="timeout")
            return

        # Generate the answer -- assistant persistence DEFERRED.
        chat = self.chat_service.send_message(request.to_chat_request(request_id), persist_assistant=False)
        state["conversation_id"] = chat.conversation_id
        state["chat_trace"] = chat.trace
        steps = chat.trace.completed_steps
        if "build_context_window" in steps:
            events.record(StreamingEventType.CONTEXT_READY)
        if "render_prompt" in steps:
            events.record(StreamingEventType.PROMPT_READY)

        if not chat.ok:
            error = chat.error or "chat_failed"
            events.record(StreamingEventType.ERROR, error)
            yield emit(ChunkType.ERROR, error)
            respond(completed=False, cancelled=False, timed_out=False, ok=False, error=error)
            return

        state["answer"] = chat.answer
        events.record(StreamingEventType.AI_STARTED)

        for piece in chunk_text(chat.answer, max_chunk):
            if cancel.cancelled:
                events.record(StreamingEventType.CANCELLED)
                yield emit(ChunkType.CANCELLED)
                respond(completed=False, cancelled=True, timed_out=False, ok=False, error="cancelled")
                return
            if self._over_deadline(start, timeout):
                events.record(StreamingEventType.ERROR, "timeout")
                yield emit(ChunkType.ERROR, "timeout")
                respond(completed=False, cancelled=False, timed_out=True, ok=False, error="timeout")
                return
            events.record(StreamingEventType.TOKEN)
            yield emit(ChunkType.TOKEN, piece)

        events.record(StreamingEventType.AI_FINISHED)

        # Persist the assistant reply ONLY now -- after every token, before COMPLETE.
        if chat.answer and chat.answer.strip():
            usage = chat.metrics.token_usage
            message = self.conversation_service.append_message(
                chat.conversation_id, MessageRole.ASSISTANT, chat.answer,
                token_usage=MessageTokenUsage(usage.prompt_tokens, usage.completion_tokens),
                metadata={"request_id": request_id, "provider": chat.trace.provider,
                          "model": chat.trace.model, "streamed": True},
            )
            state["assistant_id"] = message.message_id
            events.record(StreamingEventType.MESSAGE_PERSISTED)

        events.record(StreamingEventType.COMPLETE)
        yield emit(ChunkType.COMPLETE)
        respond(completed=True, cancelled=False, timed_out=False, ok=True, error=None)

    def _over_deadline(self, start, timeout) -> bool:
        if timeout is None:
            return False
        return (self.clock.now() - start).total_seconds() > timeout
