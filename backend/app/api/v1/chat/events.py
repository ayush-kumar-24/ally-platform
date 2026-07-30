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


def sse_event_stream(chunks: Iterator[StreamingChunk]) -> Iterator[str]:
    """Map chunks -> ordered SSE events. Persistence happens inside the generator as
    it is consumed here (deferred assistant persist after tokens, before COMPLETE)."""
    pre_answer_emitted = False

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
            yield _sse("complete", {"index": chunk.index})
        elif ct == ChunkType.ERROR:
            yield _sse("error", {"content": chunk.content, "index": chunk.index})
        elif ct == ChunkType.CANCELLED:
            yield _sse("cancelled", {"index": chunk.index})
