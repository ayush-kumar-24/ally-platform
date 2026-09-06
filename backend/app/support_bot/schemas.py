"""Domain DTOs for the support bot.

Frozen dataclasses, not ORM rows and not Pydantic models -- the service returns
these and the API maps them to the wire, so the persistence layer can change
without touching either.

THE ONE RULE THIS FILE ENFORCES: `finding` and `note` never appear here. Those
two columns on support_bot_answers hold internal product observations -- defects
noticed while writing the answer, maintenance context, and in several cases
plain criticism of our own product. They are useful to the team and must never
reach a founder. Leaving them out of the domain object entirely means no
endpoint can leak them by forgetting to exclude them.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AnswerRef:
    """One published question and its answer, as the bot may use it."""

    question_id: int
    question: str
    answer: str
    links: tuple[str, ...] = ()
    group_title: str = ""


@dataclass(frozen=True)
class IndexEntry:
    """One line of the routing index: what a question is, and nothing else.

    Deliberately without the answer. The whole index is sent to the model to
    choose from, and including 277 answers would be a large prompt for a
    decision that only needs the questions.
    """

    question_id: int
    question: str


@dataclass(frozen=True)
class SupportReply:
    """What the bot came back with.

    `sources` is the answers the reply was built from -- always populated when
    `answered` is true, because an answer with no source is exactly the thing
    this design exists to prevent.
    """

    answer: str
    answered: bool
    sources: tuple[AnswerRef, ...] = ()
    links: tuple[str, ...] = ()
    escalate: bool = False
    #: Set when the reply did not come from the model -- "llm_unavailable",
    #: "no_match", "content_unavailable". Internal; useful in logs, and the API
    #: passes it through so the frontend can vary its wording if it wants to.
    reason: str | None = None


@dataclass(frozen=True)
class FaqEntry:
    """One entry for the Help page's FAQ list."""

    question_id: int
    question: str
    answer: str
    group_number: int
    group_title: str
    links: tuple[str, ...] = field(default=())
