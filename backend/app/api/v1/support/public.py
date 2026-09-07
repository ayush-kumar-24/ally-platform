"""The help bot, for people who are not signed in.

WHY THIS EXISTS. The most valuable question the bot can answer is "why can't I
sign in?", and that is the one question a signed-in bot can never be asked. A
founder locked out of their account has no route to help at all -- which is
exactly the person who most needs one.

WHY IT IS A SEPARATE MODULE AND NOT `auth=False` ON THE EXISTING ROUTE. The
authenticated endpoint's abuse protection is a per-founder rate limit, and an
anonymous caller has no founder. Removing the dependency would have left an
LLM-backed endpoint open to the whole internet with no counter on it at all --
free model access, billed to us, scriptable by anyone. The note in router.py
called this out and declined to ship it accidentally.

THREE LAYERS OF PROTECTION, because one is not enough for an anonymous endpoint
that costs money per call:

  1. PER-IP rate limit -- stops one person hammering it.
  2. A GLOBAL hourly ceiling -- stops a distributed script, which per-IP limits
     cannot see. This is the one that actually caps the bill.
  3. A SHORTER question limit than the authenticated route. A genuine "how do I
     log in" is a sentence; a 2,000-character prompt is somebody trying to use
     us as a free model.

When either limit is hit the visitor gets an honest reply pointing at email, not
an error. Someone locked out and asking for help must never meet a 429.

IDENTICAL ANSWERS. This runs the same service, the same content and the same
prompts as the signed-in bot. Two bots that answer the same question differently
is worse than one bot, and the whole point of the content living in the database
is that there is one source of truth.

COUNTERS ARE IN-PROCESS, deliberately. This is abuse protection, not billing.
A restart resets them; several instances each get their own budget. Both are
acceptable for a ceiling whose job is to stop a runaway, and neither is worth a
shared store on the critical path of a help widget.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.db.session import get_db
from app.support_bot.service import SupportBotService

router = APIRouter(prefix="/support/public", tags=["support"])

#: Per visitor. Generous for a real question, tight enough that scripting it is
#: pointless.
_IP_LIMIT = 8
_IP_WINDOW_S = 900.0            # 15 minutes

#: Across everyone, per hour. THE COST CEILING. Per-IP limits cannot see a
#: distributed script; this can. Sized so a normal launch day never reaches it
#: and a runaway stops within one hour of model spend.
_GLOBAL_LIMIT = 300
_GLOBAL_WINDOW_S = 3600.0

#: Shorter than the signed-in route's 2,000. A sign-in question is a sentence.
_MAX_QUESTION_CHARS = 500

_by_ip: dict[str, deque[float]] = defaultdict(deque)
_global: deque[float] = deque()

#: What a rate-limited visitor is told. Never an error -- this person may be
#: locked out and asking for help, and a 429 would be the second door closed in
#: their face.
_BUSY_REPLY = (
    "I am getting a lot of questions right now, so I cannot answer this one.\n\n"
    "Please write to info@goxl.in and a person will help you. If you cannot get "
    "into your account, say so at the top of your message and include the email "
    "address you signed up with."
)


def _client_ip(request: Request) -> str:
    """The caller's address, for counting only.

    X-Forwarded-For's first entry is the original client; later entries are
    proxy hops. Client-controllable, so this is a rate-limit key and nothing
    else -- it authorises nothing and is never trusted as identity.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return request.client.host if request.client else "unknown"


def _prune(q: deque[float], window: float, now: float) -> None:
    while q and now - q[0] > window:
        q.popleft()


def _allowed(ip: str) -> tuple[bool, str]:
    """(allowed, reason). Checks the global ceiling first -- it is the one that
    protects the bill, and there is no point letting a new IP through while the
    system as a whole is over budget."""
    now = time.monotonic()

    _prune(_global, _GLOBAL_WINDOW_S, now)
    if len(_global) >= _GLOBAL_LIMIT:
        return False, "global_hourly_cap"

    q = _by_ip[ip]
    _prune(q, _IP_WINDOW_S, now)
    if len(q) >= _IP_LIMIT:
        return False, "per_ip"

    q.append(now)
    _global.append(now)
    return True, ""


class PublicAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=_MAX_QUESTION_CHARS)


class PublicAskResponse(BaseModel):
    """Deliberately thinner than the signed-in response.

    No `sources` and no `links`: an anonymous visitor cannot open an in-app link
    anyway, and publishing which help entries exist tells anyone probing us more
    about the content set than they need. `answer` is always safe to render.
    """
    answer: str
    answered: bool
    escalate: bool = False


def get_public_support_service(db: Session = Depends(get_db)) -> SupportBotService:
    return SupportBotService(db)


@router.post("/ask", response_model=PublicAskResponse,
             summary="Ask the help bot a question without signing in")
async def ask_public(
    payload: PublicAskRequest,
    request: Request,
    service: SupportBotService = Depends(get_public_support_service),
) -> PublicAskResponse:
    """Same bot, same content, no account needed. Never 500s.

    `founder_id=0` is passed to the service purely because its signature wants
    one for its own per-founder limiter; the limiting that matters here has
    already happened above. It is not an identity and nothing is stored
    against it.
    """
    ip = _client_ip(request)
    allowed, reason = _allowed(ip)
    if not allowed:
        logger.info("public support bot rate limited", extra={"path": f"reason={reason}"})
        return PublicAskResponse(answer=_BUSY_REPLY, answered=False, escalate=True)

    reply = await service.answer(payload.question, founder_id=0)
    return PublicAskResponse(
        answer=reply.answer,
        answered=reply.answered,
        escalate=reply.escalate,
    )
