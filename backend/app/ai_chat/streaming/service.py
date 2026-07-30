"""StreamingChatService (Phase 6, Milestone 3, Part 3).

A thin delivery facade over the StreamingGenerator. It composes the existing
ChatExecutionService (never re-implements chat logic) and only controls delivery:
give it a founder + message (+ optional conversation), get a stream of chunks. It
exposes both a sync iterator and an async generator, plus `collect`/`acollect`
convenience methods that drive the stream to completion and return the aggregate
StreamingResponse.
"""

from __future__ import annotations

from typing import AsyncIterator, Callable, Iterator

from app.ai_chat.clock import Clock
from app.ai_chat.streaming.generator import CancelToken, StreamingConfig, StreamingGenerator
from app.ai_chat.streaming.schemas import StreamingChatRequest, StreamingChunk, StreamingResponse


class StreamingChatService:
    def __init__(
        self,
        *,
        chat_service,
        conversation_service,
        clock: Clock | None = None,
        id_factory: Callable[[], str] | None = None,
        config: StreamingConfig | None = None,
    ):
        self._generator = StreamingGenerator(
            chat_service=chat_service, conversation_service=conversation_service,
            clock=clock, id_factory=id_factory, config=config,
        )

    # --- streaming --------------------------------------------------------

    def stream(self, request: StreamingChatRequest, *, cancel: CancelToken | None = None,
               sink: list | None = None) -> Iterator[StreamingChunk]:
        return self._generator.stream(request, cancel=cancel, sink=sink)

    def astream(self, request: StreamingChatRequest, *, cancel: CancelToken | None = None,
                sink: list | None = None) -> AsyncIterator[StreamingChunk]:
        return self._generator.astream(request, cancel=cancel, sink=sink)

    # --- drive-to-completion ---------------------------------------------

    def collect(self, request: StreamingChatRequest, *, cancel: CancelToken | None = None) -> StreamingResponse:
        return self._generator.collect(request, cancel=cancel)

    async def acollect(self, request: StreamingChatRequest, *, cancel: CancelToken | None = None) -> StreamingResponse:
        return await self._generator.acollect(request, cancel=cancel)

    # --- convenience ------------------------------------------------------

    def send(self, founder_id: int, message: str, *, conversation_id: str | None = None,
             cancel: CancelToken | None = None, **kwargs) -> StreamingResponse:
        request = StreamingChatRequest(
            founder_id=founder_id, message=message, conversation_id=conversation_id, **kwargs
        )
        return self.collect(request, cancel=cancel)
