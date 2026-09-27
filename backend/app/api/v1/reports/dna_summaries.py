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


def current_summaries(report: FounderReport) -> dict[str, list[str]]:
    """The card previews stored on this report right now, minus the empty ones.

    Read at RESPONSE time rather than taken from the narrative. The narrative is
    cached on narrative_snapshot the first time a report is opened, and the
    summaries are baked into it -- so a summary written afterwards could never
    reach the page, and filling the cache on a report whose snapshot already
    existed was work whose result nothing would ever read.
    """
    stored = (report.founder_dna or {}).get(SUMMARIES_KEY)
    if not isinstance(stored, dict):
        return {}
    return {
        code: [str(b) for b in bullets if isinstance(b, str) and b.strip()]
        for code, bullets in stored.items()
        if isinstance(bullets, list) and bullets
    }


def pending_dimensions(report: FounderReport) -> dict[str, list[str]]:
    """Dimensions with no summary attempt recorded yet -- what a run would send.

    Public so the endpoint can decide whether there is any work AT ALL before
    scheduling it, rather than starting a task that opens a database session to
    discover there is nothing to do.
    """
    if not settings.FOUNDER_DNA_SUMMARY_LLM:
        return {}
    founder_dna = report.founder_dna or {}
    dimensions = _dimensions(founder_dna)
    if not dimensions:
        return {}
    existing = founder_dna.get(SUMMARIES_KEY)
    existing = existing if isinstance(existing, dict) else {}
    return {code: answers for code, answers in dimensions.items() if code not in existing}


def ensure_dna_summaries(db: Session, report: FounderReport) -> None:
    """Fill in any missing card previews for this report. Never raises.

    Only the dimensions with no summary yet are sent, so a report that gains a
    dimension later pays for that one rather than for all of them again, and a
    run that only half-succeeded is completed by the next read rather than
    redone.

    NOT ON THE REQUEST PATH. This is a synchronous LLM call against a 25-second
    timeout: live-measured at 7.7s and 10.1s on two calls in ONE page load,
    beside 399ms for the Business DNA section that does everything else the same
    way. The endpoint schedules it after the response instead -- the first view
    of a report renders the founder's own answers, which is the documented
    fallback, and the view after that has the previews.
    """
    founder_dna = report.founder_dna or {}
    missing = pending_dimensions(report)
    if not missing:
        return

    existing = founder_dna.get(SUMMARIES_KEY)
    existing = existing if isinstance(existing, dict) else {}

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

    # ATTEMPTED, NOT JUST PRODUCED.
    #
    # `missing` is "every dimension with no summary yet", so a dimension the
    # model declines to summarise is missing again on the next read -- and the
    # one after that. The docstring's "a run that only half-succeeded is
    # completed by the next read" is the intent, and it is right for a call that
    # timed out; it is wrong for a dimension the model will never summarise.
    #
    # Those exist and are ordinary: the summariser is asked to turn a
    # dimension's answers into a few bullets, and a live report's dimensions
    # included "Monday.", "The bridge" and "It doesn't end." There is nothing to
    # summarise there, the model correctly returns nothing for them, and the
    # card falls back to the answer itself -- which is the right page. The cost
    # was that the call was made AGAIN on every subsequent view of that
    # founder's Founder DNA, synchronously, against a 25-second timeout, for a
    # result that was never going to arrive.
    #
    # Recording an empty list for an attempted dimension fixes it in one line
    # of intent: `code not in existing` is then False, so it is not re-sent, and
    # every reader already treats an empty list as no summary (payload.py's
    # dimension_summaries filters falsy bullets, and the card renders the
    # answers). One call per report, which is what the module docstring
    # promised.
    # ONLY after a call that actually came back with something. A total failure
    # -- no provider, a timeout, a malformed reply -- also returns {}, and
    # marking every dimension attempted off one network blip would disable this
    # founder's summaries permanently. An empty result still retries; a partial
    # one records what it declined.
    if not produced:
        return
    attempted = {code: list(produced.get(code) or ()) for code in missing}

    try:
        merged = dict(founder_dna)
        merged[SUMMARIES_KEY] = {**existing, **attempted, **produced}
        report.founder_dna = merged
        flag_modified(report, "founder_dna")
        db.commit()
    except Exception as exc:  # the page is fine without the cache being written
        logger.warning("could not store founder DNA summaries: %s", exc)
        db.rollback()
