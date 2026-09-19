"""Tag preconditions: can this question legitimately be asked of this founder?

THE FIFTH AXIS, and the last one that removes questions:

    stage_scope     "is this founder far enough along to have an answer?"
    context_scope   "is this subject part of their situation at all?"  (fundraising)
    industry_scope  "is this question written for the kind of business they run?"
    applicability   "does this question presuppose something they have told us
                     is NOT true?"

WHERE THE DATA LIVES. `question_tags.precondition_token`, joined to questions
through `question_tag_mapping`. A precondition is CONTENT -- an editorial
judgement about the bank -- so adding one is a data change and needs no release,
exactly like `questions.industry_relevance`. 91 of 3,460 questions carry one
today (the three `hr-*` tags -> `has_team`); every other question is
unconditional and passes untouched.

THREE-VALUED, AND THE MIDDLE VALUE IS THE POINT.

    founder stated team_size='solo'   -> has_team CONTRADICTED -> remove
    founder stated team_size='6_10'   -> has_team SATISFIED    -> keep
    founder never told us team_size   -> has_team UNKNOWN      -> KEEP, and mark
                                                                  uncertain

UNKNOWN NEVER MEANS NO. A founder who skipped a field is not a founder who
answered it negatively. Collapsing the two would silently under-diagnose exactly
the people whose onboarding is least complete -- and on this axis that is most
of them. The whole resolution lives in `FounderContext.verdict`; this module
only decides which tokens a question carries and what to do with the verdicts.

MULTIPLE TOKENS ARE CONJUNCTIVE, BUT CONTRADICTION WINS OUTRIGHT. A question
tagged both `hr-process` and some future `has_revenue` tag must satisfy both to
be certain, and ONE contradiction removes it -- an HR question is unaskable to a
solo founder whether or not they have revenue. Unknowns downgrade to uncertain;
they never remove.

WHAT THIS DELIBERATELY DOES NOT GATE. "Solo" is not "no founder dependency". A
solo founder is the founder MOST likely to have delegation-readiness, workload,
bottleneck and role-evolution problems, so none of `delegation`, `hiring`,
`team-communication`, `sales-founder-bottleneck` or `pitch` carries a
precondition. The gate stops Ally asking about a team that does not exist; it
never stops Ally asking about the founder. See the migration
b7c2d94e5f10 for every tag that was read and rejected, with the disqualifying
question text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from app.api.v1.diagnosis.founder_context import Applicability, FounderContext
from app.core.logger import logger

#: What a question with no precondition tokens resolves to. Stated as a constant
#: because it is a decision, not an accident: an untagged question is
#: unconditional, and 3,369 of 3,460 rely on it.
UNCONDITIONAL = Applicability.SATISFIED


def verdict_for_tokens(
    tokens: Iterable[str] | None, context: FounderContext
) -> Applicability:
    """Resolve a question's preconditions to one three-valued answer.

        any CONTRADICTED   -> CONTRADICTED   (remove; one is enough)
        else any UNKNOWN   -> UNKNOWN        (keep, mark uncertain)
        else               -> SATISFIED

    Contradiction is checked across ALL tokens before unknown is considered, so
    the order tokens arrive in cannot change the answer.
    """
    if not tokens:
        return UNCONDITIONAL
    verdicts = [context.verdict(token) for token in tokens if token]
    if not verdicts:
        return UNCONDITIONAL
    if Applicability.CONTRADICTED in verdicts:
        return Applicability.CONTRADICTED
    if Applicability.UNKNOWN in verdicts:
        return Applicability.UNKNOWN
    return Applicability.SATISFIED


@dataclass(frozen=True)
class ApplicabilityResult:
    """What the applicability gate did, in a shape a log line and a test read."""

    kept: tuple
    #: (question_id, the tokens that could not be satisfied) per removal, so
    #: "why was this not asked" is answerable without re-running selection.
    removed: tuple[tuple[int, tuple[str, ...]], ...]
    #: Kept, but only because a precondition's family has no data. These are the
    #: candidates the advisor is told are an uncertain fit.
    uncertain_ids: frozenset[int]

    @property
    def removed_ids(self) -> frozenset[int]:
        return frozenset(qid for qid, _tokens in self.removed)

    def log_extra(self) -> dict:
        return {
            "stage": "applicability",
            "kept": len(self.kept),
            "removed": len(self.removed),
            "uncertain": len(self.uncertain_ids),
        }


def filter_by_applicability(
    candidates: Sequence,
    context: FounderContext,
    preconditions: Mapping[int, frozenset[str]] | None,
) -> ApplicabilityResult:
    """Drop the questions this founder has told us do not apply.

    Pure: no database, no ordering change. `preconditions` maps question_id to
    its tokens and is supplied by the caller, because loading it is one query
    for the whole pool rather than one per question.

    An EMPTY OR MISSING map means nothing is gated -- that is the state of any
    database that has not run b7c2d94e5f10, and degrading to "ask everything" is
    the same fail-open every other optional map in this package uses.
    """
    if not preconditions:
        return ApplicabilityResult(tuple(candidates), (), frozenset())

    kept: list = []
    removed: list[tuple[int, tuple[str, ...]]] = []
    uncertain: set[int] = set()

    for question in candidates:
        qid = getattr(question, "question_id", None)
        tokens = preconditions.get(qid) if qid is not None else None
        verdict = verdict_for_tokens(tokens, context)
        if verdict is Applicability.CONTRADICTED:
            unmet = tuple(sorted(
                t for t in (tokens or ())
                if context.verdict(t) is Applicability.CONTRADICTED
            ))
            removed.append((qid, unmet))
            continue
        if verdict is Applicability.UNKNOWN and qid is not None:
            uncertain.add(qid)
        kept.append(question)

    result = ApplicabilityResult(tuple(kept), tuple(removed), frozenset(uncertain))
    if removed:
        # One line per selection, not per question: the pool is four figures.
        logger.info(
            "applicability removed candidates",
            extra={
                **result.log_extra(),
                "reason": "precondition_contradicted",
                "sample": [
                    {"question_id": qid, "unmet": list(unmet)}
                    for qid, unmet in removed[:5]
                ],
            },
        )
    return result


# --- the relaxation ladder --------------------------------------------------
#
# The pool floor exists because a filtered pool of two makes ADAPTIVE_SHORTLIST_
# SIZE a lie: the advisor is handed "the top 5" and gets three. Relaxation buys
# the shortlist back, but only by giving up SOFT restrictions, and it says so.

#: In the order they are given up. Each rung names a filter whose result is
#: discarded, most-expendable first. A rung is only tried when the rungs before
#: it did not reach the floor, and the ladder STOPS at hard contradictions --
#: there is no rung that restores a question the founder's own data rules out.
#: ONE RUNG, and the shortness of this tuple is the design.
#:
#: Industry is the only axis whose removals are "this question was written for a
#: different kind of business". The founder can still answer it; it is merely
#: aimed slightly wide. `industry_scope` already fails open on an unknown
#: industry and on a would-empty pool, so relaxing it under the floor is the
#: same judgement it already makes, applied one step earlier.
#:
#: STAGE SCOPE WAS CONSIDERED AND REJECTED. Category, pillar and dimension rungs
#: were implemented first and removed, because a stage removal means "this
#: founder is not far enough along to have an answer" -- and a question someone
#: cannot answer is not a degraded question, it is a wasted turn that reads as
#: Ally not listening. `tests/test_diagnosis_stage_scope.py::
#: test_ideation_never_sees_revenue_or_team_questions` states the invariant as
#: "never", with no "unless the pool is short" clause, and it caught exactly
#: that regression: a six-question bank relaxed all the way back to revenue and
#: team questions for an ideation founder. A short shortlist is the honest
#: outcome; four questions left is four questions left.
#:
#: `_in_scope` still ACCEPTS the category/pillar/dimension relax keys, so the
#: ordering knowledge is preserved and testable, but nothing in the ladder emits
#: them. Widening this tuple is a product decision, not a tuning knob.
RELAXATION_LADDER = (
    "industry_scope",
)

#: Never relaxed, at any rung, for any pool size.
#:
#:   applicability  asking a solo founder to describe their managers' hiring bar
#:                  is not a degraded question, it is an incoherent one -- the
#:                  exact failure this step exists to stop.
#:   context_scope  its removals are contradictions too: a founder who answered
#:                  the challenges question and did not tick Fundraising has
#:                  denied fundraising intent, and relaxing that re-admits the
#:                  FND-005 investor questions the gate exists to withhold.
#:   stage_scope    see RELAXATION_LADDER.
NEVER_RELAXED = ("applicability", "context_scope", "stage_scope")


@dataclass(frozen=True)
class RelaxationOutcome:
    """The pool after relaxation, and an honest record of what it cost."""

    candidates: tuple
    #: Rungs actually given up, in order. Empty when the strict pool sufficed.
    relaxed: tuple[str, ...]
    #: True when even the full ladder could not reach the floor. Not an error:
    #: a Stage 0 founder 40 answers deep legitimately has four questions left.
    floor_unreached: bool

    def log_extra(self) -> dict:
        return {
            "stage": "pool_floor",
            "candidates": len(self.candidates),
            "relaxed": list(self.relaxed),
            "floor_unreached": self.floor_unreached,
        }


def relax_to_floor(
    strict: Sequence,
    rungs: Sequence[tuple[str, Sequence]],
    floor: int,
) -> RelaxationOutcome:
    """Climb the ladder until the pool reaches `floor`, and record every rung.

    `rungs` is (name, the pool that results from ALSO giving up this rung),
    supplied by the caller in ladder order and already filtered by everything
    that is never relaxed. This function owns the stopping rule, not the
    filtering -- which is what keeps "we never relax applicability" a property
    of the caller's inputs rather than a promise made in prose here.

    Stops at the FIRST rung that reaches the floor; it does not keep climbing
    for a bigger pool. Giving up more than the shortlist needs is not free --
    every relaxed rung is a question asked slightly out of scope.
    """
    if len(strict) >= floor:
        return RelaxationOutcome(tuple(strict), (), False)

    given_up: list[str] = []
    best = tuple(strict)
    for name, pool in rungs:
        given_up.append(name)
        # A rung can only ever ADD candidates back; if it somehow returns fewer
        # (a caller bug), keep the larger pool rather than shrinking on relax.
        if len(pool) > len(best):
            best = tuple(pool)
        if len(best) >= floor:
            outcome = RelaxationOutcome(best, tuple(given_up), False)
            logger.info("pool floor reached by relaxing scope", extra=outcome.log_extra())
            return outcome

    outcome = RelaxationOutcome(best, tuple(given_up), True)
    logger.info(
        "pool floor unreachable; asking what is left rather than relaxing "
        "applicability",
        extra={**outcome.log_extra(), "never_relaxed": list(NEVER_RELAXED)},
    )
    return outcome
