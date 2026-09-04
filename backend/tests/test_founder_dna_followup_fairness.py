"""Follow-up slots must be spread across unresolved dimensions, not hoarded.

Founder DNA has 15 dimensions and a ceiling of base + 2 follow-ups + 1 close, so once the
base journey is done there are only a couple of follow-up slots left. Ordering
those purely by arc_position let the lowest-arc unresolved dimension take every
one of them.

Observed live: `purpose_mission` was asked three times while `core_values` and
`energy_patterns` were never asked again, and the phase then closed reporting
12 of 14 dimensions resolved -- with those two blank permanently, since nothing
revisits a completed phase.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.api.v1.founder_dna.engine import FOLLOW_UP_FLOOR, FounderDnaSelectionEngine
from app.core.config import settings


def _q(qid: int, dimension: str, arc: int, closing: bool = False):
    return SimpleNamespace(
        founder_dna_question_id=qid,
        dimension_code=dimension,
        arc_position=arc,
        is_closing=closing,
    )


class _Repo:
    """Only the methods the selector touches."""

    def __init__(self, candidates, resolved, answered_total, per_dimension,
                 closing_done=False):
        self._candidates = candidates
        self._resolved = resolved
        self._answered_total = answered_total
        self._per_dimension = per_dimension
        self._closing_done = closing_done

    def closing_answered(self, founder_id, stage_group):
        return self._closing_done

    def list_candidate_questions(self, founder_id, stage_group):
        return list(self._candidates)

    def get_resolved_dimensions(self, founder):
        return set(self._resolved)

    def count_answered(self, founder_id):
        return self._answered_total

    def answers_per_dimension(self, founder_id, stage_group):
        return dict(self._per_dimension)


FOUNDER = SimpleNamespace(founder_id=1)
CLOSING = _q(999, "emotional_intelligence", 100, closing=True)


def test_followup_goes_to_the_least_asked_unresolved_dimension():
    """purpose_mission sorts first by arc, but has already had 3 attempts."""
    candidates = [
        _q(10, "purpose_mission", FOLLOW_UP_FLOOR + 1),
        _q(11, "core_values", FOLLOW_UP_FLOOR + 5),
        _q(12, "energy_patterns", FOLLOW_UP_FLOOR + 9),
        CLOSING,
    ]
    repo = _Repo(
        candidates,
        resolved=["origin", "archetype"],
        answered_total=10,
        per_dimension={"purpose_mission": 3, "core_values": 1, "energy_patterns": 1},
    )

    chosen = FounderDnaSelectionEngine(repo).select_next_question(FOUNDER, "Stage 0")

    # Not purpose_mission, despite it having the lowest arc_position.
    assert chosen.dimension_code == "core_values"


def test_arc_position_still_breaks_ties_at_equal_attention():
    """Authored order must still decide between equally-attempted dimensions."""
    candidates = [
        _q(11, "core_values", FOLLOW_UP_FLOOR + 5),
        _q(12, "energy_patterns", FOLLOW_UP_FLOOR + 9),
        CLOSING,
    ]
    repo = _Repo(
        candidates,
        resolved=[],
        answered_total=10,
        per_dimension={"core_values": 2, "energy_patterns": 2},
    )

    chosen = FounderDnaSelectionEngine(repo).select_next_question(FOUNDER, "Stage 0")

    assert chosen.dimension_code == "core_values"


def test_resolved_dimensions_are_never_followed_up():
    candidates = [
        _q(10, "purpose_mission", FOLLOW_UP_FLOOR + 1),
        _q(11, "core_values", FOLLOW_UP_FLOOR + 5),
        CLOSING,
    ]
    repo = _Repo(
        candidates,
        resolved=["purpose_mission"],
        answered_total=10,
        per_dimension={"purpose_mission": 0, "core_values": 9},
    )

    chosen = FounderDnaSelectionEngine(repo).select_next_question(FOUNDER, "Stage 0")

    # core_values wins on the only criterion that matters: it is still open.
    assert chosen.dimension_code == "core_values"


def test_base_questions_still_outrank_every_follow_up():
    """The mandatory arc must not be reordered by the fairness rule."""
    candidates = [
        _q(1, "vision", 5),                                  # base
        _q(10, "purpose_mission", FOLLOW_UP_FLOOR + 1),      # follow-up
        CLOSING,
    ]
    repo = _Repo(
        candidates,
        resolved=[],
        answered_total=3,
        per_dimension={"vision": 8, "purpose_mission": 0},
    )

    chosen = FounderDnaSelectionEngine(repo).select_next_question(FOUNDER, "Stage 0")

    assert chosen.founder_dna_question_id == 1


def test_closing_question_wins_once_the_budget_is_spent():
    """With no room left, the phase closes rather than squeezing one more in."""
    candidates = [
        _q(11, "core_values", FOLLOW_UP_FLOOR + 5),
        CLOSING,
    ]
    repo = _Repo(
        candidates,
        resolved=[],
        # Derived from the ceiling, not pinned to it. This read `16` back when
        # MAX_FOUNDER_DNA_QUESTIONS was 17; raising it to 18 for the fifteenth
        # dimension (RISK_APPETITE) left the literal asserting nothing -- 16 + 1
        # no longer spends the budget, so the phase correctly kept asking and
        # the test failed on behaviour that was right. One less than the ceiling
        # is the actual condition: the last slot is the reserved close.
        answered_total=settings.MAX_FOUNDER_DNA_QUESTIONS - 1,
        per_dimension={"core_values": 0},
    )

    chosen = FounderDnaSelectionEngine(repo).select_next_question(FOUNDER, "Stage 0")

    assert chosen.is_closing is True


def test_nothing_is_asked_after_the_closing_question():
    """The regression: a follow-up landed AFTER the wow-close.

    Budget and pool both still allow another question here -- `core_values` is
    unresolved, unanswered and affordable. The close having already run is what
    must end the phase.
    """
    repo = _Repo(
        [_q(11, "core_values", FOLLOW_UP_FLOOR + 5)],  # close already answered
        resolved=[],
        answered_total=10,                              # plenty of budget left
        per_dimension={"core_values": 0},
        closing_done=True,
    )

    assert FounderDnaSelectionEngine(repo).select_next_question(FOUNDER, "Stage 0") is None


def test_close_still_comes_last_when_a_follow_up_is_affordable():
    """Ordering, not exclusion: the follow-up runs first, the close after it."""
    candidates = [
        _q(15, "energy_patterns", FOLLOW_UP_FLOOR + 2),
        CLOSING,
    ]
    repo = _Repo(
        candidates,
        resolved=[],
        # Comfortably inside the ceiling, so a follow-up is still affordable.
        answered_total=settings.MAX_FOUNDER_DNA_QUESTIONS - 4,
        per_dimension={"energy_patterns": 1},
    )

    chosen = FounderDnaSelectionEngine(repo).select_next_question(FOUNDER, "Stage 0")

    assert chosen.is_closing is False
    assert chosen.dimension_code == "energy_patterns"
