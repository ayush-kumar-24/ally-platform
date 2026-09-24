"""Integration of RCCS / the quality gate into the live diagnosis flow.

Covers the wiring the pure-model tests in test_rccs.py cannot: the safety
ceiling's separation from the coverage denominator, the selector's RCCS bias,
post-report termination, and the cost guarantee.
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.api.v1.diagnosis.rccs import RCCS_STRONG_THRESHOLD
from app.core.config import settings
from app.models.enums import RoutingState, SessionStatus


# --- 26. The safety ceiling is NOT the coverage denominator -------------------

def test_safety_ceiling_and_coverage_denominator_are_different_numbers():
    """The whole point of isolating them. If these ever collapse into one value,
    allowing longer diagnoses silently redefines what the confidence score means
    by 'fully covered' and moves the 80-point threshold underneath everything."""
    assert settings.safety_ceiling(None) > settings.question_budget(None)
    assert settings.question_budget(None) == settings.MAX_DIAGNOSIS_QUESTIONS


def test_coverage_denominator_is_unchanged_by_this_work():
    """Pinned explicitly: the brief forbids silently changing this meaning."""
    assert settings.MAX_DIAGNOSIS_QUESTIONS == 30
    assert settings.question_budget(None) == 30
    assert settings.question_budget(12) == 12


def test_safety_ceiling_scales_with_a_stage_budget_but_never_tightens():
    assert settings.safety_ceiling(12) >= settings.DIAGNOSIS_SAFETY_CEILING
    assert settings.safety_ceiling(50) == 200
    assert settings.safety_ceiling(0) == settings.DIAGNOSIS_SAFETY_CEILING
    assert settings.safety_ceiling(None) > settings.question_budget(None)


def test_2_the_ceiling_permits_a_materially_longer_diagnosis_than_before():
    """'No fixed question count' has to mean a founder CAN be asked more than 30."""
    assert settings.safety_ceiling(None) >= 4 * settings.MAX_DIAGNOSIS_QUESTIONS


# --- Completion ordering in the live service ----------------------------------

def test_attach_question_completes_on_the_safety_ceiling_not_the_budget():
    """A session at the old 30-question budget must still be IN PROGRESS."""
    from app.api.v1.diagnosis.service import DiagnosisService

    session = SimpleNamespace(
        session_id=1, questions_answered_count=settings.MAX_DIAGNOSIS_QUESTIONS,
        status=SessionStatus.IN_PROGRESS.value, routing_state=RoutingState.CONTINUE.value,
        current_question_id=None, current_category=None, completed_at=None,
    )
    founder = SimpleNamespace(stage=SimpleNamespace(question_budget=None))
    question = SimpleNamespace(question_id=7, category="Sales Execution")

    DiagnosisService._attach_question(
        SimpleNamespace(), session, question, founder
    )
    assert session.status == SessionStatus.IN_PROGRESS.value
    assert session.current_question_id == 7


def test_attach_question_still_completes_at_the_safety_ceiling():
    from app.api.v1.diagnosis.service import DiagnosisService

    session = SimpleNamespace(
        session_id=1, questions_answered_count=settings.safety_ceiling(None),
        status=SessionStatus.IN_PROGRESS.value, routing_state=RoutingState.CONTINUE.value,
        current_question_id=None, current_category=None, completed_at=None,
    )
    founder = SimpleNamespace(stage=SimpleNamespace(question_budget=None))

    DiagnosisService._attach_question(
        SimpleNamespace(), session, SimpleNamespace(question_id=7, category="x"), founder
    )
    assert session.status == SessionStatus.COMPLETED.value


def test_generate_report_routing_still_completes_the_session():
    """The adaptive gate reaches the service THROUGH routing_state, so this is
    the path a problem-explained diagnosis takes to actually stop."""
    from app.api.v1.diagnosis.service import DiagnosisService

    session = SimpleNamespace(
        session_id=1, questions_answered_count=11,
        status=SessionStatus.IN_PROGRESS.value,
        routing_state=RoutingState.GENERATE_REPORT.value,
        current_question_id=None, current_category=None, completed_at=None,
    )
    founder = SimpleNamespace(stage=SimpleNamespace(question_budget=None))

    DiagnosisService._attach_question(
        SimpleNamespace(), session, SimpleNamespace(question_id=7, category="x"), founder
    )
    assert session.status == SessionStatus.COMPLETED.value
    assert session.routing_state == RoutingState.GENERATE_REPORT.value


# --- 26. Post-report termination ----------------------------------------------

def test_26_a_completed_session_cannot_be_answered_again():
    """Post-report the diagnosis ENDS. Structural, not advisory: every mutating
    entry point runs _assert_active first."""
    from app.api.v1.diagnosis.service import DiagnosisService, SessionNotActiveError

    session = SimpleNamespace(session_id=1, status=SessionStatus.COMPLETED.value)
    with pytest.raises(SessionNotActiveError):
        DiagnosisService._assert_active(SimpleNamespace(), session)


def test_26_selector_offers_no_rccs_contenders_once_the_report_is_triggered():
    from app.api.v1.diagnosis.engine import QuestionSelectionEngine

    session = SimpleNamespace(
        session_id=1, routing_state=RoutingState.GENERATE_REPORT.value
    )
    engine = QuestionSelectionEngine(SimpleNamespace(db=None))
    assert engine._rccs_contender_ids(session) == set()


# --- 7. Selector extension -----------------------------------------------------

def test_selector_degrades_to_the_existing_order_without_rccs_state():
    """No contenders and no detections must return the untouched base key -- the
    ordering is not 'equivalent to' today's, it IS today's."""
    from app.api.v1.diagnosis.engine import QuestionSelectionEngine

    engine = QuestionSelectionEngine(SimpleNamespace(db=None))
    session = SimpleNamespace(session_id=1, routing_state=RoutingState.CONTINUE.value)

    base_sentinel = object()
    engine._round_robin_key_for = lambda *a, **k: base_sentinel
    engine._rccs_contender_ids = lambda s: set()
    engine._detected_root_cause_ids = lambda s: set()

    assert engine._sort_key_for(session) is base_sentinel


def test_selector_ranks_rccs_contenders_ahead_of_detected_and_the_rest():
    from app.api.v1.diagnosis.engine import QuestionSelectionEngine

    engine = QuestionSelectionEngine(SimpleNamespace(db=None))
    session = SimpleNamespace(session_id=1, routing_state=RoutingState.VALIDATE.value)

    engine._round_robin_key_for = lambda *a, **k: (lambda q: (0,))
    engine._rccs_contender_ids = lambda s: {11}
    engine._detected_root_cause_ids = lambda s: {22}

    key = engine._sort_key_for(session)
    contender = SimpleNamespace(root_cause_id=11)
    detected = SimpleNamespace(root_cause_id=22)
    other = SimpleNamespace(root_cause_id=33)

    assert key(contender) < key(detected) < key(other)


# --- 25. Cost --------------------------------------------------------------

def test_25_the_rccs_model_makes_no_model_calls():
    """Structural guarantee, not a measurement: the scoring and stopping modules
    import nothing from the LLM layer, so a stopping decision cannot cost a call."""
    import app.api.v1.diagnosis.completion as completion_mod
    import app.api.v1.diagnosis.rccs as rccs_mod

    for module in (rccs_mod, completion_mod):
        source = open(module.__file__).read()
        assert "services.llm" not in source
        assert "LLMProvider" not in source


def test_threshold_is_defined_once_and_never_re_hardcoded():
    """Guards against a second, drifting copy of the product's 0.80 rule.

    The constant is declared exactly once, and every other module in the adaptive
    path reaches it by import rather than by writing the number again -- which is
    how a threshold ends up meaning two different things in two places.
    """
    import app.api.v1.diagnosis.adaptive_loop as loop_mod
    import app.api.v1.diagnosis.completion as completion_mod
    import app.api.v1.diagnosis.engine as engine_mod
    import app.api.v1.diagnosis.rccs as rccs_mod

    assert RCCS_STRONG_THRESHOLD == Decimal("0.80")

    declarations = [
        line for line in open(rccs_mod.__file__).read().splitlines()
        if line.startswith("RCCS_STRONG_THRESHOLD")
    ]
    assert declarations == ['RCCS_STRONG_THRESHOLD = Decimal("0.80")']

    for module in (completion_mod, loop_mod, engine_mod):
        source = open(module.__file__).read()
        # Prose may DISCUSS 0.80; what must not exist anywhere else is a second
        # literal the code actually reads.
        assert 'Decimal("0.80")' not in source, module.__name__
        assert "RCCS_STRONG_THRESHOLD" in source
