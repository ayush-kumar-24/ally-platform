"""Short bullet summaries of a founder's own Founder DNA answers.

WHY THIS EXISTS. Each Founder DNA dimension holds up to three of the founder's
own narrative answers -- often several hundred words apiece. The card grid shows
every dimension at once, so at full length the page is a wall of prose nobody
scans. The founder wants the gist on the card and the whole answer behind "Read
more".

Cutting the paragraph down mechanically (first sentence, first N words) does not
produce the gist; it produces a sentence fragment that happens to be first. What
is wanted is a summary, and a summary is a judgement about meaning -- so this
asks the model.

THREE BOUNDARIES, because each is a way this could go wrong quietly:

* IT SUMMARISES, IT NEVER REPLACES. The founder's answers are stored untouched
  and are what "Read more" shows. These bullets are a preview of text the reader
  can always open in full, which is what makes a lossy rendering of someone's
  own words acceptable at all.

* IT NEVER INVENTS. The prompt forbids adding advice, judgement or any fact not
  in the answer, and the validator drops anything for a dimension that was not
  asked about. A bullet that asserts something the founder did not say would be
  the model putting words in their mouth on a page titled "your profile".

* IT FAILS TO NOTHING. Any provider error, timeout, malformed reply or
  unrecognised key returns an empty dict, and the card falls back to showing the
  answers themselves. A missing summary costs the reader some scrolling; a wrong
  one costs them their own profile.

ONE CALL FOR THE WHOLE SECTION, not one per dimension: eight dimensions is eight
round trips and eight times the fixed prompt overhead, for work the model can do
in a single pass. `reports/dna_summaries.py` then stores the result on the report,
so the cost is once per report and not once per page view.
"""

from __future__ import annotations

import json
import re

from app.core.logger import logger
from app.services.llm.base import LLMError, LLMMessage, LLMRequest, LLMRole
from app.services.llm.text import run_sync

_SYSTEM = (
    "You compress a founder's own answers into a short preview. "
    "For each dimension you are given, write 2 or 3 bullets that say what the "
    "founder actually said, in their own vocabulary, each under 14 words and "
    "written as a plain statement with no leading dash or bullet character. "
    "Never add advice, praise, diagnosis, or any fact that is not in the answer. "
    "Never write a bullet for a dimension that is not in the input. "
    'Reply with JSON only: {"<dimension_code>": ["<bullet>", "<bullet>"], ...}'
)

#: Bullets past this are not previews any more, they are the paragraph again.
_MAX_BULLETS = 3
_MAX_BULLET_CHARS = 120

#: Each answer is trimmed before it goes in the prompt. The gist of a 2,000-word
#: answer is in its opening far more often than it is in its tail, and sending
#: every answer whole is what turns one cheap call into an expensive one.
_MAX_ANSWER_CHARS = 1200
_MAX_ANSWERS_PER_DIMENSION = 3

_LEADING_BULLET = re.compile(r"^\s*[-*•·]+\s*")


def _prompt(dimensions: dict[str, list[str]]) -> str:
    parts = []
    for code, answers in dimensions.items():
        joined = "\n".join(
            f"- {a.strip()[:_MAX_ANSWER_CHARS]}"
            for a in answers[:_MAX_ANSWERS_PER_DIMENSION]
            if a and a.strip()
        )
        if joined:
            parts.append(f"{code}:\n{joined}")
    return "\n\n".join(parts)


def _clean(text: str) -> str:
    """One bullet, stripped of any list punctuation the model added anyway."""
    return _LEADING_BULLET.sub("", str(text)).strip()[:_MAX_BULLET_CHARS]


def _parse(reply: str, allowed: set[str]) -> dict[str, list[str]]:
    """Validate the reply into `{code: [bullet, ...]}`, dropping everything else.

    Permissive about the envelope (models wrap JSON in prose or a code fence
    often enough that refusing those would mean discarding good answers), strict
    about the content: an unknown dimension code is never accepted, because that
    is the shape a hallucinated dimension arrives in.
    """
    start, end = reply.find("{"), reply.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(reply[start : end + 1])
    except (ValueError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}

    out: dict[str, list[str]] = {}
    for code, bullets in data.items():
        if code not in allowed or not isinstance(bullets, list):
            continue
        cleaned = [_clean(b) for b in bullets if isinstance(b, (str, int, float))]
        cleaned = [b for b in cleaned if b][:_MAX_BULLETS]
        if cleaned:
            out[code] = cleaned
    return out


def summarise_dimensions(provider, dimensions: dict[str, list[str]],
                         *, timeout_seconds: float = 25.0) -> dict[str, list[str]]:
    """`{dimension_code: [bullet, ...]}` for whatever the model summarised well.

    Best-effort by contract: returns `{}` rather than raising, for any failure at
    all. Callers render the founder's answers when a dimension is missing here,
    so an empty result is a degraded page, never a broken one.
    """
    body = _prompt(dimensions)
    if not body:
        return {}

    request = LLMRequest(
        messages=(
            LLMMessage(role=LLMRole.SYSTEM, content=_SYSTEM),
            LLMMessage(role=LLMRole.USER, content=body),
        ),
        temperature=0.0,
        max_tokens=700,
    )
    try:
        reply = run_sync(_generate(provider, request, timeout_seconds))
    except (LLMError, TimeoutError, OSError) as exc:
        logger.warning("founder DNA summary failed: %s", exc)
        return {}
    except Exception as exc:  # a summary is never worth failing a page load over
        logger.warning("founder DNA summary failed unexpectedly: %s", exc)
        return {}
    return _parse(reply or "", set(dimensions))


async def _generate(provider, request: LLMRequest, timeout_seconds: float) -> str:
    import asyncio

    result = await asyncio.wait_for(provider.generate(request), timeout=timeout_seconds)
    return result.text
