"""Sync text-completion bridge over the async provider layer.

Some engines (the report section narrator) are synchronous; the provider layer is
async. `make_sync_text` returns a plain `str -> str` callable that runs one LLM
call to completion, working whether or not an event loop is already running in the
calling thread. Errors propagate to the caller (the narrator catches them and
falls back to the template, recording the fallback)."""

from __future__ import annotations

import asyncio
import json
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


def loads_json(text: str) -> dict:
    """Parse a model reply that is supposed to be a JSON object.

    `json.loads(response.text)` is what four reasoning engines used to do, and
    it is a coin flip. `response_format={"type": "json_object"}` is an OpenAI
    parameter; the Anthropic adapter does not enforce it, so a reply arrives as
    bare JSON on most calls and, on the rest, wrapped in a ```json fence or
    introduced with a line of prose. The bare call then raises

        JSONDecodeError: Expecting value: line 1 column 1 (char 0)

    -- observed in production on RC-519, where the recommendation engine's
    fallback died and that root cause shipped with no recommendation at all.
    The engines' fail-open guards turn it into one warning line, so the visible
    result is simply less content than there should be.

    Taking the outermost {...} handles fences and chattiness in one rule,
    rather than enumerating the ways a model can decorate an object. Anything
    with no object in it is passed through untouched so the caller's own
    JSONDecodeError still fires and still says what came back.
    """
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start : end + 1] if 0 <= start < end else text)


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
