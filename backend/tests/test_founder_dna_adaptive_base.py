"""The base journey has to react to what the founder said, not just replay.

The engine used to treat every base question (arc_position < FOLLOW_UP_FLOOR)
as unconditional, applying adaptive skipping only to follow-ups. Since the
base journey IS the first nine turns, the practical effect was that for those
nine turns a founder's answers could not change the next question at all --
under a screen that says "Adaptive diagnosis".

Skipping is now allowed on base questions, bounded by the guarantee that used
to be enforced by making them unconditional: a dimension is skipped only once
it has ALREADY been asked and been judged resolved, so the arc still visits
every dimension. Both halves are tested here, because dropping either one
brings back a bug that shipped before.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.api.v1.founder_dna.engine import FOLLOW_UP_FLOOR, FounderDnaSelectionEngine


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


def _select(repo):
    return FounderDnaSelectionEngine(repo).select_next_question(FOUNDER, "Stage 0")


def test_a_resolved_dimension_loses_its_remaining_base_questions():
    """origin sorts first by arc, but the advisor already called it resolved
    off the answer to origin's first question."""
    candidates = [
        _q(10, "origin", 10),
        _q(11, "origin", 20),
        _q(12, "core_values", 30),
        CLOSING,
    ]
    repo = _Repo(
        candidates,
        resolved={"origin"},
        answered_total=1,
        per_dimension={"origin": 1},
    )
    assert _select(repo).founder_dna_question_id == 12


def test_a_resolved_dimension_that_was_never_asked_is_still_asked():
    """The breadth guarantee. `resolved` without any answers is not a
    judgement about this founder -- nothing has been read yet -- and honouring
    it would let a dimension go permanently unasked, which is exactly the bug
    that made base questions unconditional in the first place."""
    candidates = [
        _q(10, "origin", 10),
        _q(12, "core_values", 30),
        CLOSING,
    ]
    repo = _Repo(
        candidates,
        resolved={"origin"},
        answered_total=0,
        per_dimension={},
    )
    assert _select(repo).founder_dna_question_id == 10


def test_unresolved_base_questions_still_run_in_arc_order():
    """Skipping filters, it never reorders -- the doc's narrative arc is the
    whole reason base ordering is by arc_position rather than round-robin."""
    candidates = [
        _q(12, "core_values", 30),
        _q(10, "origin", 10),
        _q(11, "vision", 20),
        CLOSING,
    ]
    repo = _Repo(
        candidates,
        resolved=set(),
        answered_total=3,
        per_dimension={"archetype": 3},
    )
    assert _select(repo).founder_dna_question_id == 10


def test_all_base_dimensions_resolved_falls_through_to_follow_ups():
    """Nothing left worth asking in the base pool is not a dead end -- it
    hands over to the follow-up/close path rather than returning None."""
    candidates = [
        _q(10, "origin", 10),
        _q(20, "core_values", FOLLOW_UP_FLOOR + 1),
        CLOSING,
    ]
    repo = _Repo(
        candidates,
        resolved={"origin"},
        answered_total=2,
        per_dimension={"origin": 2},
    )
    assert _select(repo).founder_dna_question_id == 20


def test_all_base_resolved_and_no_follow_ups_left_ends_on_the_close():
    candidates = [
        _q(10, "origin", 10),
        CLOSING,
    ]
    repo = _Repo(
        candidates,
        resolved={"origin"},
        answered_total=2,
        per_dimension={"origin": 2},
    )
    assert _select(repo).founder_dna_question_id == CLOSING.founder_dna_question_id
