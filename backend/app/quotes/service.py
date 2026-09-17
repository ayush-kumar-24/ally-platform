"""Choosing each founder's two lines for the day.

THE SHAPE OF THIS, and why it is not one model call over the whole catalogue:

    founder -> context -> shortlist (code) -> pick two (model) -> store

The shortlist is the important step. Handing a model four hundred lines and
asking for the best two is both expensive and worse: it pays for four hundred
lines of prompt per founder per night, and a model choosing among forty
relevant candidates picks better than one scanning four hundred mostly
irrelevant ones. The narrowing is deterministic and cheap; only the judgement
is bought.

THE MODEL PICKS, IT NEVER WRITES. It returns two ids from the shortlist it was
given, and anything else -- an unknown id, one id twice, malformed JSON, a
provider outage -- is discarded in favour of the deterministic fallback below.
Nothing a model returns can put a sentence in front of a founder that was not
already written and reviewed in catalogue.py.

WHAT IS SENT ABOUT THE FOUNDER. Stage, industry, the themes inferred from their
challenges, and whether their last report raised flags. Not their name, not
their email, not their own words from the diagnosis. The prompt needs enough to
tell an ideation founder from a growth one; it does not need to identify anybody
to do that.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.quotes.catalogue import BY_ID, QUOTES, THEMES, Quote
from app.services.llm.base import LLMError, LLMMessage, LLMRequest, LLMRole
from app.services.llm.text import run_sync

#: The two places a quote card appears. Values match the frontend's `surface`
#: prop (components/QuoteCard.jsx), which is also what the API returns them as.
SURFACES = ("compass", "plan")

#: How many candidates the model gets. Enough that the choice is real, few
#: enough that the prompt stays around two thousand tokens.
SHORTLIST_SIZE = 40

#: A founder should not read the same line twice in a fortnight.
NO_REPEAT_DAYS = 14

_SYSTEM = (
    "You choose lines for a founder's dashboard from a fixed list. "
    "Pick the two that this specific founder is most likely to read and think "
    "'that is exactly where I am right now', based on their stage and what they "
    "are dealing with. The two must be different from each other. "
    "Choose only from the ids given. Never write a line of your own, never "
    "invent an id, never explain your choice. "
    'Reply with JSON only: {"compass": "<id>", "plan": "<id>"}'
)

# --- what we know about the founder -----------------------------------------

#: Words that appear in `founders.current_challenges` (and the report's red
#: flags) mapped to the themes they imply. Deliberately a small, readable table
#: rather than an embedding: it is inspectable, it is free, and when it gets a
#: founder wrong the reason is visible in one line of this file.
_CHALLENGE_THEMES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("customer", ("customers",)),
    ("user", ("customers",)),
    ("market", ("customers",)),
    ("sales", ("customers", "money")),
    ("revenue", ("money",)),
    ("fund", ("money",)),
    ("runway", ("money", "resilience")),
    ("cash", ("money",)),
    ("price", ("money",)),
    # "hiring", not just "hire": the two share no prefix past "hir" and the
    # gerund is what a founder actually writes. Caught by a test rather than in
    # production, where it would have looked like the table simply having an
    # opinion.
    ("hire", ("team",)),
    ("hiring", ("team",)),
    ("recruit", ("team",)),
    ("team", ("team",)),
    ("deleg", ("team", "focus")),
    ("co-founder", ("team", "decisions")),
    ("focus", ("focus",)),
    ("priorit", ("focus", "decisions")),
    ("time", ("focus",)),
    ("decision", ("decisions",)),
    ("direction", ("decisions", "doubt")),
    ("clarity", ("decisions", "doubt")),
    ("confidence", ("doubt",)),
    ("doubt", ("doubt",)),
    ("motivation", ("momentum", "resilience")),
    ("burn", ("rest", "resilience")),
    ("stress", ("rest", "resilience")),
    ("overwhelm", ("rest", "focus")),
    ("ship", ("execution",)),      # ship, shipping
    ("build", ("execution",)),     # build, building
    ("launch", ("execution",)),
    ("product", ("execution",)),
    ("scale", ("execution", "team")),
)


@dataclass(frozen=True)
class FounderContext:
    """What the shortlist and the prompt are allowed to know."""

    founder_id: int
    stage: str | None = None
    industry: str | None = None
    themes: tuple[str, ...] = field(default=())
    flagged: bool = False

    def describe(self) -> str:
        """The founder as a few words, for the prompt. No identifying fields."""
        parts = [f"stage: {self.stage or 'not recorded'}"]
        if self.industry:
            parts.append(f"industry: {self.industry}")
        if self.themes:
            parts.append(f"currently dealing with: {', '.join(self.themes)}")
        if self.flagged:
            parts.append("their latest diagnosis raised concerns")
        return " | ".join(parts)


def _slug(stage_name: str | None) -> str | None:
    """"Early Traction" -> "early-traction", matching catalogue.STAGES."""
    if not stage_name:
        return None
    return "-".join(str(stage_name).lower().split())


def _themes_from(values) -> tuple[str, ...]:
    """Themes implied by a founder's challenges, in catalogue order.

    Accepts the several shapes `current_challenges` actually holds across
    onboarding versions -- a list, a dict of flags, a bare string -- because a
    jsonb column with no schema is what it is, and a TypeError here would take
    down a nightly job over somebody's profile."""
    if isinstance(values, dict):
        blob = " ".join(str(k) for k, v in values.items() if v) + " " + str(values)
    elif isinstance(values, (list, tuple)):
        blob = " ".join(str(v) for v in values)
    else:
        blob = str(values or "")
    blob = blob.lower()

    found: set[str] = set()
    for needle, themes in _CHALLENGE_THEMES:
        if needle in blob:
            found.update(themes)
    # Catalogue order, so the prompt and the shortlist read consistently rather
    # than in whatever order a set happened to iterate.
    return tuple(t for t in THEMES if t in found)


def build_context(db: Session, founder_id: int) -> FounderContext:
    """Read the founder's situation. Best-effort: an empty profile is a valid
    answer (a founder who signed up this morning has one), and yields the
    stage-agnostic shortlist rather than an error."""
    row = db.execute(
        text(
            "select s.stage_name, f.industry, f.current_challenges "
            "from founders f left join founder_stages s on s.stage_id = f.stage_id "
            "where f.founder_id = :fid"
        ),
        {"fid": founder_id},
    ).mappings().first()
    if row is None:
        return FounderContext(founder_id=founder_id)

    flagged = bool(
        db.execute(
            text(
                "select 1 from founder_reports "
                "where founder_id = :fid and business_dna is not null "
                "and jsonb_array_length(coalesce(business_dna->'red_flags', '[]'::jsonb)) > 0 "
                "limit 1"
            ),
            {"fid": founder_id},
        ).first()
    )

    return FounderContext(
        founder_id=founder_id,
        stage=_slug(row["stage_name"]),
        industry=(row["industry"] or None),
        themes=_themes_from(row["current_challenges"]),
        flagged=flagged,
    )


# --- narrowing ---------------------------------------------------------------

def shortlist(ctx: FounderContext, *, exclude: frozenset[str] = frozenset(),
              size: int = SHORTLIST_SIZE) -> list[Quote]:
    """The candidates this founder gets to be chosen among.

    Ranked, not filtered, on theme: a founder whose challenges imply `money`
    should see the money lines first, but a catalogue slice containing ONLY
    money lines would hand them the same two every fortnight. Stage is a real
    filter -- a hiring line does not belong in front of someone who has no team
    yet -- and the stage-agnostic lines are always in play.

    `exclude` is what they have already read recently. It is applied before the
    cut rather than after, so excluding a line promotes the next one in instead
    of shortening the list.
    """
    pool = [
        q for q in QUOTES
        if q.id not in exclude and (not q.stages or not ctx.stage or ctx.stage in q.stages)
    ]
    # A founder who has read everything recently gets the whole catalogue back
    # rather than an empty card.
    if not pool:
        pool = [q for q in QUOTES if not q.stages or not ctx.stage or ctx.stage in q.stages]
    if not pool:
        pool = list(QUOTES)

    wanted = set(ctx.themes)

    def rank(q: Quote) -> tuple[int, int, str]:
        overlap = len(wanted.intersection(q.themes))
        # Stage-specific before stage-agnostic at equal overlap: it is the more
        # particular line, which is the whole point of the exercise.
        specific = 1 if q.stages else 0
        return (-overlap, -specific, q.id)

    return sorted(pool, key=rank)[:size]


# --- the pick ----------------------------------------------------------------

def _stable_index(founder_id: int, day: date, salt: str, modulo: int) -> int:
    """A stable number for this founder, this day, this surface.

    Hashed rather than `founder_id % n`: ids are sequential, so the modulo of
    two founders who signed up minutes apart differs by one, and they would sit
    next to each other in the catalogue every single day.
    """
    key = f"{founder_id}:{day.isoformat()}:{salt}".encode()
    return int.from_bytes(hashlib.sha256(key).digest()[:8], "big") % max(modulo, 1)


def fallback_pick(ctx: FounderContext, candidates: list[Quote], day: date) -> dict[str, str]:
    """Two different lines, no model involved.

    This is what runs when the flag is off, when the provider is down, when the
    reply is unusable -- and on the very first read for a founder who signed up
    after last midnight. It is not a degraded mode anybody should be able to
    spot: the lines are from the same shortlist the model would have chosen
    from, and they are stable for the day like any other pick.
    """
    if not candidates:
        candidates = list(QUOTES)
    first = _stable_index(ctx.founder_id, day, "compass", len(candidates))
    # Offset by an odd stride so the two never collide, whatever the length.
    second = (first + 1 + _stable_index(ctx.founder_id, day, "plan", max(len(candidates) - 1, 1))) % len(candidates)
    if second == first:
        second = (first + 1) % len(candidates)
    return {"compass": candidates[first].id, "plan": candidates[second].id}


def _parse(reply: str, allowed: set[str]) -> dict[str, str] | None:
    """The reply, or None if it is not two distinct ids from `allowed`.

    Permissive about the envelope -- models wrap JSON in prose often enough that
    refusing those would throw away good answers -- and strict about the
    content, because an id that is not in the shortlist is the shape a made-up
    line arrives in.
    """
    start, end = reply.find("{"), reply.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(reply[start : end + 1])
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    picked = {}
    for surface in SURFACES:
        value = data.get(surface)
        if not isinstance(value, str) or value not in allowed:
            return None
        picked[surface] = value
    if len(set(picked.values())) != len(SURFACES):
        return None  # the same line on both pages is the thing we set out to avoid
    return picked


async def _generate(provider, request: LLMRequest, timeout_seconds: float) -> str:
    import asyncio

    result = await asyncio.wait_for(provider.generate(request), timeout=timeout_seconds)
    return result.text


def model_pick(provider, ctx: FounderContext, candidates: list[Quote],
               *, timeout_seconds: float = 20.0) -> dict[str, str] | None:
    """Ask the model to choose two. `None` on any failure at all -- the caller
    falls back, and a founder never learns which one happened."""
    if len(candidates) < len(SURFACES):
        return None

    listing = "\n".join(f"{q.id}: {q.text}" for q in candidates)
    body = f"Founder -- {ctx.describe()}\n\nLines to choose from:\n{listing}"

    request = LLMRequest(
        messages=(
            LLMMessage(role=LLMRole.SYSTEM, content=_SYSTEM),
            LLMMessage(role=LLMRole.USER, content=body),
        ),
        temperature=0.0,
        max_tokens=120,
        response_format={"type": "json_object"},
    )
    try:
        reply = run_sync(_generate(provider, request, timeout_seconds))
    except (LLMError, TimeoutError, OSError) as exc:
        logger.warning("daily quote pick failed", extra={"error": str(exc)})
        return None
    except Exception as exc:  # a quote is never worth failing a nightly job over
        logger.warning("daily quote pick failed unexpectedly", extra={"error": str(exc)})
        return None

    return _parse(reply or "", {q.id for q in candidates})


def resolve(quote_id: str) -> Quote | None:
    """A stored id back to its line, or None when the line has since been
    removed from the catalogue -- the caller re-picks rather than rendering an
    empty card."""
    return BY_ID.get(quote_id)
