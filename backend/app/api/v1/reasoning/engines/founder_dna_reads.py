"""One line saying what a Founder DNA dimension's answers show about the founder.

WHY THIS IS NOT THE SUMMARISER. founder_dna_summary.py compresses the founder's
answers into a shorter version of the same words, and is told in as many words
never to add "advice, praise, diagnosis". That is the right rule for a preview
and it is why the cards could never do their job: a card headed EMOTIONAL
INTELLIGENCE that holds a tidier quote is still not a read on how the founder
handles people. A founder told us exactly that -- "how is this matching the
emotional intelligence? what can we understand from this sentence about a
person's emotional intelligence?" -- about a card reading "Our Halol plant
head, Ramesh, 2022."

So this asks for the thing the heading promises, and the summariser keeps doing
what it does: the read leads the card, the founder's own words sit under it as
evidence they can check it against.

THE QUESTION GOES IN. The summariser is handed answers with no questions, which
is most of why it produced "The bridge" for two unrelated founders -- that is
the founder picking one of two options they were offered, and without the offer
it is a noun. A read cannot be written without knowing what was asked.

IT MUST BE ALLOWED TO SAY NOTHING, and this is the whole safety of it. These
questions ask for a moment, so an answer can be exact and empty: "Our Halol
plant head, Ramesh, 2022" identifies an episode without saying what happened in
it. There is no read in that, and a model pressed for one would invent a
founder. Returning nothing for a dimension is a first-class answer here, and
the caller drops the card rather than printing a fragment under a heading that
promises more.

FAILS OPEN: any error, timeout or unparseable reply returns {}, and the cards
fall back to the founder's own answers with the question above them.
"""

from __future__ import annotations

import json
import re

from app.core.logger import logger
from app.services.llm.base import LLMError, LLMMessage, LLMRequest, LLMRole
from app.services.llm.text import run_sync

#: A read is one or two sentences. Past that it is a paragraph competing with
#: the answer below it, and the card has two things saying the same thing.
_MAX_READ_CHARS = 240

#: Answers are trimmed before they go in the prompt -- the substance of a long
#: answer is near its start, and sending every answer whole turns one cheap
#: call into an expensive one.
_MAX_ANSWER_CHARS = 1200
_MAX_ANSWERS_PER_DIMENSION = 3

_SYSTEM = (
    "You write one line about a founder, for one facet of who they are, from "
    "their own answers in an interview.\n"
    "\n"
    "You are given the facet, the question they were asked, and what they "
    "said. Write ONE or TWO short sentences saying what their answer shows "
    "about them on that facet. Address them as 'you'.\n"
    "\n"
    "WHAT MAKES A GOOD LINE:\n"
    "- It says something about the PERSON, not about the episode. Not \"You "
    "had a problem with a plant head in 2022\" but \"You see a people problem "
    "early and sit on it longer than you should.\"\n"
    "- It is grounded in what they actually said. A reader who saw only their "
    "answer should recognise it.\n"
    "- Plain, everyday English. Short words. No jargon, no praise, no advice, "
    "no labels like 'high EQ' or 'Type A'.\n"
    "- It may name a concrete detail they gave, if that detail carries the "
    "point.\n"
    "\n"
    "WHEN TO SAY NOTHING -- READ THIS TWICE:\n"
    "Leave a facet OUT of your reply entirely when the answer does not "
    "support a line about the person. That is common and it is the correct "
    "answer, not a failure.\n"
    "- An answer that names a moment without describing it supports nothing. "
    "\"Our plant head, Ramesh, 2022\" and \"March, year-end\" are exact and "
    "empty: they identify an episode and say nothing about what happened in "
    "it, what the founder did, or what it cost.\n"
    "- A one-word or one-phrase answer to a choice supports nothing. \"The "
    "bridge\", \"Daily\", \"Monday\", \"2013\" are picks and dates, not "
    "descriptions.\n"
    "- If writing the line would need you to guess at the founder's feelings, "
    "reasons or behaviour, guess NOTHING and leave the facet out.\n"
    "Half the facets you are given may belong in neither list. Returning an "
    "empty object is a normal reply.\n"
    "\n"
    'Reply with JSON only: {"<facet_code>": "<one or two sentences>", ...}. '
    "Include only the facets you can write a grounded line for."
)


def _prompt(items: dict[str, dict]) -> str:
    parts = []
    for code, item in items.items():
        answers = [a for a in (item.get("answers") or []) if str(a).strip()]
        if not answers:
            continue
        lines = [f"FACET: {code.replace('_', ' ')}"]
        question = str(item.get("question") or "").strip()
        if question:
            lines.append(f"They were asked: {question}")
        for answer in answers[:_MAX_ANSWERS_PER_DIMENSION]:
            text = " ".join(str(answer).split())[:_MAX_ANSWER_CHARS]
            lines.append(f"They said: {text}")
        lines.append(f"(reply under the key \"{code}\")")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _clean(text: object) -> str:
    """One read line, trimmed, or "" for anything unusable."""
    if not isinstance(text, str):
        return ""
    line = " ".join(text.split())
    line = re.sub(r"^[-*•·]+\s*", "", line)
    if not line:
        return ""
    if len(line) > _MAX_READ_CHARS:
        line = line[:_MAX_READ_CHARS].rsplit(" ", 1)[0] + "…"
    return line


def _parse(text: str, wanted: set[str]) -> dict[str, str]:
    if not text:
        return {}
    blob = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", blob, re.DOTALL)
    if fenced:
        blob = fenced.group(1).strip()
    start, end = blob.find("{"), blob.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        data = json.loads(blob[start:end + 1])
    except (ValueError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out = {}
    for code, value in data.items():
        # A facet we did not ask about is dropped rather than trusted: it would
        # render as a card of its own on the frontend's generic grid.
        if code not in wanted:
            continue
        line = _clean(value)
        if line:
            out[code] = line
    return out


async def _generate(provider, request: LLMRequest, timeout_seconds: float) -> str:
    import asyncio

    result = await asyncio.wait_for(provider.generate(request), timeout=timeout_seconds)
    return result.text


def read_dimensions(provider, items: dict[str, dict],
                    *, timeout_seconds: float = 30.0) -> dict[str, str]:
    """`{dimension_code: read}` for whatever could be read honestly.

    `items` is `{code: {"question": str, "answers": [str, ...]}}`.

    Best-effort by contract: returns `{}` rather than raising, for any failure.
    A dimension missing from the result has no read, which the caller treats as
    "this card has nothing to say" -- see the module docstring.
    """
    body = _prompt(items)
    if not body:
        return {}

    request = LLMRequest(
        messages=(
            LLMMessage(role=LLMRole.SYSTEM, content=_SYSTEM),
            LLMMessage(role=LLMRole.USER, content=body),
        ),
        temperature=0.0,
        max_tokens=900,
    )
    try:
        text = run_sync(_generate(provider, request, timeout_seconds))
    except (LLMError, TimeoutError, OSError) as exc:
        logger.warning("founder DNA reads failed: %s", exc)
        return {}
    except Exception as exc:  # noqa: BLE001 -- never worth failing a page over
        logger.warning("founder DNA reads failed unexpectedly: %s", exc)
        return {}
    return _parse(text or "", set(items))
