"""The support bot's flow: route, then answer, with a fallback at every step.

    founder question
        -> routing model picks up to 3 published answer ids from the index
        -> answering model writes a reply from ONLY those answers
        -> reply, with its sources

Both model calls are wrapped. If either fails, the bot falls back to keyword
search, and if that finds nothing it hands the founder to a person. It never
raises at the caller, and it never composes an answer from anything but
published content.

WHY THE ROUTING STEP IS A MODEL AND NOT A SEARCH. Keyword search was built and
measured first (`SupportContentRepository.search`, still used as the fallback).
Postgres full-text ANDs every word with plainto_tsquery, so "how much is a
discovery call" returned nothing at all. An OR-ranked version with the question
weighted above the body works, but still misses what a person catches -- "forgot
my password" barely reaches the answer titled "I've forgotten my password",
because the English stemmer does not join *forgot* to *forgotten*. The whole
index is ~4,000 tokens and has no vocabulary problem, so the model does the
matching and search stays as the safety net.

NOT METERED. Deliberately. Ally chat charges a founder's daily token allowance;
charging them to ask how to cancel would be indefensible. The protection here is
a per-founder rate limit, not a price.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections import defaultdict, deque

from sqlalchemy.orm import Session

from app.core.logger import logger
from app.support_bot.prompts import (
    ANSWER_SYSTEM,
    MAX_SOURCES,
    NO_MATCH_REPLY,
    ROUTING_SYSTEM,
    UNAVAILABLE_REPLY,
    answer_user_prompt,
    routing_user_prompt,
)
from app.support_bot.repository import SupportContentRepository
from app.support_bot.schemas import AnswerRef, FaqEntry, SupportReply

#: Per call. Routing returns a few numbers; answering is capped at ~120 words by
#: the prompt, and 400 tokens leaves room to run over rather than truncate
#: mid-sentence, which reads as the bot breaking.
ROUTING_MAX_TOKENS = 32
ANSWER_MAX_TOKENS = 400

#: A founder waiting on a help answer has already decided the product is
#: confusing. Twelve seconds is the point past which the fallback is kinder than
#: the wait.
ROUTING_TIMEOUT_S = 8.0
ANSWER_TIMEOUT_S = 12.0

#: Rate limit, per founder. Generous enough that nobody legitimately using help
#: will meet it, tight enough that the endpoint cannot be turned into free model
#: access. Counted in-process: this is abuse protection, not billing, and a
#: shared store is not worth the dependency for it.
RATE_LIMIT_CALLS = 20
RATE_LIMIT_WINDOW_S = 300.0

_calls: dict[int, deque[float]] = defaultdict(deque)


def _rate_limited(founder_id: int) -> bool:
    now = time.monotonic()
    q = _calls[founder_id]
    while q and now - q[0] > RATE_LIMIT_WINDOW_S:
        q.popleft()
    if len(q) >= RATE_LIMIT_CALLS:
        return True
    q.append(now)
    return False


def _parse_ids(text: str) -> list[int]:
    """Ids out of the routing reply.

    The prompt asks for bare comma-separated numbers, and models mostly comply
    -- but not always, so this reads numbers out of whatever came back rather
    than trusting the format. 'NONE', prose, an empty string and a refusal all
    correctly yield nothing.
    """
    if not text or "NONE" in text.upper():
        return []
    seen: list[int] = []
    for m in re.finditer(r"\d+", text):
        n = int(m.group())
        if n not in seen:
            seen.append(n)
    return seen[:MAX_SOURCES]


class SupportBotService:
    def __init__(self, db: Session, repository: SupportContentRepository | None = None):
        self.db = db
        self.repo = repository or SupportContentRepository(db)

    # --- public -----------------------------------------------------------

    def faq(self, limit: int | None = None) -> list[FaqEntry]:
        """The Help page's list, from the database rather than a hardcoded array."""
        return self.repo.faq(limit=limit)

    def is_available(self) -> bool:
        return self.repo.is_available()

    async def answer(self, question: str, *, founder_id: int) -> SupportReply:
        """Answer `question`. Never raises."""
        question = (question or "").strip()
        if not question:
            return SupportReply(answer=NO_MATCH_REPLY, answered=False,
                                escalate=True, reason="empty_question")

        if _rate_limited(founder_id):
            logger.info("support bot rate limited", extra={"founder_id": founder_id})
            return SupportReply(
                answer=("You have asked a lot of questions in a short time, so I am going to "
                        "pause for a few minutes.\n\n"
                        "If you need something now, message our team from Help & Support or "
                        "write to info@goxl.in."),
                answered=False, escalate=True, reason="rate_limited")

        if not self.repo.is_available():
            # Content not loaded -- a fresh clone, or RDS before the SQL is run.
            logger.warning("support bot asked but content table is unavailable")
            return SupportReply(answer=UNAVAILABLE_REPLY, answered=False,
                                escalate=True, reason="content_unavailable")

        sources = await self._route(question)
        if sources:
            reply = await self._compose(question, sources)
            if reply is not None:
                return reply
            # Model wrote nothing usable. The approved answer is still better
            # than an apology, so hand back the best source verbatim.
            best = sources[0]
            return SupportReply(answer=best.answer, answered=True, sources=(best,),
                                links=best.links, reason="verbatim_fallback")

        # Routing found nothing, or the model was unreachable.
        #
        # KEYWORD HITS ARE NO LONGER RETURNED VERBATIM. They used to be, and it
        # produced the worst failure this bot can have -- a confident, wrong,
        # off-topic answer. Measured: "give me a recipe for biryani" came back
        # with the credits-and-allowances answer, and "what is Ally" came back
        # explaining which file types can be uploaded. Keyword search always has
        # a best hit; it has no idea whether that hit answers the question.
        #
        # So the hits become CANDIDATES for the model rather than the reply. It
        # uses them when they fit, ignores them when they do not, and falls back
        # to what it knows about Ally -- or declines. An empty list is a real and
        # useful input here: "what is this?" matches no single row well, and the
        # ABOUT_ALLY block in the prompt is always there to answer it.
        #
        # This is also what makes the same question answer the same way twice.
        # Before, two accounts asking "how will it help me" got different replies
        # depending on which rows routing happened to grab that run.
        hits = self.repo.search(question, limit=2)
        reply = await self._compose(question, hits)
        if reply is not None:
            return SupportReply(
                answer=reply.answer, answered=True, sources=tuple(hits),
                links=reply.links,
                reason="keyword_grounded" if hits else "about_ally")

        # The model is unreachable AND keyword search found something. Better to
        # offer the closest published answer than nothing -- but say plainly that
        # it might not be the right one, which the verbatim path never did.
        if hits:
            return SupportReply(
                answer=("I could not work out a proper answer just now. This one "
                        "might be close:\n\n" + hits[0].answer),
                answered=True, sources=tuple(hits), links=hits[0].links,
                reason="keyword_verbatim_degraded")

        return SupportReply(answer=NO_MATCH_REPLY, answered=False,
                            escalate=True, reason="no_match")

    # --- steps ------------------------------------------------------------

    async def _route(self, question: str) -> list[AnswerRef]:
        """Which published answers fit. Empty on any failure."""
        index = self.repo.index()
        if not index:
            return []
        text = await self._generate(
            task_attr="SUPPORT_ROUTING",
            system=ROUTING_SYSTEM,
            user=routing_user_prompt(question, index),
            max_tokens=ROUTING_MAX_TOKENS,
            timeout=ROUTING_TIMEOUT_S,
        )
        if text is None:
            return []
        ids = _parse_ids(text)
        # by_ids drops anything unknown or unpublished, so a hallucinated number
        # costs one fewer source rather than an error.
        return self.repo.by_ids(ids)

    async def _compose(self, question: str, sources: list[AnswerRef]) -> SupportReply | None:
        """Write the reply from `sources` only. None if the model gave nothing."""
        text = await self._generate(
            task_attr="SUPPORT_ANSWER",
            system=ANSWER_SYSTEM,
            user=answer_user_prompt(question, sources),
            max_tokens=ANSWER_MAX_TOKENS,
            timeout=ANSWER_TIMEOUT_S,
        )
        if not text or not text.strip():
            return None
        links: list[str] = []
        for s in sources:
            for link in s.links:
                if link not in links:
                    links.append(link)
        return SupportReply(answer=text.strip(), answered=True,
                            sources=tuple(sources), links=tuple(links))

    async def _generate(self, *, task_attr: str, system: str, user: str,
                        max_tokens: int, timeout: float) -> str | None:
        """One model call. Returns None on ANY failure, having logged it.

        Imported inside the function, the same way the reports and impression
        paths do it, so importing this module never drags in httpx or a vendor
        adapter -- which matters because the FAQ read below has no model in it
        at all.
        """
        try:
            from app.services.llm import provider_for_task
            from app.services.llm.base import LLMMessage, LLMRequest, LLMRole
            from app.services.llm.router import LLMTask

            provider = provider_for_task(self.db, getattr(LLMTask, task_attr))
            request = LLMRequest(
                messages=(
                    LLMMessage(role=LLMRole.SYSTEM, content=system),
                    LLMMessage(role=LLMRole.USER, content=user),
                ),
                max_tokens=max_tokens,
                metadata={"task": getattr(LLMTask, task_attr)},
            )
            response = await asyncio.wait_for(provider.generate(request), timeout=timeout)
            return response.text
        except asyncio.TimeoutError:
            logger.warning("support bot: %s timed out after %ss", task_attr, timeout)
            return None
        except Exception:
            # Unconfigured, no routing row seeded, rate limited upstream, 5xx --
            # all the same from here. The founder still gets an honest reply.
            logger.warning("support bot: %s unavailable", task_attr, exc_info=True)
            return None


def build_support_bot_service(db: Session) -> SupportBotService:
    return SupportBotService(db)
