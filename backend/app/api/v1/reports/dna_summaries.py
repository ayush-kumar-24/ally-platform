"""Generate the Founder DNA card previews once, then read them back forever.

WHERE THE SUMMARIES LIVE. On the report itself, under `founder_dna["_summaries"]`
-- the same jsonb that already holds the dimensions they summarise. The leading
underscore is load-bearing: `factList()` in the frontend skips underscore-prefixed
keys, so this cannot accidentally render as a dimension card of its own, and
`resolve_phase2_dimensions` never writes a key that starts with one, so the two
cannot collide.

WHY LAZILY, ON READ, RATHER THAN AT GENERATION. Doing it in the generator would
mean every founder who already has a report -- which is all of them -- sees the
old wall of prose forever, or somebody runs a backfill over the whole table.
Filling the cache the first time a report's Founder DNA is opened covers old and
new reports with one code path, and costs one call per report, not one per view.

A GET THAT WRITES is unusual enough to say out loud: this writes a cache, not
founder data. Nothing the founder said changes, the answer to the request is the
same with or without it, and a failure to store is swallowed -- the page renders
from the answers themselves.
"""

from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.api.v1.reasoning.engines.founder_dna_summary import summarise_dimensions
from app.core.config import settings
from app.core.logger import logger
from app.models import FounderReport
from app.services.llm.router import LLMTask
from app.services.llm.tasks import provider_for_task

#: Keys inside `founder_dna` that are NOT a dimension of narrative answers.
#: `archetype` is a dict with its own card, origin/vision are single strings with
#: theirs, and chronic_state is the engine's own bookkeeping.
_NOT_A_DIMENSION = frozenset({"archetype", "origin", "vision", "chronic_state"})

SUMMARIES_KEY = "_summaries"


def _dimensions(founder_dna: dict) -> dict[str, list[str]]:
    """The dimensions worth summarising: lists of the founder's own answers."""
    out: dict[str, list[str]] = {}
    for code, value in (founder_dna or {}).items():
        if code.startswith("_") or code in _NOT_A_DIMENSION:
            continue
        if isinstance(value, list):
            answers = [str(v).strip() for v in value if isinstance(v, str) and v.strip()]
            if answers:
                out[code] = answers
    return out


def ensure_dna_summaries(db: Session, report: FounderReport) -> None:
    """Fill in any missing card previews for this report. Never raises.

    Only the dimensions with no summary yet are sent, so a report that gains a
    dimension later pays for that one rather than for all of them again, and a
    run that only half-succeeded is completed by the next read rather than
    redone.
    """
    if not settings.FOUNDER_DNA_SUMMARY_LLM:
        return

    founder_dna = report.founder_dna or {}
    dimensions = _dimensions(founder_dna)
    if not dimensions:
        return

    existing = founder_dna.get(SUMMARIES_KEY)
    existing = existing if isinstance(existing, dict) else {}
    missing = {code: answers for code, answers in dimensions.items() if code not in existing}
    if not missing:
        return

    try:
        provider = provider_for_task(
            db,
            LLMTask.FOUNDER_DNA_DIMENSION_RESOLUTION,
            founder_id=report.founder_id,
        )
        produced = summarise_dimensions(provider, missing)
    except Exception as exc:  # no provider configured, no routing row, anything
        logger.warning("founder DNA summaries unavailable: %s", exc)
        return

    if not produced:
        return

    try:
        merged = dict(founder_dna)
        merged[SUMMARIES_KEY] = {**existing, **produced}
        report.founder_dna = merged
        flag_modified(report, "founder_dna")
        db.commit()
    except Exception as exc:  # the page is fine without the cache being written
        logger.warning("could not store founder DNA summaries: %s", exc)
        db.rollback()
