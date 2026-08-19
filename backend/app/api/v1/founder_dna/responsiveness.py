"""Is this actually an answer to the question that was asked?

Live testing found the phase would accept the QUESTION ITSELF pasted back as
an answer, save it, and move on -- so the conversation read as if Ally never
looked at what was written. Nothing between the client and the database
checked responsiveness: the only validation was `answer_text` being
non-blank (schemas.SubmitFounderDnaAnswerRequest).

Deliberately DETERMINISTIC, not another LLM call. Two reasons:

  * cost and latency. POST /answer already spends one LLM call on dimension
    resolution; adding a second in front of the write would double the wait
    on every turn to catch a case that is unambiguous in plain Python.
  * a judge that is only ~right is worse than no judge here. Rejecting a
    real answer is a much worse failure than accepting a lazy one, so the
    rules below are narrow on purpose -- each one fires only where there is
    no honest reading of the input as an answer.

What is NOT gated, on purpose: short answers, vague answers, "I don't know".
Those are answers -- often revealing ones -- and they are exactly what the
dimension-resolution advisor exists to judge. Gating them would trap a
founder in a reprompt loop over a question they genuinely cannot answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Words carrying no topical signal. Kept small on purpose -- this is used to
#: decide whether an answer merely REPEATS the question, so only words that
#: would appear in both regardless of content belong here.
_STOPWORDS = frozenset(
    """
    a an the and or but if then than that this these those of in on at to for
    with from by as is are was were be been being do does did doing have has
    had you your yours my me mine we our us it its i am so about into over
    what when where which who whom how why tell me last time about
    """.split()
)

_WORD = re.compile(r"[a-z0-9']+")

#: How much of the answer's vocabulary can come from the question before it
#: stops being an answer. 0.8 rather than 1.0 so a paste with a typo, a
#: trailing "?" removed, or one word changed still counts as an echo.
_ECHO_OVERLAP = 0.8

#: ...paired with a cap on genuinely NEW words. Reusing the question's words
#: is normal ("the last time someone pointed something out was...") -- what
#: makes an echo an echo is reusing them and adding nothing. Both conditions
#: must hold.
_ECHO_MAX_NEW_WORDS = 2

#: Below this the overlap ratio is noise: a two-word answer that happens to
#: share both words with the question is not a paste.
_ECHO_MIN_WORDS = 4


@dataclass(frozen=True)
class Rejection:
    """Why the answer was not accepted, and what Ally should say back.

    `reprompt` is founder-facing copy, not an error string -- a rejected turn
    is a conversational beat ("that's my question back at me"), not a failure
    the client should render as a broken save.
    """

    reason: str
    reprompt: str


def _content_words(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS]


def _is_echo(question_text: str, answer_text: str) -> bool:
    """True when the answer is the question handed back.

    Requires BOTH that almost all of the answer's vocabulary came from the
    question AND that it introduced essentially nothing new -- either alone
    produces false positives on real answers that quote the question before
    answering it.
    """
    answer_words = _content_words(answer_text)
    if len(answer_words) < _ECHO_MIN_WORDS:
        return False

    question_words = set(_content_words(question_text))
    if not question_words:
        return False

    answer_set = set(answer_words)
    borrowed = len(answer_set & question_words) / len(answer_set)
    new_words = len(answer_set - question_words)
    return borrowed >= _ECHO_OVERLAP and new_words <= _ECHO_MAX_NEW_WORDS


def _has_letters(text: str) -> bool:
    return any(ch.isalpha() for ch in text)


def check(
    *,
    question_text: str,
    question_format: str,
    options: list[str] | None,
    answer_text: str,
) -> Rejection | None:
    """None when the answer may be saved, otherwise why it may not.

    A picked option short-circuits to accepted. Note this is NOT the same as
    requiring one: FounderDnaChat's own placeholder invites free text on a
    pick-one ("Pick one above -- or type if none of them fit"), so rejecting
    a typed answer here would break a promise the UI makes on screen. Anything
    else on a forced-choice question falls through to the general rules below,
    which is what catches the question being pasted back into one.
    """
    cleaned = answer_text.strip()

    if question_format == "forced_choice" and options:
        picked = cleaned.casefold()
        if any(picked == opt.strip().casefold() for opt in options):
            return None

    if not _has_letters(cleaned):
        return Rejection(
            reason="no_content",
            reprompt=(
                "I didn't get anything I can read there. Take another run at "
                "it — a rough answer in your own words is plenty."
            ),
        )

    if _is_echo(question_text, cleaned):
        return Rejection(
            reason="echo",
            reprompt=(
                "That's my question handed back to me — I need your side of "
                "it. Even a half-formed answer or a single specific moment "
                "tells me more than a polished one."
            ),
        )

    return None
