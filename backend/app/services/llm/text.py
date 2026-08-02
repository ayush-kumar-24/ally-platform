"""Sync text-completion bridge over the async provider layer.

Some engines (the report section narrator) are synchronous; the provider layer is
async. `make_sync_text` returns a plain `str -> str` callable that runs one LLM
call to completion, working whether or not an event loop is already running in the
calling thread. Errors propagate to the caller (the narrator catches them and
falls back to the template, recording the fallback)."""

from __future__ import annotations

import asyncio
import threading
from typing import Callable

from app.services.llm.base import LLMMessage, LLMProvider, LLMRequest, LLMRole


def run_sync(coro):
    """Run an async coroutine to completion from sync code, even if a loop is
    already running in this thread (then it runs on a short-lived worker thread)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    box: dict = {}
    def _worker():
        try:
            box["value"] = asyncio.run(coro)
        except BaseException as exc:  # surface it to the caller
            box["error"] = exc
    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join()
    if "error" in box:
        raise box["error"]
    return box["value"]


async def acomplete(provider: LLMProvider, prompt: str, *, max_tokens: int = 700) -> str:
    req = LLMRequest(
        messages=(LLMMessage(role=LLMRole.USER, content=prompt),),
        max_tokens=max_tokens,
    )
    return (await provider.generate(req)).text


def make_sync_text(provider: LLMProvider, *, max_tokens: int = 700) -> Callable[[str], str]:
    """A `str -> str` completion callable backed by `provider`."""
    def _call(prompt: str) -> str:
        return run_sync(acomplete(provider, prompt, max_tokens=max_tokens))
    return _call
