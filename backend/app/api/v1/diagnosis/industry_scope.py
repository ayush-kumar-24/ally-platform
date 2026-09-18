"""Which questions this founder's INDUSTRY makes it sensible to ask.

A FOURTH AXIS, and deliberately separate from the three that came before it:

    stage_scope     "is this founder far enough along to have an answer?"
    context_scope   "is this subject part of their situation at all?"  (fundraising)
    industry_scope  "is this question written for the kind of business they run?"

WHY THE DATA LIVES WHERE IT DOES. `questions.industry_relevance` is a jsonb array
of industry codes, or `["all"]`. The shape predates this module -- it is the same
one `interventions.industry_relevance` has always used -- and the column was
added by migration 62ebd946ebc0 with `["all"]` as the default, so all 3,340
pre-existing questions stayed universal without being touched. That default is
what makes the hybrid question architecture work: universal questions are not
duplicated per industry, industry-specific ones are simply tagged.

QUESTION-LEVEL METADATA IS AUTHORITATIVE, AND IS THE ONLY THING CONSULTED.
`problems.industry_relevance` and `root_causes.industry_relevance` exist too, and
this module ignores both. They describe how relevant a diagnostic INTERPRETATION
is, not whether a question may be asked. Inheriting from them would let a
problem tagged `["agritech"]` silently remove a question its own author marked
`["all"]` -- a restriction nobody wrote, appearing from a join. Where the three
disagree, `validate_industry_metadata` REPORTS it; nothing reconciles it
automatically.

UNKNOWN INDUSTRY IS NOT `["all"]`. They are different states and the difference
matters:

    industry = agritech   ->  ["healthtech"] is removed
    industry = unknown    ->  ["healthtech"] is KEPT, marked uncertain

46 of 47 production founders had no resolvable industry before the Step 2
writers landed. Treating "we never asked" as a filter would have quietly taken
questions away from exactly the founders whose profiles are least complete. So
an unknown industry removes nothing.

NO CROSS-INDUSTRY FALLBACK, EVER. If an industry has no questions of its own at
a stage, that founder gets the universal ones and nothing else. Another
industry's questions never stand in: a SaaS retention question is not an
Agriculture question because Agriculture is thin. `industry_content_summary`
makes the distinction between "this industry has content here" and "this
industry is not populated yet" visible in logs instead of leaving it to be
inferred from a small pool.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from app.api.v1.diagnosis.founder_context import Applicability, FounderContext
from app.core.logger import logger

#: The marker that makes a question universal. Lower-cased on comparison, so a
#: row carrying "All" behaves the same as one carrying "all".
UNIVERSAL = "all"


def relevance_codes(raw: Any) -> frozenset[str] | None:
    """The industry codes on a row, or None when the row says nothing usable.

    None means "no opinion" and is returned for NULL, a non-list, an empty list
    and a list with nothing readable in it. Every one of those means the same
    thing operationally -- this row was never tagged -- and the caller treats it
    exactly as `["all"]`, because a question nobody restricted is unrestricted.

    Never raises. `industry_relevance` is free-shaped jsonb; a malformed row
    must not be able to end a founder's diagnosis.
    """
    if not isinstance(raw, (list, tuple)):
        return None
    codes = frozenset(
        code.strip().lower()
        for code in raw
        if isinstance(code, str) and code.strip()
    )
    return codes or None


def is_universal(raw: Any) -> bool:
    """True when this row is eligible for every industry."""
    codes = relevance_codes(raw)
    return codes is None or UNIVERSAL in codes


def verdict_for(raw: Any, context: FounderContext) -> Applicability:
    """Can this row be asked to this founder, on industry grounds alone?

        SATISFIED     universal, or tagged with the founder's own industry
        CONTRADICTED  tagged with other industries, and we know this founder's
        UNKNOWN       tagged with other industries, and we do not know theirs

    The UNKNOWN case is the fail-open half and is the common one today.
    """
    if is_universal(raw):
        return Applicability.SATISFIED
    codes = relevance_codes(raw)
    assert codes is not None  # is_universal() already returned for the None case
    # Delegated to FounderContext rather than compared here, so "known industry
    # that is not this one" resolves to CONTRADICTED through the same family
    # logic every other gate uses -- and an unknown industry through the same
    # UNKNOWN. One reading of the founder, not a second one written inline.
    verdicts = {context.verdict(f"industry:{code}") for code in codes}
    if Applicability.SATISFIED in verdicts:
        return Applicability.SATISFIED
    if Applicability.UNKNOWN in verdicts:
        return Applicability.UNKNOWN
    return Applicability.CONTRADICTED


@dataclass(frozen=True)
class IndustryFilterResult:
    """What the industry gate did, in a shape a log line and a test can both read."""

    kept: tuple
    #: (question_id, its industry_relevance) for each removal, so "why was this
    #: question not asked" is answerable without re-running the selection.
    removed: tuple[tuple[int, tuple[str, ...]], ...]
    #: Kept, but only because the founder's industry is unknown. These are the
    #: candidates a later step will mark applicability_uncertain.
    uncertain_ids: frozenset[int]
    industry_code: str | None

    @property
    def removed_ids(self) -> frozenset[int]:
        return frozenset(qid for qid, _codes in self.removed)

    def log_extra(self) -> dict:
        return {
            "stage": "industry_scope",
            "industry": self.industry_code or "unknown",
            "kept": len(self.kept),
            "removed": len(self.removed),
            "uncertain": len(self.uncertain_ids),
        }


def filter_by_industry(
    candidates: Sequence, context: FounderContext, *, question_ids=None
) -> IndustryFilterResult:
    """Drop the questions written for somebody else's industry.

    Pure: no database, no session, no ordering change. The surviving questions
    keep their original order, so this composes in front of the ranking key
    without perturbing it.

    `question_ids` lets a caller supply ids for objects that do not carry one
    (test doubles); production rows always do.
    """
    kept: list = []
    removed: list[tuple[int, tuple[str, ...]]] = []
    uncertain: set[int] = set()

    for index, question in enumerate(candidates):
        raw = getattr(question, "industry_relevance", None)
        qid = (
            question_ids[index] if question_ids is not None
            else getattr(question, "question_id", None)
        )
        verdict = verdict_for(raw, context)
        if verdict is Applicability.CONTRADICTED:
            codes = relevance_codes(raw) or frozenset()
            removed.append((qid, tuple(sorted(codes))))
            continue
        if verdict is Applicability.UNKNOWN and qid is not None:
            uncertain.add(qid)
        kept.append(question)

    result = IndustryFilterResult(
        kept=tuple(kept),
        removed=tuple(removed),
        uncertain_ids=frozenset(uncertain),
        industry_code=context.industry_code,
    )

    if removed:
        # One line per selection, not per question: a 1,478-candidate pool would
        # otherwise write 1,400 log lines per turn. The per-question detail is
        # on the result object for callers that want it (tests, a debug
        # endpoint), and a sample goes into the line so a reader can see the
        # shape of what went.
        logger.info(
            "industry scope removed candidates",
            extra={
                **result.log_extra(),
                "reason": "industry_mismatch",
                "sample": [
                    {"question_id": qid, "question_industry_relevance": list(codes)}
                    for qid, codes in removed[:5]
                ],
            },
        )
    return result


def industry_content_summary(candidates: Iterable, context: FounderContext) -> dict:
    """How much of this pool is this founder's own industry, and how much universal.

    The point is the distinction the architecture requires us not to blur:

        specific > 0   this industry has content at this stage
        specific == 0  this industry is not populated here yet

    Both leave the founder with the universal questions and neither borrows from
    another industry -- but only one of them is a content gap worth a ticket, and
    a small candidate pool alone cannot tell you which you are looking at.
    """
    universal = specific = 0
    code = context.industry_code
    for question in candidates:
        raw = getattr(question, "industry_relevance", None)
        if is_universal(raw):
            universal += 1
        elif code and code in (relevance_codes(raw) or frozenset()):
            specific += 1
    return {
        "industry": code or "unknown",
        "universal_candidates": universal,
        "industry_specific_candidates": specific,
        "industry_content_present": specific > 0,
    }


def validate_industry_metadata(db) -> dict:
    """Data-quality report on `industry_relevance`. Reports; never repairs.

    Five checks, all of them things that would otherwise fail silently:

      * a code on a question that is not in `industries` -- the question is
        unreachable, because no founder can ever match it
      * `["all"]` mixed with specific codes -- ambiguous; `all` wins today, but
        the row's author probably meant one or the other
      * a duplicate code within one array
      * a row whose value is not a usable array at all
      * a question whose industries disagree with its problem's or root cause's

    The last one is reported and NOT reconciled, by explicit architectural
    decision: question-level metadata answers "can we ask this", problem and
    root-cause metadata answer "how relevant is the interpretation". Making one
    override the other would create restrictions nobody wrote.
    """
    from sqlalchemy import text

    catalogue = {
        code.lower()
        for (code,) in db.execute(text("SELECT industry_code FROM industries")).all()
    }

    report: dict[str, list] = {
        "unknown_codes": [], "mixed_all_and_specific": [],
        "duplicate_codes": [], "unreadable": [], "mismatched_with_taxonomy": [],
    }

    rows = db.execute(text(
        "SELECT q.question_id, q.industry_relevance, p.industry_relevance,"
        "       r.industry_relevance"
        "  FROM questions q"
        "  LEFT JOIN problems p ON p.problem_id = q.problem_id"
        "  LEFT JOIN root_causes r ON r.root_cause_id = q.root_cause_id"
    )).all()

    for qid, q_raw, p_raw, r_raw in rows:
        if q_raw is not None and not isinstance(q_raw, (list, tuple)):
            report["unreadable"].append(qid)
            continue
        codes = relevance_codes(q_raw)
        if codes is None:
            continue
        if isinstance(q_raw, (list, tuple)):
            lowered = [c.strip().lower() for c in q_raw if isinstance(c, str) and c.strip()]
            if len(lowered) != len(set(lowered)):
                report["duplicate_codes"].append(qid)
        if UNIVERSAL in codes and len(codes) > 1:
            report["mixed_all_and_specific"].append(qid)
        unknown = sorted(codes - catalogue - {UNIVERSAL})
        if unknown:
            report["unknown_codes"].append({"question_id": qid, "codes": unknown})

        # Reported only. See the docstring.
        specific = codes - {UNIVERSAL}
        for label, other in (("problem", p_raw), ("root_cause", r_raw)):
            other_codes = (relevance_codes(other) or frozenset()) - {UNIVERSAL}
            if specific and other_codes and not (specific & other_codes):
                report["mismatched_with_taxonomy"].append({
                    "question_id": qid, "level": label,
                    "question": sorted(specific), "taxonomy": sorted(other_codes),
                })

    report["checked"] = len(rows)
    report["catalogue_size"] = len(catalogue)
    return report
