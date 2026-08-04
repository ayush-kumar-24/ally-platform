"""Get-or-generate the founder's first impression.

Order of preference:
  1. What we already stored -- an impression is formed once, not re-formed.
  2. The model, grounded in their onboarding answers.
  3. A read derived from those same answers by rule.

Step 3 is why nothing here raises for a founder who has finished onboarding.
The screen this feeds is the emotional high point of the flow; an error state
there is worse than a plainer sentence.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.api.v1.impression.derive import derive_impression
from app.api.v1.impression.facts import FounderFacts, facts_from_founder
from app.api.v1.impression.prompt import SYSTEM, build_prompt
from app.api.v1.impression.schemas import FirstImpression, FirstImpressionEnvelope
from app.models import Founder

logger = logging.getLogger("ally")

# Generous: this runs once per founder, behind a screen that is already playing
# a deliberate "thinking" animation. Still bounded, so a hung provider degrades
# to the derived read instead of holding the request open.
TIMEOUT_SECONDS = 25
MAX_TOKENS = 700

_BULLET_MAX = 150
_READ_MAX = 900


def _clip(text: str, limit: int) -> str:
    """Trim to `limit` without slicing a word in half.

    A cap is still needed -- the timeline these sit in has a fixed row -- but
    cutting mid-word ("...not just operationa") looks like a broken string, not
    a long sentence.
    """
    s = (text or "").strip()
    if len(s) <= limit:
        return s
    cut = s[:limit].rstrip()
    space = cut.rfind(" ")
    if space > limit * 0.6:          # only if it leaves something substantial
        cut = cut[:space].rstrip()
    return cut.rstrip(",;:.—-") + "…"


def _strip_fence(text: str) -> str:
    """Models like to wrap JSON in ```json fences even when told not to."""
    s = (text or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _parse(text: str) -> FirstImpression | None:
    """Turn the model's reply into an impression, or None if it isn't usable.

    Deliberately strict: a malformed or empty reply falls through to the derived
    read rather than showing the founder half a sentence.
    """
    raw = _strip_fence(text)
    if not raw:
        return None
    # Tolerate a stray sentence before or after the object.
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(raw[start:end + 1])
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    bullets = [
        _clip(str(b), _BULLET_MAX)
        for b in (data.get("bullets") or [])
        if str(b).strip()
    ][:4]
    read = _clip(str(data.get("read") or ""), _READ_MAX)
    instinct = _clip(str(data.get("instinct") or ""), _READ_MAX)

    if not bullets or not read or not instinct:
        return None

    return FirstImpression(
        bullets=bullets, read=read, instinct=instinct, source="llm",
    )


async def _generate_with_model(db: Session, founder: Founder, facts: FounderFacts) -> FirstImpression | None:
    """One grounded model call. Returns None on any failure -- never raises."""
    # Imported here, as the reports route does, so the derived path never pulls
    # in httpx or a vendor adapter.
    try:
        from app.services.llm import LLMTask, provider_for_task
        from app.services.llm.base import LLMMessage, LLMRequest, LLMRole

        provider = provider_for_task(
            db, LLMTask.FIRST_IMPRESSION, founder_id=founder.founder_id,
        )
        request = LLMRequest(
            messages=(
                LLMMessage(role=LLMRole.SYSTEM, content=SYSTEM),
                LLMMessage(role=LLMRole.USER, content=build_prompt(facts)),
            ),
            max_tokens=MAX_TOKENS,
            response_format={"type": "json_object"},
            metadata={"task": "first_impression", "founder_id": founder.founder_id},
        )
        response = await asyncio.wait_for(
            provider.generate(request), timeout=TIMEOUT_SECONDS,
        )
        return _parse(response.text)
    except asyncio.TimeoutError:
        logger.warning(
            "first impression: model timed out after %ss; using derived read",
            TIMEOUT_SECONDS, extra={"founder_id": founder.founder_id},
        )
        return None
    except Exception:
        # Unconfigured, no routing row, rate limited, upstream 5xx -- all the
        # same from here: the founder still gets a read.
        logger.warning(
            "first impression: model unavailable; using derived read",
            exc_info=True, extra={"founder_id": founder.founder_id},
        )
        return None


def _stored(founder: Founder) -> FirstImpression | None:
    data = founder.first_impression
    if not isinstance(data, dict) or not data:
        return None
    try:
        return FirstImpression(
            bullets=data["bullets"],
            read=data["read"],
            instinct=data["instinct"],
            source=data.get("source", "derived"),
            generated_at=founder.first_impression_at,
        )
    except (KeyError, TypeError, ValueError):
        # Shape changed under us -- regenerate rather than serve something broken.
        return None


def _persist(db: Session, founder: Founder, impression: FirstImpression) -> datetime:
    now = datetime.now(timezone.utc)
    founder.first_impression = {
        "bullets": impression.bullets,
        "read": impression.read,
        "instinct": impression.instinct,
        "source": impression.source,
    }
    founder.first_impression_at = now
    db.add(founder)
    db.commit()
    return now


async def get_or_create(db: Session, founder: Founder) -> FirstImpressionEnvelope:
    """The founder's first impression, generating and storing it on first ask."""
    existing = _stored(founder)
    if existing is not None:
        return FirstImpressionEnvelope(available=True, impression=existing)

    facts = facts_from_founder(founder)
    if not facts.complete_enough:
        # Nothing honest to say yet. The UI shows its own empty state.
        return FirstImpressionEnvelope(available=False, impression=None)

    impression = await _generate_with_model(db, founder, facts) or derive_impression(facts)

    try:
        generated_at = _persist(db, founder, impression)
        impression = impression.model_copy(update={"generated_at": generated_at})
    except Exception:
        # Failing to store it must not cost the founder the screen; they simply
        # get a fresh one next visit.
        db.rollback()
        logger.warning(
            "first impression: could not store; serving unsaved",
            exc_info=True, extra={"founder_id": founder.founder_id},
        )

    return FirstImpressionEnvelope(available=True, impression=impression)
