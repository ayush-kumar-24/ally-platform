"""Stage scoping: which pillars a founder's stage may be diagnosed on.

The pillar round-robin gives every pillar its turn, which is what stopped
Founder Psychology draining the whole budget -- but it also walked a pre-launch
solo founder through Revenue Maturity and Team & Leadership. Measured against
the live Stage 0 bank, 20 of an ideation founder's 30 questions landed outside
Founder DNA and Idea Validation.

Scope removes candidates rather than reordering them, because the ranking bias
only reorders and an out-of-scope question would still surface once the in-scope
ones ran out -- exactly the budget tail an ideation founder reaches.
"""

from types import SimpleNamespace

import pytest

from app.api.v1.diagnosis.engine import QuestionSelectionEngine
from app.api.v1.diagnosis.stage_scope import (
    ALL_PILLARS,
    FOUNDER_READINESS,
    MARKET_CLARITY,
    PRODUCT_AND_EXECUTION,
    REVENUE_MATURITY,
    SCOPE_BY_STAGE_ORDER,
    TEAM_AND_LEADERSHIP,
    resolve_scope,
    scope_for,
)

#: problem_id -> pillar_id, one problem per pillar so a question's pillar is
#: readable straight off its problem_id.
_PILLAR_MAP = {10 + pid: pid for pid in sorted(ALL_PILLARS)}


def _q(qid, pillar, category="Idea & Validation", priority="CORE", difficulty=1):
    return SimpleNamespace(
        question_id=qid, problem_id=10 + pillar, root_cause_id=None,
        category=category, priority=priority, difficulty_level=difficulty,
    )


def _founder(stage_order):
    stage = SimpleNamespace(stage_order=stage_order) if stage_order else None
    return SimpleNamespace(founder_id=1, stage=stage)


def _engine(candidates, *, pillar_map=_PILLAR_MAP, pillar_map_raises=False):
    def problem_to_pillar():
        if pillar_map_raises:
            raise RuntimeError("db down")
        return pillar_map

    return QuestionSelectionEngine(SimpleNamespace(
        list_candidate_questions=lambda **kw: list(candidates),
        problem_to_pillar=problem_to_pillar,
        answered_count_per_pillar_category=lambda session_id: {},
        get_detected_root_cause_ids=lambda session_id: set(),
    ))


def _session():
    return SimpleNamespace(session_id=1, routing_state="continue")


_ONE_PER_PILLAR = [_q(pid, pid) for pid in sorted(ALL_PILLARS)]


# --- the scope table itself ------------------------------------------------

def test_every_stage_has_a_scope():
    """All eight periods are covered -- no stage falls through to 'unscoped'."""
    assert sorted(SCOPE_BY_STAGE_ORDER) == [1, 2, 3, 4, 5, 6, 7, 8]


def test_ideation_is_founder_dna_and_idea_validation_only():
    scope = SCOPE_BY_STAGE_ORDER[1]
    assert scope.pillars == {FOUNDER_READINESS, MARKET_CLARITY}
    assert not scope.covers_all_pillars


@pytest.mark.parametrize("stage_order", [4, 5, 6, 7, 8])
def test_early_traction_onward_is_the_full_business(stage_order):
    assert SCOPE_BY_STAGE_ORDER[stage_order].covers_all_pillars


def test_revenue_and_team_are_out_of_scope_before_early_traction():
    """The two pillars the Business DNA doc and the product rule both exclude:
    they need an actual revenue base and actual hires to mean anything."""
    for stage_order in (1, 2, 3):
        pillars = SCOPE_BY_STAGE_ORDER[stage_order].pillars
        assert REVENUE_MATURITY not in pillars or stage_order == 3
        assert TEAM_AND_LEADERSHIP not in pillars


def test_scope_widens_monotonically_through_the_early_stages():
    """A stage never loses a pillar the stage before it had."""
    for earlier, later in zip(range(1, 8), range(2, 9)):
        assert SCOPE_BY_STAGE_ORDER[earlier].pillars <= SCOPE_BY_STAGE_ORDER[later].pillars


# --- resolution ------------------------------------------------------------

def test_unknown_stage_leaves_every_pillar_in_scope():
    """Fail open, same convention as stage_groups_for: narrowing a founder we
    cannot place would silently under-diagnose them."""
    assert resolve_scope(_founder(None)) is None
    assert scope_for(None) is None
    assert scope_for(SimpleNamespace()) is None


def test_a_stage_order_outside_the_table_is_unscoped():
    assert scope_for(SimpleNamespace(stage_order=99)) is None


# --- filtering -------------------------------------------------------------

def test_ideation_never_sees_revenue_or_team_questions():
    engine = _engine(_ONE_PER_PILLAR)
    got = engine.candidate_questions(_session(), _founder(1))
    assert {q.problem_id for q in got} == {10 + FOUNDER_READINESS, 10 + MARKET_CLARITY}


def test_prototype_stage_admits_revenue_but_still_not_team():
    engine = _engine(_ONE_PER_PILLAR)
    got = engine.candidate_questions(_session(), _founder(3))
    pillars = {q.problem_id - 10 for q in got}
    assert REVENUE_MATURITY in pillars
    assert PRODUCT_AND_EXECUTION in pillars
    assert TEAM_AND_LEADERSHIP not in pillars


def test_a_full_scope_stage_keeps_every_candidate():
    engine = _engine(_ONE_PER_PILLAR)
    got = engine.candidate_questions(_session(), _founder(5))
    assert len(got) == len(_ONE_PER_PILLAR)


def test_selection_only_ever_returns_an_in_scope_question():
    """End to end through the ranking, not just the filter."""
    engine = _engine(_ONE_PER_PILLAR)
    picked = engine.select_next_question(_session(), _founder(1))
    assert _PILLAR_MAP[picked.problem_id] in {FOUNDER_READINESS, MARKET_CLARITY}


# --- degrade paths: scope must never end a diagnosis early -----------------

def test_an_unavailable_pillar_map_leaves_the_candidates_alone():
    engine = _engine(_ONE_PER_PILLAR, pillar_map_raises=True)
    got = engine.candidate_questions(_session(), _founder(1))
    assert len(got) == len(_ONE_PER_PILLAR)


def test_an_empty_pillar_map_leaves_the_candidates_alone():
    engine = _engine(_ONE_PER_PILLAR, pillar_map={})
    got = engine.candidate_questions(_session(), _founder(1))
    assert len(got) == len(_ONE_PER_PILLAR)


def test_scope_matching_nothing_falls_back_rather_than_starving():
    """A bank with no in-scope question is a data problem. Ending the founder's
    diagnosis over it is worse than asking something off-topic."""
    only_out_of_scope = [_q(1, REVENUE_MATURITY), _q(2, TEAM_AND_LEADERSHIP)]
    engine = _engine(only_out_of_scope)
    got = engine.candidate_questions(_session(), _founder(1))
    assert len(got) == 2


def test_no_candidates_stays_no_candidates():
    """An exhausted bank must still report exhaustion -- that is the completion
    signal, and scope must not turn it into anything else."""
    engine = _engine([])
    assert engine.candidate_questions(_session(), _founder(1)) == []
