"""Whether a founder's answer actually said anything.

A live ideation report printed "i dont remember" as the founder's CORE VALUES
card, repeated it in the Founder DNA prose ("A pattern worth naming: i dont
remember"), and quoted two "I'm not sure" answers under "These moments carried
the most weight". Every one of those is the report presenting a non-answer as
a finding about the person.

This is deliberately NOT a scoring change. A founder who says "I don't know
what one dabba costs me" is telling us something real and it must keep counting
against them. What is filtered here is narrower: text that carries no content
about the business at all, and only where the report would QUOTE it back as
though it did -- a DNA card, or an evidence quote.

Kept as a whitelist of whole phrases rather than a keyword search, because
"I'm not sure how I'd find out" and "I don't know if anyone would pay" are real
answers containing the same words. Matching the whole string (after stripping
punctuation and case) is the only rule that cannot swallow one of those.
"""
from __future__ import annotations

import re

#: Normalised forms of an answer that declines to answer. Apostrophes, case and
#: trailing punctuation are stripped before the comparison, so one entry covers
#: "I don't remember.", "i dont remember" and "I DONT REMEMBER".
_NON_ANSWERS = frozenset({
    "i dont remember",
    "i dont remember right now",
    "i dont know",
    "i dont know right now",
    "im not sure",
    "i am not sure",
    "not sure",
    "unsure",
    "i dont know yet",
    "dont know yet",
    "no idea",
    "cant remember",
    "i cant remember",
    "i dont want to answer this",
    "i dont want to answer",
    "prefer not to say",
    "skip",
    "skipped",
    "na",
    "n a",
    "no comment",
    "dont know",
    "dont remember",
})

# DELIBERATELY ABSENT: "nothing", "none", "pass", "zero". Each is a complete and
# informative answer to questions this diagnosis actually asks -- "what have you
# tried?" / "nothing", "how many people outside your network?" / "zero" -- and
# filtering them would delete the founder's strongest admissions from their own
# evidence section. A declined answer and a bleak answer are not the same thing.

_STRIP = re.compile(r"[^a-z0-9 ]+")
_SPACES = re.compile(r"\s+")


def _normalise(text: str) -> str:
    return _SPACES.sub(" ", _STRIP.sub("", text.lower())).strip()


def is_non_answer(text: object) -> bool:
    """True when `text` declines to answer rather than answering.

    Anything that is not a string, or is blank, counts as a non-answer -- the
    callers all use this to decide whether there is something worth printing.
    """
    if not isinstance(text, str):
        return True
    normalised = _normalise(text)
    return not normalised or normalised in _NON_ANSWERS


def said_something(text: object) -> bool:
    """The positive form, for filter() and comprehensions that read better."""
    return not is_non_answer(text)
