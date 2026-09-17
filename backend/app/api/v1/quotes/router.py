"""The founder's two lines for today.

ONE CALL, BOTH SURFACES. The Compass and Plan Your Day each show one line, and
they are chosen together so they can be guaranteed different -- so they are
served together too rather than as two endpoints that would each have to
re-derive the other's answer to avoid colliding with it.

NO MODEL CALL HAPPENS HERE. The nightly job has already chosen and stored;
this reads a row. The one exception is a founder with no row at all -- someone
who signed up after last midnight -- who gets the deterministic pick computed
and stored inline, which is arithmetic, not a request to anybody.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.core.logger import logger
from app.db.session import get_db
from app.models import Founder
from app.quotes.jobs import ensure_today
from app.quotes.service import SURFACES, resolve

router = APIRouter(prefix="/quotes", tags=["quotes"])


class DailyQuote(BaseModel):
    """One line, for one surface. No author field, deliberately -- every line
    in the catalogue is written for this product and attributed to nobody."""

    surface: str
    text: str


class DailyQuotes(BaseModel):
    """Today's lines. `quotes` may be short, or empty, if the catalogue has
    changed under a stored pick -- the card falls back to its own bundled list
    rather than rendering a blank, so an empty list here is safe."""

    quotes: list[DailyQuote] = []


@router.get("/today", response_model=DailyQuotes)
def today(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> DailyQuotes:
    """This founder's quote for each surface, fixed until midnight IST."""
    try:
        picks = ensure_today(db, founder.founder_id)
    except Exception as exc:  # a quote card is never worth a 500
        logger.warning("daily quotes unavailable", extra={"error": str(exc)})
        return DailyQuotes()

    out: list[DailyQuote] = []
    for surface in SURFACES:
        quote = resolve(picks.get(surface, ""))
        # A stored id with no line behind it means the catalogue lost that
        # entry since the pick was made. Skipping it lets the frontend fall
        # back for that one surface while the other still works.
        if quote is not None:
            out.append(DailyQuote(surface=surface, text=quote.text))
    return DailyQuotes(quotes=out)
