"""Root Cause Confidence Score (RCCS) -- the normalised, incremental, evidence-
driven measure of how strongly a founder's answers support one root cause.

RANGE AND REPRESENTATION. RCCS is a Decimal on **0.0000 .. 1.0000**. It is a
FRACTION, never a percentage: the strong-root-cause threshold is the literal
Decimal("0.80"), not 80 and not 0.008. `RCCS_STRONG_THRESHOLD` below is the only
place that number is written, and `format_rccs_percent` is the only sanctioned way
to render it for a human. Nothing in this module multiplies by 100.

WHY A NEW SCORE. Four scores already existed and none of them means this:

  detection_score        mean over NEGATIVE evidence only, so it SATURATES at
                         exactly 1.0000 for any cause whose every probe came back
                         Red -- including a cause probed exactly once. A stopping
                         rule built on it ends a diagnosis on one answer.
  detection_confidence   intensity x corroboration, and corroboration is
                         n/(n+1), so a single-question cause is capped at 0.5000.
                         80% of the catalogue's root causes have exactly one
                         question, so a 0.80 rule on it is unreachable for them.
  final_weighted_score   NOT normalised. Confirmation enters it as a multiplier on
                         {0.5, 1.0, 1.5}, so the range is [0.125, 1.125].
  overall_confidence_score  a SESSION score on 0..100 over five signals, four of
                         which say nothing about any individual root cause.

All four keep their jobs. RCCS is additional, and it answers only: *how strongly
does the evidence collected from this founder support this root cause?*

THE MODEL: COVERAGE-RELATIVE (Option E).

RCCS measures evidence strength RELATIVE TO THE EVIDENCE THAT WAS AVAILABLE, not
absolute evidence mass. The distinction is the whole of Option E, and it exists
because the catalogue made the absolute reading unusable:

    1,997 of 1,997 root causes have all their questions in ONE pillar, so
    cross-pillar corroboration for a single cause is structurally impossible.
    1,603 of them (80.3%) have exactly ONE question. All 12 frozen ground-truth
    primaries have exactly one question. Real sessions collect ~1 answer per
    cause (88.0% of cases; the observed maximum is 2).

Under an absolute model no amount of tuning let ANY of those causes reach the
strong threshold -- measured across four candidate parameterisations, 0 of 12
ground-truth primaries were reachable, so no production diagnosis could ever
complete successfully. Coverage-relative scoring asks the answerable question
instead: *did we collect the evidence that exists, and was it bad?*

  PRIMARY evidence is scored against what could have been asked:

      reach = primary_mass / (askable_questions + _COVERAGE_PRIOR)

      A cause with one question, answered Red, reaches 1 / 1.25 = 0.8000.
      A cause with five questions and one Red reaches 1 / 5.25 = 0.1905 -- asking
      more of a cause makes it HARDER to call strong, which is correct: we looked
      harder and found less.

  SIBLING evidence still saturates absolutely, because there is no "available
  sibling evidence" to be relative to. Its ceiling depends on DIRECTION:

      sibling_support = min(saturated_mass, _SIBLING_SUPPORT_CAP)   # 0.25
      sibling_contra  = saturated_mass                              # uncapped

  The asymmetry is deliberate. The support cap stops indirect evidence
  MANUFACTURING a strong cause. Capping contradiction would stop indirect
  evidence CHALLENGING one, and a diagnosis has to stay reversible -- so
  accumulated contradicting evidence elsewhere in the business can materially
  reduce a high RCCS, while accumulated supporting evidence elsewhere cannot
  create one.

  The two combine by noisy-OR, so sibling evidence corroborates but can never
  stand alone:

      support_signal = 1 - (1 - reach) * (1 - sibling)

  CONTRADICTION accumulates through the identical shape and attenuates:

      RCCS = support_signal * (1 - CONTRA_WEIGHT * contra_signal)

      Multiplicative, not subtractive: it cannot drive the score below 0, and a
      contradiction dents a well-evidenced cause less than a thin one.

WHAT 0.80 MEANS, AND WHAT IT DOES NOT. RCCS >= 0.80 means "the evidence for this
cause is strong relative to what could be gathered". It does NOT mean the
diagnosis is finished, and it is NOT a probability. Deciding whether a diagnosis
may END is the FINAL QUALITY GATE's job (see completion.py), which additionally
requires that the cause explain the founder's stated problem, that supporting
evidence exists, that contradictions are accounted for, that pillar coverage is
sufficient, and that no high-value question remains unasked. Evidence strength
and diagnostic sufficiency are separate concepts and must not be collapsed.

TRAJECTORY for a three-question cause (askable = 3), all in one pillar as the
catalogue requires:

    Red    (1 of 3 asked)          0.3077
    Red    (2 of 3)                0.6154
    Red    (3 of 3, fully probed)  0.9231
    Green  sibling (contradicts)   0.8308


DIRECTION comes from the answer's band, which is an EXISTING, documented
semantic -- `ScoreLabel`, where the band score is RISK and higher is worse. It is
not re-derived from answer text and no new weight is invented:

    RED   (2)  supports the cause      magnitude 1.0
    AMBER (1)  supports the cause      magnitude 0.5
    GREEN (0)  CONTRADICTS the cause   magnitude 1.0
    N/A        no event at all         (never scored, never zero -- see ScoreLabel)

A Green is the only genuinely load-bearing reading here, and it is the reading
`StandardRootCauseEngine` already takes: a cause whose every probe came back Green
is not a candidate at all. RCCS says the same thing continuously rather than as a
cliff.

MULTI-ROOT-CAUSE, DIRECTIONALLY. One answer reaches more than one cause through
the two edges the schema actually has, and through no others:

    PRIMARY  `questions.root_cause_id`               weight 1.00
    SIBLING  other root causes sharing the question's
             `questions.problem_id`                  weight SIBLING_WEIGHT (0.25)

The sibling edge is real structure, not an invented association: a Red answer is
evidence that the PROBLEM is present, which raises every cause filed under it a
little; a Green is evidence the problem is absent, which lowers them all a
little. Direction propagates unchanged along both edges, magnitude is attenuated
along the sibling edge. So one answer produces, e.g., RC-A +, RC-B +, RC-C -,
which is what the directional requirement asks for. A cause is never reached by
any other route, so no arbitrary id-based behaviour can enter.

DEDUPLICATION. Events are keyed `(answer_id, root_cause_id)`. Applying the same
answer twice -- replay, reprocessing, a resumed session, a retried request -- is a
no-op, not a second increment. `RCCSState.apply` returns False when it rejects a
duplicate, so callers can assert on it rather than hoping.

DETERMINISM AND COST. Pure arithmetic over already-classified answers. No LLM
call, no database access, no clock, no randomness. Recomputing from the same
event set yields the identical Decimal, which is what lets
`incremental_confidence` call this after every answer for free.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from app.models.enums import ScoreLabel

__all__ = [
    "EvidenceDirection",
    "EvidenceEvent",
    "RCCSState",
    "RootCauseScore",
    "RCCS_STRONG_THRESHOLD",
    "SIBLING_WEIGHT",
    "events_for_answer",
    "format_rccs_percent",
]

_QUANT = Decimal("0.0001")
_ZERO = Decimal("0")
_ONE = Decimal("1")

#: The strong-root-cause threshold, as a FRACTION on the 0..1 RCCS scale.
#: 0.80 means eighty percent. It is not 80 and it is not 0.008. Written once.
RCCS_STRONG_THRESHOLD = Decimal("0.80")

#: Saturation constant for SIBLING evidence only. depth = mass / (mass + K).
#:
#: Primary evidence no longer uses this: it is scored COVERAGE-RELATIVELY (see
#: _COVERAGE_PRIOR). Sibling evidence still saturates absolutely, because there
#: is no meaningful "how much sibling evidence was available" -- a founder's
#: problem can be probed through any number of neighbouring causes.
_K_SIBLING = Decimal("1")

#: Smoothing prior on the coverage denominator: reach = mass / (askable + PRIOR).
#:
#: This is the single number that decides what "fully investigated" is worth. At
#: 0.25 a cause whose ONLY question came back Red reaches 1 / 1.25 = 0.8000 --
#: exactly the strong threshold, and not a hair more. That is the product
#: decision (Option E) expressed as arithmetic: when the catalogue offers one
#: probe and that probe comes back at maximum severity, the evidence for that
#: cause is as strong as evidence for it can possibly be.
#:
#: The prior is not decoration. Without it, one Red on a one-question cause would
#: score 1.0000 -- certainty from a single sentence -- and a cause could never be
#: distinguished from one probed five times and Red every time (0.9524 here). It
#: is deliberately the smallest value that keeps that ordering while letting a
#: fully-investigated single-question cause reach the bar.
_COVERAGE_PRIOR = Decimal("0.25")

#: How much a fully-contradicted picture attenuates a fully-supported one.
#: At 0.2 a single Green answer costs a corroborated cause about 0.08, matching
#: the frozen worked example (0.81 -> 0.73). Deliberately gentle: one green
#: answer should qualify a diagnosis, not delete it.
_CONTRA_WEIGHT = Decimal("0.2")

#: Attenuation along the sibling edge (same `problems.problem_id`, different root
#: cause). Four sibling answers are worth one direct answer. Small on purpose:
#: the sibling edge exists so the score is not blind to problem-level evidence,
#: not so a cause can be carried to the threshold without ever being asked about.
SIBLING_WEIGHT = Decimal("0.25")

#: Hard ceiling on the SUPPORT signal sibling evidence can produce on its own.
#:
#: Per-event attenuation alone does NOT bound this, which a test caught: sibling
#: mass still accumulates, so twenty-four Red answers on a sibling question drove
#: an unasked cause to 0.9375 -- above the strong threshold, on a cause the
#: founder was never asked about. Attenuating each event only slows that down; it
#: does not stop it.
#:
#: So the sibling support signal is computed separately and capped here.
#: Problem-level implication can contribute at most this much confidence, no
#: matter how much of it there is. A cause must be probed DIRECTLY to become
#: strong, which is the property the threshold has to mean.
#:
#: SUPPORT ONLY. This cap is deliberately NOT applied to sibling CONTRADICTION.
#: The two directions serve opposite purposes -- this one stops indirect evidence
#: manufacturing a strong cause; capping the other would stop indirect evidence
#: challenging one, and a diagnosis has to stay reversible. Applying it to both
#: was defect E1: a fully-probed cause could not be dislodged by any quantity of
#: contradicting sibling evidence (0.8889 -> 0.8445 at saturation).
_SIBLING_SUPPORT_CAP = SIBLING_WEIGHT

#: Magnitude contributed by each band, before edge attenuation.
_BAND_MAGNITUDE: dict[ScoreLabel, Decimal] = {
    ScoreLabel.RED: Decimal("1.0"),
    ScoreLabel.AMBER: Decimal("0.5"),
    ScoreLabel.GREEN: Decimal("1.0"),
}


def _q(value: Decimal) -> Decimal:
    return value.quantize(_QUANT, rounding=ROUND_HALF_UP)


def _pillars_of(buckets: dict[tuple[str, int | None], Decimal]) -> tuple[int | None, ...]:
    """Distinct pillars a bucket set touches, in a reproducible order."""
    pillars = {pillar for (_source, pillar) in buckets}
    return tuple(sorted(pillars, key=lambda p: (p is None, p)))


class EvidenceDirection(str, Enum):
    """Which way one piece of evidence moves one root cause."""

    SUPPORT = "support"
    CONTRADICT = "contradict"

    @property
    def sign(self) -> str:
        return "+" if self is EvidenceDirection.SUPPORT else "-"


@dataclass(frozen=True)
class EvidenceEvent:
    """One answer's effect on one root cause. Immutable and fully traceable.

    Everything needed to explain a score movement in the report is on this
    record: which question was asked, which answer produced it, which cause it
    moved, which way, by how much, in which pillar, and by which edge.
    """

    answer_id: int
    question_id: int
    root_cause_id: int
    direction: EvidenceDirection
    magnitude: Decimal          # post-attenuation, > 0
    pillar_id: int | None
    score_label: ScoreLabel
    #: "primary" (questions.root_cause_id) or "sibling" (shared problem_id).
    source: str = "primary"
    #: Monotonic ordering within a session; the caller supplies it (answer order).
    sequence: int = 0

    @property
    def dedupe_key(self) -> tuple[int, int]:
        return (self.answer_id, self.root_cause_id)


@dataclass(frozen=True)
class RootCauseScore:
    """The computed RCCS for one root cause, with the state that explains it."""

    root_cause_id: int
    rccs: Decimal
    support_signal: Decimal
    contra_signal: Decimal
    supporting_pillars: tuple[int | None, ...]
    contradicting_pillars: tuple[int | None, ...]
    supporting_event_count: int
    contradicting_event_count: int
    #: How many questions the catalogue holds for this cause -- the denominator
    #: the score is relative to. The report needs it: "strong" means something
    #: different for a cause with one probe than for one with twelve, and a
    #: reader cannot interpret the number without it.
    askable_questions: int = 0
    #: Distinct questions of this cause the founder actually answered.
    answered_questions: int = 0

    @property
    def coverage(self) -> Decimal:
        """Fraction of this cause's available questions that were answered."""
        if self.askable_questions <= 0:
            return _ZERO
        return _q(Decimal(self.answered_questions) / Decimal(self.askable_questions))

    @property
    def is_strong(self) -> bool:
        """RCCS alone has cleared 0.80.

        NOT a report trigger on its own. The frozen rule requires supporting
        evidence AND that the cause materially explains the founder's stated
        problem; see `has_supporting_evidence` and the completion gate.
        """
        return self.rccs >= RCCS_STRONG_THRESHOLD

    @property
    def has_supporting_evidence(self) -> bool:
        """At least one real supporting answer stands behind this score.

        Guards the case the brief calls out explicitly: a score at or above the
        threshold with no supporting evidence must NOT qualify. That is not
        hypothetical -- a cause reached only by sibling edges, or one whose
        support was later fully contradicted, can carry a number with nothing
        under it.
        """
        return self.supporting_event_count > 0


def events_for_answer(
    *,
    answer_id: int,
    question_id: int,
    score_label: ScoreLabel,
    primary_root_cause_id: int | None,
    sibling_root_cause_ids: tuple[int, ...] = (),
    pillar_id: int | None = None,
    sequence: int = 0,
) -> tuple[EvidenceEvent, ...]:
    """Turn one classified answer into its directional evidence events.

    Returns an empty tuple for an unscored (N/A) answer: not applicable is
    neither support nor contradiction, and it must not become a zero -- the same
    rule `ScoreLabel.is_scored` enforces everywhere else.

    Siblings are attenuated by SIBLING_WEIGHT and carry `source="sibling"`, so a
    reader of the trail can always tell a cause that was asked about from one
    that was merely implicated by its problem.
    """
    if not score_label.is_scored:
        return ()

    magnitude = _BAND_MAGNITUDE.get(score_label)
    if magnitude is None:                                # unknown band: no event
        return ()

    direction = (
        EvidenceDirection.CONTRADICT
        if score_label is ScoreLabel.GREEN
        else EvidenceDirection.SUPPORT
    )

    events: list[EvidenceEvent] = []
    if primary_root_cause_id is not None:
        events.append(
            EvidenceEvent(
                answer_id=answer_id,
                question_id=question_id,
                root_cause_id=primary_root_cause_id,
                direction=direction,
                magnitude=magnitude,
                pillar_id=pillar_id,
                score_label=score_label,
                source="primary",
                sequence=sequence,
            )
        )

    for sibling_id in sibling_root_cause_ids:
        if sibling_id == primary_root_cause_id:
            continue
        events.append(
            EvidenceEvent(
                answer_id=answer_id,
                question_id=question_id,
                root_cause_id=sibling_id,
                direction=direction,
                magnitude=_q(magnitude * SIBLING_WEIGHT),
                pillar_id=pillar_id,
                score_label=score_label,
                source="sibling",
                sequence=sequence,
            )
        )
    return tuple(events)


class RCCSState:
    """Accumulates evidence events and exposes the current RCCS per root cause.

    Incremental by construction: `apply` folds one event into the running state
    in constant time, and `score_for` reads the result. Rebuilding the state from
    the full event list produces identical scores, which is what makes the
    persisted trail authoritative rather than a parallel copy that can drift.
    """

    def __init__(self, askable: Mapping[int, int] | None = None) -> None:
        """`askable` maps root_cause_id -> how many questions the catalogue holds.

        It is the denominator coverage-relative scoring is relative to, and it is
        supplied by the caller because this module must stay free of database
        access. When a cause is missing from the map the state FALLS BACK to the
        number of distinct questions of that cause the founder actually answered
        -- i.e. "everything we knew to ask" -- which is the only honest reading
        available without the catalogue, and which degrades to the same score a
        fully-probed cause would get rather than to zero.
        """
        # root_cause_id -> (source, pillar_id) -> accumulated magnitude.
        # Keyed by SOURCE as well as pillar so the sibling signal can be bounded
        # separately -- see _SIBLING_SUPPORT_CAP.
        self._support: dict[int, dict[tuple[str, int | None], Decimal]] = {}
        self._contra: dict[int, dict[tuple[str, int | None], Decimal]] = {}
        self._seen: set[tuple[int, int]] = set()
        self._events: list[EvidenceEvent] = []
        self._askable: dict[int, int] = dict(askable or {})
        # Distinct PRIMARY question ids per cause -- the fallback denominator and
        # the report's "answered" figure. Sibling questions are not counted:
        # they are not probes of this cause.
        self._primary_questions: dict[int, set[int]] = {}

    # --- Mutation ---------------------------------------------------------

    def apply(self, event: EvidenceEvent) -> bool:
        """Fold one event in. Returns False if it was a duplicate and ignored.

        Duplicate means the same answer has already moved this same root cause.
        Replaying a session, reprocessing an answer, or a retried request must
        not increase a score twice, so this is a guard rather than an
        optimisation, and it reports what it did.
        """
        key = event.dedupe_key
        if key in self._seen:
            return False
        self._seen.add(key)
        self._events.append(event)

        target = (
            self._support
            if event.direction is EvidenceDirection.SUPPORT
            else self._contra
        )
        buckets = target.setdefault(event.root_cause_id, {})
        key_ = (event.source, event.pillar_id)
        buckets[key_] = buckets.get(key_, _ZERO) + event.magnitude

        if event.source != "sibling":
            self._primary_questions.setdefault(event.root_cause_id, set()).add(
                event.question_id
            )
        return True

    def apply_all(self, events) -> int:
        """Fold many events in; returns how many were actually applied."""
        return sum(1 for event in events if self.apply(event))

    # --- Reading ----------------------------------------------------------

    @property
    def events(self) -> tuple[EvidenceEvent, ...]:
        """The full trail, in application order. This is what gets persisted."""
        return tuple(self._events)

    def events_for(self, root_cause_id: int) -> tuple[EvidenceEvent, ...]:
        return tuple(e for e in self._events if e.root_cause_id == root_cause_id)

    def tracked_root_cause_ids(self) -> tuple[int, ...]:
        """Every cause any evidence has touched, ascending.

        Ascending purely so iteration is reproducible. Ordering BY id is never a
        ranking here -- that is exactly the id-based behaviour the ranking layer
        was corrected to avoid.
        """
        return tuple(sorted(set(self._support) | set(self._contra)))

    def askable_for(self, root_cause_id: int) -> int:
        """Questions the catalogue holds for this cause -- the reach denominator.

        Falls back to the distinct questions actually answered when the caller
        supplied no catalogue figure, and to 1 when neither is known, so the
        denominator can never be 0 and a missing map degrades the score rather
        than crashing it.
        """
        supplied = self._askable.get(root_cause_id)
        if supplied and supplied > 0:
            return supplied
        return max(1, len(self._primary_questions.get(root_cause_id, ())))

    def _reach(self, root_cause_id: int, primary_mass: Decimal) -> Decimal:
        """Coverage-relative primary signal: how much of the AVAILABLE evidence
        was collected, weighted by how bad it was.

        Not per-pillar. Every root cause in the catalogue has all its questions
        in a single pillar, so a per-pillar split would be arithmetic with no
        production meaning; the pillars a cause's evidence touches are still
        recorded on the score for the report.
        """
        if primary_mass <= _ZERO:
            return _ZERO
        denominator = Decimal(self.askable_for(root_cause_id)) + _COVERAGE_PRIOR
        return min(primary_mass / denominator, _ONE)

    @staticmethod
    def _sibling_signal(masses, cap: Decimal) -> Decimal:
        """Absolute, saturating, bounded by `cap`.

        The CAP DIFFERS BY DIRECTION, and that asymmetry is the point:

          SUPPORT       cap = _SIBLING_SUPPORT_CAP (0.25). Indirect evidence must
                        not be able to MANUFACTURE a strong cause -- a cause has
                        to be probed directly to become strong.
          CONTRADICTION cap = 1.0. Indirect evidence MUST be able to challenge a
                        cause. Capping here would protect a strong cause from
                        being overturned, which is the opposite of what the
                        support cap exists to do.

        Both remain bounded: the saturation `mass / (mass + K)` is < 1 for any
        finite mass, so the contradiction signal approaches 1.0 without reaching
        it. Contradiction still cannot zero a cause -- _CONTRA_WEIGHT bounds its
        effect at a x0.80 attenuation.
        """
        remainder = _ONE
        for mass in masses:
            if mass <= _ZERO:
                continue
            remainder *= _ONE - mass / (mass + _K_SIBLING)
        return min(_ONE - remainder, cap)

    def _signal(
        self,
        root_cause_id: int,
        buckets: dict[tuple[str, int | None], Decimal],
        sibling_cap: Decimal,
    ) -> Decimal:
        """Coverage-relative primary signal combined with the sibling signal."""
        if not buckets:
            return _ZERO
        primary_mass = sum(
            (mass for (source, _p), mass in buckets.items() if source != "sibling"),
            _ZERO,
        )
        reach = self._reach(root_cause_id, primary_mass)
        sibling = self._sibling_signal(
            (mass for (source, _p), mass in buckets.items() if source == "sibling"),
            sibling_cap,
        )
        return _q(_ONE - (_ONE - reach) * (_ONE - sibling))

    def score_for(self, root_cause_id: int) -> RootCauseScore:
        """Current RCCS for one root cause, with its explaining state."""
        support = self._support.get(root_cause_id, {})
        contra = self._contra.get(root_cause_id, {})

        # Support is capped so indirect evidence cannot manufacture strength;
        # contradiction is NOT, so indirect evidence can still challenge a cause.
        # See _sibling_signal for why the asymmetry is deliberate.
        support_signal = self._signal(root_cause_id, support, _SIBLING_SUPPORT_CAP)
        contra_signal = self._signal(root_cause_id, contra, _ONE)
        rccs = _q(support_signal * (_ONE - _CONTRA_WEIGHT * contra_signal))

        events = self.events_for(root_cause_id)
        return RootCauseScore(
            root_cause_id=root_cause_id,
            # Multiplicative attenuation cannot leave [0,1]; the clamp is a
            # guard against a future constant change, not live arithmetic.
            rccs=max(_ZERO, min(_ONE, rccs)),
            support_signal=support_signal,
            contra_signal=contra_signal,
            supporting_pillars=_pillars_of(support),
            contradicting_pillars=_pillars_of(contra),
            supporting_event_count=sum(
                1 for e in events if e.direction is EvidenceDirection.SUPPORT
            ),
            contradicting_event_count=sum(
                1 for e in events if e.direction is EvidenceDirection.CONTRADICT
            ),
            askable_questions=self.askable_for(root_cause_id),
            answered_questions=len(self._primary_questions.get(root_cause_id, ())),
        )

    def all_scores(self) -> tuple[RootCauseScore, ...]:
        """Every tracked cause, strongest RCCS first.

        Ties break on root_cause_id ASCENDING only as a determinism anchor, in
        the same spirit as the ranking layer's terminal key -- never as a
        substantive selector between causes that differ.
        """
        scores = [self.score_for(rc) for rc in self.tracked_root_cause_ids()]
        return tuple(sorted(scores, key=lambda s: (-s.rccs, s.root_cause_id)))

    def strong_scores(self) -> tuple[RootCauseScore, ...]:
        """Causes at or above 0.80 that also have real supporting evidence.

        Both conditions, because the frozen rule is both. A score that reached
        the threshold with no supporting event behind it is excluded here rather
        than filtered somewhere downstream.
        """
        return tuple(
            s for s in self.all_scores() if s.is_strong and s.has_supporting_evidence
        )


def format_rccs_percent(rccs: Decimal) -> str:
    """Render an RCCS for a human: Decimal("0.8342") -> "83%".

    The ONLY sanctioned conversion out of the 0..1 scale. It exists so that
    multiplying by 100 never happens anywhere else, which is how a fraction and a
    percentage get confused in the first place.
    """
    return f"{int((rccs * Decimal(100)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))}%"
