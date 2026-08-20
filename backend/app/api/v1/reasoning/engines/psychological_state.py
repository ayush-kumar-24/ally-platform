"""Psychological State (Distress) Engine -- named session-level distress engine.

Turns detected psychological-state signal occurrences into a cumulative session
distress score, using the seeded Doc-10 tables:

  * `psychological_state_signals` -- the 20 acute signals, each with a
    `score_per_instance` (the scoring table this engine reads).
  * `session_state_bands` -- maps the cumulative score to a session state +
    `reliability_factor` (read by the confidence model via
    `ReasoningRepository.get_reliability_factor`).

The cumulative score this engine produces is written to
`sessions.session_distress_score`, which is exactly what the Confidence model
already consumes for the reliability modifier and the High-Distress override
(>= SESSION_STATE_HIGH_DISTRESS_THRESHOLD). Before this engine, that column was
never computed and stayed 0, so reliability was always 1.0 and the score-based
High-Distress path could never fire.

Deterministic and DB-driven -- no hardcoded weights. Detecting the 20 *linguistic*
signals in free-text answers is an LLM concern (the seam): `assess` accepts an
already-detected occurrence map from that layer. Until the LLM detector lands,
`assess_from_diagnosis` derives a conservative occurrence count from the
distress-tagged Red answers the deterministic diagnosis already produces, so the
score is real (non-zero when there is distress evidence) rather than a constant 0.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from app.api.v1.reasoning.repository import ReasoningRepository
from app.api.v1.reasoning.schemas import AnswerClassification
from app.models.diagnosis import Question
from app.models.enums import ScoreLabel

_ZERO = Decimal("0")


class PsychologicalStateSignalScorer:
    """Implements the `DistressSignalScorer` protocol: the cumulative session
    distress score is the sum, over detected signals, of that signal's
    `score_per_instance` times its occurrence count. Weights come from
    `psychological_state_signals`; nothing is hardcoded."""

    def __init__(self, repository: ReasoningRepository):
        self.repository = repository

    def session_distress_score(self, signals: Mapping[str, object]) -> Decimal:
        if not signals:
            return _ZERO
        weights = self.repository.get_distress_signal_weights()  # {signal_id: score}
        total = _ZERO
        for signal_id, count in signals.items():
            try:
                weight = weights.get(int(signal_id))
                occurrences = int(count)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            if weight is None or occurrences <= 0:
                continue
            total += Decimal(weight) * occurrences
        return total


# Acute-state code -> prompt_library distress empathy protocol. The deterministic
# proxy detects State D (crisis) from distress-tagged Reds; A/B/C (stress /
# withdrawal / defensiveness) need the LLM linguistic detector.
_STATE_PROTOCOL = {
    "A": "PROMPT-EMPATHY-STRESS",
    "B": "PROMPT-EMPATHY-WITHDRAWAL",
    "C": "PROMPT-EMPATHY-DEFENSIVENESS",
    "D": "PROMPT-EMPATHY-DISTRESS",
}


@dataclass(frozen=True)
class DistressAssessment:
    """Result of a psychological-state assessment for one session."""

    session_distress_score: Decimal
    signal_occurrences: Mapping[str, int]
    is_high_distress: bool
    # The session must leave the confidence loop for the wellbeing path.
    distress_override: bool = False
    distress_red_count: int = 0
    # The empathy protocol (prompt_library, category='distress') to apply.
    empathy_protocol_code: str | None = None
    empathy_protocol_text: str | None = None
    # How this assessment was produced: "measured" (LLM language detection),
    # "error" (detector failed -> failed CLOSED to high distress), or None (the
    # deterministic proxy). Recorded so an error-induced closure is never
    # indistinguishable from a measured clean result.
    detector_status: str | None = None


class PsychologicalStateEngine:
    """Named psychological-safety engine: detect signal occurrences, score them
    against the seeded table, and flag High Distress. The score it returns is
    written to `sessions.session_distress_score` and drives the confidence
    reliability modifier + distress override."""

    def __init__(
        self,
        repository: ReasoningRepository,
        scorer: PsychologicalStateSignalScorer,
        high_distress_score: Decimal,
    ):
        self.repository = repository
        self.scorer = scorer
        self.high_distress_score = high_distress_score

    def assess(self, signal_occurrences: Mapping[str, int]) -> DistressAssessment:
        """Score an already-detected occurrence map (the LLM detector's output)."""
        score = self.scorer.session_distress_score(signal_occurrences)
        high = score >= self.high_distress_score
        return DistressAssessment(
            session_distress_score=score,
            signal_occurrences=dict(signal_occurrences),
            is_high_distress=high,
            distress_override=high,
        )

    def assess_from_diagnosis(
        self,
        classifications: list[AnswerClassification],
        questions: dict[int, Question],
    ) -> DistressAssessment:
        """Deterministic detection from distress-tagged Red answers.

        A distress-tagged question probes exactly the State-D acute signals
        (identity collapse, hopelessness, isolation, sustained neglect), so a Red
        on one IS an acute State-D signal. Per DISTRESS_SCORE_RED and
        session_state_bands band 4, ANY single such signal is a complete distress
        override and classifies the session High Distress -- regardless of the
        cumulative score. We therefore FAIL CLOSED: one distress Red => High
        Distress + override. The cumulative score is kept for when the LLM adds
        the State A/B/C linguistic signals; until then the persisted score is
        floored to the High-Distress threshold so the confidence model's existing
        score>=threshold override + null reliability fire through unchanged."""
        occ = self._detect_deterministic(classifications, questions)
        acute = sum(occ.values())  # distress-tagged Reds = State-D acute signals
        cumulative = self.scorer.session_distress_score(occ)
        # Strict >, matching build_distress_assessment: a tie is not an
        # exceedance. `acute` keeps its immediate trigger.
        is_high = acute >= 1 or cumulative > self.high_distress_score
        score = max(cumulative, self.high_distress_score) if is_high else cumulative
        protocol_code = _STATE_PROTOCOL["D"] if acute >= 1 else None
        protocol_text = (
            self.repository.get_empathy_protocol(protocol_code) if protocol_code else None
        )
        return DistressAssessment(
            session_distress_score=score,
            signal_occurrences=occ,
            is_high_distress=is_high,
            distress_override=is_high,
            distress_red_count=acute,
            empathy_protocol_code=protocol_code,
            empathy_protocol_text=protocol_text,
        )

    def _detect_deterministic(
        self,
        classifications: list[AnswerClassification],
        questions: dict[int, Question],
    ) -> dict[str, int]:
        count = 0
        for c in classifications:
            question = questions.get(c.question_id)
            tagged = c.is_distress_flagged or (
                question is not None and question.is_distress_tagged
            )
            if tagged and c.label == ScoreLabel.RED:
                count += 1
        if count == 0:
            return {}
        signal_id = self.repository.get_acute_distress_signal_id()
        return {str(signal_id): count} if signal_id is not None else {}
