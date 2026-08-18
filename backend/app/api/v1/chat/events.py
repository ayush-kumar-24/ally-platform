"""SSE event formatting (Phase 6, Milestone 6, Part 5).

Transport-only translation of the StreamingGenerator's chunk stream into the
`text/event-stream` wire format with the full event vocabulary. The generator
yields START / TOKEN* / COMPLETE|ERROR|CANCELLED; the finer lifecycle markers
(MESSAGE_RECEIVED, CONTEXT_READY, PROMPT_READY, AI_STARTED, AI_FINISHED,
MESSAGE_PERSISTED) are synthesised here from that stream -- no business logic, and
the frozen streaming layer is untouched.
"""

from __future__ import annotations

import json
from typing import Iterator

from app.ai_chat.streaming.schemas import ChunkType, StreamingChunk


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def sse_event_stream(
    chunks: Iterator[StreamingChunk],
    *,
    summary_sink: list | None = None,
) -> Iterator[str]:
    """Map chunks -> ordered SSE events. Persistence happens inside the generator as
    it is consumed here (deferred assistant persist after tokens, before COMPLETE).

    `summary_sink` is the list handed to StreamingGenerator.stream(sink=...). The
    generator appends its StreamingResponse there AFTER yielding its last chunk,
    so this emits one closing `summary` event once the chunk loop is exhausted.
    Without it a streaming client cannot learn the conversation_id or the
    assistant_message_id -- the chunk vocabulary carries only text and an index --
    which is the whole reason the app stayed on the blocking /chat/message.
    """
    pre_answer_emitted = False
    pending_complete: int | None = None

    def _pre_answer() -> Iterator[str]:
        yield _sse("context_ready", {})
        yield _sse("prompt_ready", {})
        yield _sse("ai_started", {})

    for chunk in chunks:
        ct = chunk.chunk_type
        if ct == ChunkType.START:
            yield _sse("start", {"index": chunk.index})
            yield _sse("message_received", {})
        elif ct == ChunkType.TOKEN:
            if not pre_answer_emitted:
                yield from _pre_answer()
                pre_answer_emitted = True
            yield _sse("token", {"content": chunk.content, "index": chunk.index})
        elif ct == ChunkType.COMPLETE:
            if not pre_answer_emitted:                       # completed with no tokens (empty answer)
                yield from _pre_answer()
                pre_answer_emitted = True
            yield _sse("ai_finished", {})
            yield _sse("message_persisted", {})
            # `complete` is DEFERRED to the end so it stays the terminal event.
            # The summary below can only be built once the generator has run past
            # its final chunk, and clients (and this repo's own SSE tests) treat
            # `complete` as "the stream is finished" -- emitting anything after it
            # would break that contract for the sake of ordering convenience.
            pending_complete = chunk.index
        elif ct == ChunkType.ERROR:
            yield _sse("error", {"content": chunk.content, "index": chunk.index})
        elif ct == ChunkType.CANCELLED:
            yield _sse("cancelled", {"index": chunk.index})

    # Closing summary. Appended by the generator after its final chunk, so it is
    # only readable once the loop above has run to exhaustion.
    if summary_sink:
        result = summary_sink[0]
        yield _sse("summary", {
            "conversation_id": result.conversation_id,
            "assistant_message_id": result.assistant_message_id,
            "ok": result.ok,
            "error": result.error,
            "completed": result.completed,
            "cancelled": result.cancelled,
            "timed_out": result.timed_out,
        })

    if pending_complete is not None:
        yield _sse("complete", {"index": pending_complete})
