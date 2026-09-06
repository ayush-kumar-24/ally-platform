"""Help & Support bot endpoints -- transport only.

    POST /support/ask     ask a question, get an answer built from published content
    GET  /support/faq     the published answers, for the Help page and the widget
    GET  /support/status  whether content is loaded (used by the widget to decide
                          between the live bot and its built-in fallback list)

All three delegate to SupportBotService. No business logic here.

WHY THIS IS BEHIND AUTH TODAY, AND WHY THAT HAS TO CHANGE. The team decided the
bot should also sit on the landing page, so a founder who cannot sign in can ask
why -- which is the single most valuable thing it could do, since every sign-in
question is asked by somebody locked out. That needs a public variant of /ask
with its own abuse protection (the rate limit here is per founder id, which a
signed-out caller does not have). Doing it properly is a separate piece of work;
shipping it accidentally by leaving auth off would be worse than waiting.

NOTHING HERE RETURNS `finding` OR `note`. They are absent from the domain
objects entirely (see support_bot/schemas.py), so it is not possible to leak
them by forgetting.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.db.session import get_db
from app.models import Founder
from app.support_bot import SupportBotService, build_support_bot_service

router = APIRouter(prefix="/support", tags=["support"])


def get_support_service(db: Session = Depends(get_db)) -> SupportBotService:
    return build_support_bot_service(db)


# --- wire models ------------------------------------------------------------

class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Capped so the routing prompt cannot be stuffed. A real help question is a
    #: sentence; anything past this is either a mistake or an attempt to use the
    #: endpoint as free model access.
    question: str = Field(min_length=1, max_length=1000)


class SourceOut(BaseModel):
    question_id: int
    question: str
    group_title: str = ""


class AskResponse(BaseModel):
    answer: str
    answered: bool
    escalate: bool
    links: list[str] = []
    #: What the reply was built from. Shown so a founder can see the bot is
    #: quoting real help content rather than improvising, and so support can
    #: tell which answer produced a complaint.
    sources: list[SourceOut] = []
    reason: str | None = None


class FaqOut(BaseModel):
    question_id: int
    question: str
    answer: str
    group_number: int
    group_title: str
    links: list[str] = []


class StatusOut(BaseModel):
    available: bool
    topics: int


# --- endpoints --------------------------------------------------------------

@router.post("/ask", response_model=AskResponse,
             summary="Ask the help bot a question about the product")
async def ask(
    payload: AskRequest,
    founder: Founder = Depends(get_founder_record),
    service: SupportBotService = Depends(get_support_service),
) -> AskResponse:
    """Never 500s and never guesses.

    Content missing, model down, nothing matched -- each has its own honest
    reply ending in "message a person", carried in `reason` for the logs. The
    caller can always render `answer` as-is.
    """
    reply = await service.answer(payload.question, founder_id=founder.founder_id)
    return AskResponse(
        answer=reply.answer,
        answered=reply.answered,
        escalate=reply.escalate,
        links=list(reply.links),
        sources=[SourceOut(question_id=s.question_id, question=s.question,
                           group_title=s.group_title) for s in reply.sources],
        reason=reply.reason,
    )


@router.get("/faq", response_model=list[FaqOut],
            summary="Published help answers, grouped")
def faq(
    limit: int | None = None,
    founder: Founder = Depends(get_founder_record),
    service: SupportBotService = Depends(get_support_service),
) -> list[FaqOut]:
    """What the Help page lists.

    Exists so the page can stop shipping a hardcoded array. The one it had went
    stale badly -- it told founders there was no download or share button on the
    report months after both shipped.
    """
    return [FaqOut(question_id=e.question_id, question=e.question, answer=e.answer,
                   group_number=e.group_number, group_title=e.group_title,
                   links=list(e.links))
            for e in service.faq(limit=limit)]


@router.get("/status", response_model=StatusOut,
            summary="Whether the help content is loaded")
def status(
    founder: Founder = Depends(get_founder_record),
    service: SupportBotService = Depends(get_support_service),
) -> StatusOut:
    """The widget calls this once on mount.

    Content lives in a table loaded by a SQL script rather than a migration, so
    a perfectly healthy deployment can be running without it. The widget uses
    this to choose between the live bot and its own built-in list, instead of
    discovering the gap on a founder's first question.
    """
    entries = service.faq()
    return StatusOut(available=service.is_available(), topics=len(entries))
