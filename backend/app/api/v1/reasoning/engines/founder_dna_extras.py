"""Founder DNA -- extra dimensions beyond Archetype/Core Motivation.

`archetype.py` is the only engine that has ever written into
`founder_reports.founder_dna`. This module adds the next tier of dimensions
that already have real data sitting unused elsewhere -- it does NOT invent
content for dimensions with no data source at all. That used to mean six
dimensions (Purpose & Mission, Core Values & Non-Negotiables, Mindset &
Excellence Standard, Energy Patterns, Decision Style, Focus/Attention &
Response Patterns); as of the phase-2 Founder DNA engine
(app/api/v1/founder_dna/) those six now have a real source --
`resolve_phase2_dimensions` below reads it. See
`GoXL_Founder_DNA_Decoding_Journey.docx` and the project decision recorded for
this work.

Three sources, three functions:
  * `origin_and_vision` -- the founder's own onboarding free text
    (`founders.founder_motivation` / `founders.vision_1_year`), passed through
    close to verbatim rather than paraphrased, per the doc's Section 6 intent
    ("in the founder's own language wherever possible, not GoXL's paraphrase").
  * `resolve_behavioural_dimensions` -- the seeded `blind_spots` /
    `behaviour_patterns` catalogues, resolved by the same detected-root-cause
    codes the internal report already uses (`ReasoningRepository`
    .get_blind_spots_by_root_cause_codes` /
    `.get_behaviour_patterns_by_root_cause_codes`), reading only the
    founder-safe interpretation columns (`what_it_actually_is`,
    `what_they_mean`/`empathy_response`) -- never `what_founder_says`/
    `what_they_say`, which are the founder's own self-view, not the finding.
  * `resolve_phase2_dimensions` -- the 6 Founder DNA phase-2 dimensions, read
    straight from `founder_dna_answers` (the founder's own words again, same
    "don't paraphrase" principle as origin/vision -- these are narrative
    answers, not catalogue findings, so there is nothing to interpret).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.reasoning.repository import ReasoningRepository
from app.models.diagnosis import Founder
from app.models.schema import FounderDnaAnswers, FounderDnaQuestions

_MAX_ITEMS = 3  # cap how many blind spots / patterns / answers surface per dimension


def origin_and_vision(founder: Founder) -> dict:
    """`{"origin": ..., "vision": ...}`, only the keys that have real text.

    Deliberately no LLM rewrite here -- the founder's own words, trimmed.
    """
    out: dict[str, str] = {}
    origin = (founder.founder_motivation or "").strip()
    if origin:
        out["origin"] = origin
    vision = (founder.vision_1_year or "").strip()
    if vision:
        out["vision"] = vision
    return out


def resolve_behavioural_dimensions(
    repository: ReasoningRepository, root_cause_codes: Sequence[str]
) -> dict:
    """`{"strengths_blind_spots": [...], "stress_response": [...],
    "communication_preference": [...]}`, only the keys that resolved to
    something. Best-effort by design: callers should wrap this in a
    try/except, matching the internal report's existing convention for this
    exact lookup (a catalogue-resolution miss must never fail report
    generation).
    """
    out: dict[str, list[str]] = {}
    if not root_cause_codes:
        return out

    blind_spots = repository.get_blind_spots_by_root_cause_codes(root_cause_codes)
    findings = [bs.what_it_actually_is for bs in blind_spots if bs.what_it_actually_is]
    if findings:
        out["strengths_blind_spots"] = findings[:_MAX_ITEMS]

    stress_patterns = repository.get_behaviour_patterns_by_root_cause_codes(
        root_cause_codes, pattern_type="stress_response"
    )
    stress_text = [
        bp.what_they_mean or bp.empathy_response
        for bp in stress_patterns
        if bp.what_they_mean or bp.empathy_response
    ]
    if stress_text:
        out["stress_response"] = stress_text[:_MAX_ITEMS]

    comm_patterns = repository.get_behaviour_patterns_by_root_cause_codes(
        root_cause_codes, pattern_type="communication_style"
    )
    comm_text = [
        bp.what_they_mean or bp.empathy_response
        for bp in comm_patterns
        if bp.what_they_mean or bp.empathy_response
    ]
    if comm_text:
        out["communication_preference"] = comm_text[:_MAX_ITEMS]

    return out


#: Asked dimensions whose answers must NOT be written to `founder_dna` under
#: their own code, because that key already has an owner with a different
#: shape. Keeping them out here is what stops the phase from silently
#: clobbering the archetype dict or turning origin/vision into lists that
#: ReportPayload's string handling would then fail on.
_RESERVED_KEYS = frozenset({
    "archetype",   # archetype.py owns this key (a dict). The archetype
                   # questions feed that engine's inference, not a card.
    "origin",      # single string on the payload; also onboarding text
    "vision",      # single string on the payload; also onboarding text
})


def resolve_phase2_dimensions(db: Session, founder_id: int) -> dict:
    """Founder DNA phase answers, keyed by dimension_code -- only dimensions
    the founder actually answered, and only those safe to key directly (see
    `_RESERVED_KEYS`). Each value is a list of that dimension's answer texts,
    oldest first, capped at `_MAX_ITEMS` -- same shape as
    `resolve_behavioural_dimensions`'s lists, for the same reason: one
    narrative answer rarely stands alone as "the" answer for a dimension, so
    the report/narrator layer gets the same small set a human reading the
    transcript would.

    `origin` and `vision` come back under `_origin_text` / `_vision_text` as
    single strings instead, so the caller can prefer a considered asked
    answer over the onboarding field without changing either one's shape.
    """
    stmt = (
        select(FounderDnaQuestions.dimension_code, FounderDnaAnswers.answer_text)
        .join(
            FounderDnaAnswers,
            FounderDnaAnswers.founder_dna_question_id
            == FounderDnaQuestions.founder_dna_question_id,
        )
        .where(FounderDnaAnswers.founder_id == founder_id)
        .order_by(FounderDnaAnswers.answered_at.asc())
    )
    by_dimension: dict[str, list[str]] = defaultdict(list)
    for dimension_code, answer_text in db.execute(stmt).all():
        if answer_text and answer_text.strip():
            by_dimension[dimension_code].append(answer_text.strip())

    out: dict = {
        code: answers[:_MAX_ITEMS]
        for code, answers in by_dimension.items()
        if code not in _RESERVED_KEYS
    }
    # Longest answer, not the first: these two are asked once per stage, but
    # a founder resuming or re-running leaves more than one, and the fuller
    # answer is the more useful one to show.
    for code, key in (("origin", "_origin_text"), ("vision", "_vision_text")):
        answers = by_dimension.get(code)
        if answers:
            out[key] = max(answers, key=len)
    return out
