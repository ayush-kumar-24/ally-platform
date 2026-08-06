"""Validate-mode question bias.

Between the validate and report thresholds the diagnosis already has candidate
root causes, and the job changes from gathering to confirming. Confirmation and
separation are 25% of the confidence score between them, and neither moves when
you ask another broad question -- so questions tied to a detected cause come
first.

The bias only REORDERS. Every question stays reachable, so a session that runs
out of targeted questions continues normally instead of ending early.
"""

from types import SimpleNamespace

from app.api.v1.diagnosis.engine import QuestionSelectionEngine
from app.models import RoutingState


def _q(qid, root_cause_id=None, category="Sales", priority="core", difficulty=1):
    return SimpleNamespace(
        question_id=qid, root_cause_id=root_cause_id, category=category,
        priority=priority, difficulty_level=difficulty,
    )


def _engine(detected=frozenset(), raises=False):
    def get_ids(session_id):
        if raises:
            raise RuntimeError("db down")
        return set(detected)
    return QuestionSelectionEngine(SimpleNamespace(get_detected_root_cause_ids=get_ids))


def _session(routing):
    return SimpleNamespace(session_id=1, routing_state=routing)


def test_continue_mode_keeps_the_plain_order():
    """Before validate there is no picture to confirm, so nothing is preferred."""
    engine = _engine(detected={7})
    ordered = engine.order_candidates(
        [_q(2, root_cause_id=7), _q(1)], _session(RoutingState.CONTINUE.value))
    assert [q.question_id for q in ordered] == [1, 2]


def test_validate_mode_puts_confirming_questions_first():
    engine = _engine(detected={7})
    ordered = engine.order_candidates(
        [_q(1), _q(2, root_cause_id=7)], _session(RoutingState.VALIDATE.value))
    assert [q.question_id for q in ordered] == [2, 1]


def test_the_bias_reorders_but_never_drops_anything():
    """A validate session that exhausts its targeted questions must keep going."""
    engine = _engine(detected={7})
    given = [_q(1), _q(2, root_cause_id=7), _q(3), _q(4)]
    ordered = engine.order_candidates(given, _session(RoutingState.VALIDATE.value))
    assert len(ordered) == len(given)
    assert {q.question_id for q in ordered} == {1, 2, 3, 4}


def test_ties_inside_a_group_keep_the_deterministic_order():
    """The existing key still decides within each group, so the order cannot
    wobble between requests."""
    engine = _engine(detected={7})
    ordered = engine.order_candidates(
        [_q(9, root_cause_id=7), _q(3, root_cause_id=7), _q(1)],
        _session(RoutingState.VALIDATE.value))
    assert [q.question_id for q in ordered] == [3, 9, 1]


def test_no_detections_yet_falls_back_to_the_plain_order():
    engine = _engine(detected=set())
    ordered = engine.order_candidates(
        [_q(2, root_cause_id=7), _q(1)], _session(RoutingState.VALIDATE.value))
    assert [q.question_id for q in ordered] == [1, 2]


def test_a_lookup_failure_never_breaks_selection():
    """Question selection must not fail on an optional preference."""
    engine = _engine(raises=True)
    ordered = engine.order_candidates(
        [_q(2, root_cause_id=7), _q(1)], _session(RoutingState.VALIDATE.value))
    assert [q.question_id for q in ordered] == [1, 2]


def test_select_next_question_uses_the_bias():
    engine = _engine(detected={7})
    engine.candidate_questions = lambda s, f: [_q(1), _q(2, root_cause_id=7)]
    picked = engine.select_next_question(_session(RoutingState.VALIDATE.value), None)
    assert picked.question_id == 2
