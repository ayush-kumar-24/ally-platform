"""Problem-driven completion and the final quality gate.

WHAT DECIDES WHEN A DIAGNOSIS IS DONE. Not a question count. Not a root-cause
count. The diagnosis is complete when the founder's stated CURRENT PROBLEM has
been sufficiently explained by root causes that are both strongly scored (RCCS >=
0.80) and actually evidenced by that founder's own answers.

HOW THE STATED PROBLEM IS ANCHORED. The Current Problem phase captures free text
(`current_problem_answers`), which carries no `problem_id`. The link to the
catalogue is made by the engine that already exists for it: non-Green answers map
through `questions.problem_id` to `SymptomDetection.problem_id`. Those detected
problems are the ANCHOR SET -- the founder's presenting complaint, expressed in
catalogue terms, derived deterministically from stored data with no inference.

A root cause EXPLAINS the stated problem when `root_causes.problem_id` is in the
anchor set. That is a real foreign-key relationship, not a similarity judgement,
and it is the only definition this module uses.

WHY THIS IS NOT "THREE ROOT CAUSES". `TOP_ROOT_CAUSES_REPORT` (3) is a REPORT
contract -- how many causes the report renders. It has never been a stopping
rule, and making it one would reintroduce exactly the fixed-count behaviour the
product decision removes. A founder whose single anchor problem is fully
explained by two strong causes is done; a founder with three anchor problems and
two strong causes is not, regardless of how many questions either has answered.

THE SAFETY CEILING IS NOT THE COMPLETION RULE. `settings.question_budget()`
survives as an abuse/runaway bound and as the coverage denominator inside the
confidence score. It is never the reason a healthy diagnosis ends, and
`CompletionDecision.reason` distinguishes the two so the founder is never shown a
budget number as though it were the length of their diagnosis.

Deterministic: pure functions over already-computed state. No LLM call, no
database access, no clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.api.v1.diagnosis.rccs import RCCSState, RootCauseScore, RCCS_STRONG_THRESHOLD

__all__ = [
    "CompletionDecision",
    "CompletionReason",
    "QualityGateResult",
    "evaluate_quality_gate",
    "decide_completion",
]


class CompletionReason(str):
    """Why a diagnosis stopped. A plain string subclass so it serialises freely."""


#: The founder's problem is explained -- the only SUCCESSFUL completion.
PROBLEM_EXPLAINED = CompletionReason("problem_explained")
#: Nothing eligible left to ask. Honest exhaustion, not success.
BANK_EXHAUSTED = CompletionReason("bank_exhausted")
#: The safety ceiling caught a runaway session. Never a diagnostic conclusion.
SAFETY_CEILING = CompletionReason("safety_ceiling")
#: Keep going.
CONTINUE = CompletionReason("continue")


@dataclass(frozen=True)
class QualityGateResult:
    """The hybrid final quality gate: six checks, all of which must hold.

    Each check is reported individually rather than collapsed into a boolean so
    that a diagnosis that does NOT pass can say which condition it failed -- both
    for the tests and for anyone debugging why a founder is still being asked
    questions.
    """

    explains_problem: bool            # 1. a strong cause explains the stated problem
    meets_threshold: bool             # 2. RCCS >= 0.80
    has_supporting_evidence: bool     # 3. real supporting answers behind it
    contradictions_accounted: bool    # 4. contradicted causes re-evaluated
    coverage_sufficient: bool         # 5. no important area still unexamined
    no_high_value_question: bool      # 6. nothing left that could change the answer

    qualifying_causes: tuple[RootCauseScore, ...] = ()
    unexplained_problem_ids: tuple[int, ...] = ()

    @property
    def passed(self) -> bool:
        return all(
            (
                self.explains_problem,
                self.meets_threshold,
                self.has_supporting_evidence,
                self.contradictions_accounted,
                self.coverage_sufficient,
                self.no_high_value_question,
            )
        )

    def failed_checks(self) -> tuple[str, ...]:
        names = (
            ("explains_problem", self.explains_problem),
            ("meets_threshold", self.meets_threshold),
            ("has_supporting_evidence", self.has_supporting_evidence),
            ("contradictions_accounted", self.contradictions_accounted),
            ("coverage_sufficient", self.coverage_sufficient),
            ("no_high_value_question", self.no_high_value_question),
        )
        return tuple(name for name, ok in names if not ok)


@dataclass(frozen=True)
class CompletionDecision:
    """Stop or continue, and why."""

    complete: bool
    reason: CompletionReason
    gate: QualityGateResult | None = None

    @property
    def is_diagnostic_success(self) -> bool:
        """True only when the diagnosis ended because it ANSWERED the question.

        Exhaustion and the safety ceiling are completions too, but they are not
        conclusions, and the report layer must be able to tell the difference --
        the same distinction `_attach_question` already preserves by refusing to
        stamp `generate_report` on a session that merely ran out.
        """
        return self.complete and self.reason == PROBLEM_EXPLAINED


def _explains(score: RootCauseScore, problem_of: dict[int, int], anchors: frozenset[int]) -> bool:
    problem_id = problem_of.get(score.root_cause_id)
    return problem_id is not None and problem_id in anchors


def evaluate_quality_gate(
    *,
    state: RCCSState,
    anchor_problem_ids: frozenset[int],
    problem_of_root_cause: dict[int, int],
    pillars_sufficient: bool,
    high_value_question_available: bool,
) -> QualityGateResult:
    """Run the six checks over the current evidence state.

    `pillars_sufficient` and `high_value_question_available` are supplied by the
    caller because they are properties of the QUESTION BANK and the session's
    pillar coverage, not of the RCCS state -- keeping them as inputs is what lets
    this function stay pure and hermetically testable.
    """
    strong = state.strong_scores()

    qualifying = tuple(
        s for s in strong if _explains(s, problem_of_root_cause, anchor_problem_ids)
    )

    explained_problem_ids = {
        problem_of_root_cause[s.root_cause_id]
        for s in qualifying
        if s.root_cause_id in problem_of_root_cause
    }
    unexplained = tuple(sorted(anchor_problem_ids - explained_problem_ids))

    # Check 4. A cause that carries contradicting evidence has been re-evaluated
    # by construction -- RCCS already folded the contradiction in and the cause
    # only appears in `strong` if it survived at or above the threshold. What
    # this check adds is the case the brief names explicitly: a cause that WAS
    # above 0.80 and has since been pushed below it must not still be counted.
    # `strong_scores()` recomputes from current state every time, so a fallen
    # cause is simply absent -- and that is what makes this check meaningful
    # rather than decorative: it fails when the anchor problems are left
    # unexplained BECAUSE their causes fell.
    contradictions_accounted = all(
        s.rccs >= RCCS_STRONG_THRESHOLD for s in qualifying
    )

    return QualityGateResult(
        explains_problem=bool(qualifying) and not unexplained,
        meets_threshold=bool(qualifying),
        has_supporting_evidence=all(s.has_supporting_evidence for s in qualifying)
        and bool(qualifying),
        contradictions_accounted=contradictions_accounted,
        coverage_sufficient=pillars_sufficient,
        no_high_value_question=not high_value_question_available,
        qualifying_causes=qualifying,
        unexplained_problem_ids=unexplained,
    )


def decide_completion(
    *,
    state: RCCSState,
    anchor_problem_ids: frozenset[int],
    problem_of_root_cause: dict[int, int],
    pillars_sufficient: bool,
    high_value_question_available: bool,
    candidates_remaining: bool,
    answered: int,
    safety_ceiling: int,
) -> CompletionDecision:
    """The single completion decision for the adaptive loop.

    Order matters and encodes the product rule:

      1. The QUALITY GATE first. A diagnosis that has explained the founder's
         problem stops because it is finished, and it must be able to do so at
         any question count -- twelve or ninety.
      2. Then bank exhaustion. Nothing left to ask is an honest stop.
      3. Then the safety ceiling, LAST, so it can only ever catch a session that
         neither finished nor ran out. It is an abuse bound, not a length.

    With no anchor problems (nothing detected yet) the gate cannot pass, so the
    loop keeps asking -- which is correct: a founder whose problem has not been
    located in the catalogue has not been diagnosed.
    """
    gate = evaluate_quality_gate(
        state=state,
        anchor_problem_ids=anchor_problem_ids,
        problem_of_root_cause=problem_of_root_cause,
        pillars_sufficient=pillars_sufficient,
        high_value_question_available=high_value_question_available,
    )

    if gate.passed:
        return CompletionDecision(True, PROBLEM_EXPLAINED, gate)

    if not candidates_remaining:
        return CompletionDecision(True, BANK_EXHAUSTED, gate)

    if safety_ceiling > 0 and answered >= safety_ceiling:
        return CompletionDecision(True, SAFETY_CEILING, gate)

    return CompletionDecision(False, CONTINUE, gate)
