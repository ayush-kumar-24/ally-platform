"""Industry gating: whether a question was written for THIS founder's industry.

The failure these exist to stop, measured on the seeded bank rather than
guessed: thirty industry datasets seed 60 questions each (1,800 in total), every
one of them carrying a real `primary_stage_group`. `list_candidate_questions`
filters on stage group and nothing else, so all 1,800 are eligible for every
founder. A Logistics founder at Stage 1->10+ is a valid candidate for
`S10-SAS-011` "Do you have any security certification buyers recognise?"; a SaaS
founder for `S01-LOG-002` "Out of 100 deliveries, how many arrive damaged?".

They are not asked constantly today only because the industry rows were inserted
last and carry high `question_id`s, which lose the final tie-break in
`_sort_key`. That is insertion order, not a rule.

The gate reads `question_industry_mapping`, which every industry seed populates
and which nothing in `backend/app/` read before this. A question with NO row
there is universal, and half the effort below goes on proving the universal bank
survives -- a gate that quietly narrowed the general catalogue would have traded
one wrong behaviour for a worse one.

Question ids below mirror the real shape: SAS/LOG/MFG questions sit at the high
end (industry seeds ran last), universal ones low, so any test that passes by
accident of ordering would pass identically before the gate existed.
"""

import contextlib
from types import SimpleNamespace

from app.api.v1.diagnosis.engine import QuestionSelectionEngine
from app.api.v1.diagnosis.industry_scope import (
    excluded_question_ids,
    industry_id_for,
)

SAAS_ID, LOGISTICS_ID, MANUFACTURING_ID = 3, 17, 21
_ID_TO_CODE = {SAAS_ID: "saas", LOGISTICS_ID: "logistics", MANUFACTURING_ID: "manufacturing"}

#: Real pillar/category pairs from the seeds, so the round-robin below has
#: something honest to spread across.
SALES, OPERATIONS = 4, 3

# Universal questions -- no question_industry_mapping row. Low ids, as in the
# live bank.
U_SALES_A, U_SALES_B, U_OPS_A = 101, 102, 103
# Industry-owned questions. High ids, as in the live bank.
SAS_SALES, SAS_OPS = 9001, 9002
LOG_OPS, LOG_SALES = 9101, 9102
MFG_OPS = 9201

_OWNED = {
    SAS_SALES: frozenset({"saas"}),
    SAS_OPS: frozenset({"saas"}),
    LOG_OPS: frozenset({"logistics"}),
    LOG_SALES: frozenset({"logistics"}),
    MFG_OPS: frozenset({"manufacturing"}),
}

_PILLAR_MAP = {
    11: SALES, 12: SALES, 13: OPERATIONS,       # universal problems
    21: SALES, 22: OPERATIONS,                  # saas problems
    31: OPERATIONS, 32: SALES,                  # logistics problems
    41: OPERATIONS,                             # manufacturing problems
}


def _q(qid, problem_id, category="Sales & Revenue", priority="CORE", difficulty=1):
    return SimpleNamespace(
        question_id=qid, problem_id=problem_id, root_cause_id=None,
        category=category, priority=priority, difficulty_level=difficulty,
    )


_BANK = [
    _q(U_SALES_A, 11), _q(U_SALES_B, 12), _q(U_OPS_A, 13, "Operations & Systems"),
    _q(SAS_SALES, 21), _q(SAS_OPS, 22, "Operations & Systems"),
    _q(LOG_OPS, 31, "Operations & Systems"), _q(LOG_SALES, 32),
    _q(MFG_OPS, 41, "Operations & Systems"),
]

UNIVERSAL = {U_SALES_A, U_SALES_B, U_OPS_A}


def _founder(industry_mapped_id=None, stage_order=5):
    """stage_order 5 (Growth) so `scope.withholds_nothing` is True and the stage
    filters cannot be what removes a question -- anything missing below was
    removed by the industry gate and nothing else."""
    return SimpleNamespace(
        founder_id=1,
        stage=SimpleNamespace(stage_order=stage_order),
        industry_mapped_id=industry_mapped_id,
    )


def _session(founder_industry_id=None):
    return SimpleNamespace(
        session_id=1, routing_state="continue",
        founder_industry_id=founder_industry_id,
    )


def _engine(*, owned=None, owned_raises=False, code_raises=False, candidates=None):
    def question_owned_by_industry():
        if owned_raises:
            raise RuntimeError("relation question_industry_mapping does not exist")
        return dict(_OWNED if owned is None else owned)

    def industry_code(industry_id):
        if code_raises:
            raise RuntimeError("db down")
        return _ID_TO_CODE.get(industry_id)

    fake_db = SimpleNamespace(begin_nested=lambda: contextlib.nullcontext())
    return QuestionSelectionEngine(SimpleNamespace(
        db=fake_db,
        list_candidate_questions=lambda **kw: list(
            _BANK if candidates is None else candidates),
        problem_to_pillar=lambda: dict(_PILLAR_MAP),
        problem_to_dimension=lambda: {},
        problem_to_code=lambda: {},
        root_cause_to_code=lambda: {},
        question_owned_by_industry=question_owned_by_industry,
        industry_code=industry_code,
        answered_count_per_pillar_category=lambda session_id: {},
        get_detected_root_cause_ids=lambda session_id: set(),
    ))


def _ask(founder, session=None, **engine_kwargs):
    return {
        q.question_id
        for q in _engine(**engine_kwargs).candidate_questions(
            session if session is not None else _session(), founder)
    }


# --- the bug this gate exists to stop -----------------------------------


def test_a_saas_founder_is_never_asked_another_industrys_question():
    got = _ask(_founder(SAAS_ID))
    assert LOG_OPS not in got and LOG_SALES not in got
    assert MFG_OPS not in got


def test_a_logistics_founder_is_never_asked_a_saas_question():
    got = _ask(_founder(LOGISTICS_ID))
    assert SAS_SALES not in got and SAS_OPS not in got
    assert MFG_OPS not in got


def test_each_industry_keeps_its_own_questions():
    assert {SAS_SALES, SAS_OPS} <= _ask(_founder(SAAS_ID))
    assert {LOG_OPS, LOG_SALES} <= _ask(_founder(LOGISTICS_ID))
    assert MFG_OPS in _ask(_founder(MANUFACTURING_ID))


def test_two_industries_at_the_same_stage_get_different_banks():
    """The headline claim: same stage, same pillars, different questions."""
    assert _ask(_founder(SAAS_ID)) != _ask(_founder(LOGISTICS_ID))


# --- what the gate must never do ----------------------------------------


def test_universal_questions_reach_every_industry():
    """The gate removes another industry's questions. It never removes a
    question that belongs to nobody in particular, which is most of the bank."""
    for industry in (SAAS_ID, LOGISTICS_ID, MANUFACTURING_ID, None):
        assert UNIVERSAL <= _ask(_founder(industry))


def test_the_gate_only_ever_removes_industry_owned_questions():
    for industry in (SAAS_ID, LOGISTICS_ID, MANUFACTURING_ID):
        removed = {q.question_id for q in _BANK} - _ask(_founder(industry))
        assert removed <= set(_OWNED)


# --- degrade paths: four ways to end up not gating ----------------------


def test_an_unreadable_mapping_table_disables_the_gate_not_the_diagnosis():
    """A database without the industry migrations applied must behave exactly
    as it did before this gate existed, not raise."""
    assert _ask(_founder(SAAS_ID), owned_raises=True) == {q.question_id for q in _BANK}


def test_no_mapping_rows_gates_nothing():
    assert _ask(_founder(SAAS_ID), owned={}) == {q.question_id for q in _BANK}


def test_an_unreadable_industry_code_is_treated_as_unknown_not_as_no_gate():
    """Failing open here would re-admit all thirty industries at once -- the
    exact thing the gate exists to stop. Unknown means 'no industry's questions
    are yours', so the universal bank survives and nothing else does."""
    got = _ask(_founder(SAAS_ID), code_raises=True)
    assert got == UNIVERSAL


def test_a_gate_that_would_empty_the_set_leaves_it_alone():
    """Same invariant as `_in_scope` and `_context_gated`: never end a
    founder's diagnosis over a data problem."""
    only_other_industries = [_q(LOG_OPS, 31, "Operations & Systems"), _q(MFG_OPS, 41, "Operations & Systems")]
    got = _ask(_founder(SAAS_ID), candidates=only_other_industries)
    assert got == {LOG_OPS, MFG_OPS}


def test_a_founder_with_no_industry_keeps_the_universal_bank():
    """Skipping the industry question must not cost a founder the general
    catalogue -- but it must not hand them all thirty industries either."""
    got = _ask(_founder(None))
    assert got == UNIVERSAL


# --- session isolation ---------------------------------------------------


def test_the_session_snapshot_wins_over_the_founders_current_industry():
    """A founder who edits their industry mid-diagnosis must not change which
    questions the remaining turns are drawn from."""
    founder = _founder(LOGISTICS_ID)                 # edited to Logistics today
    got = _ask(founder, session=_session(SAAS_ID))   # session started as SaaS
    assert {SAS_SALES, SAS_OPS} <= got
    assert LOG_OPS not in got


def test_the_founder_is_used_when_the_session_has_no_snapshot():
    got = _ask(_founder(SAAS_ID), session=_session(None))
    assert {SAS_SALES, SAS_OPS} <= got
    assert LOG_OPS not in got


# --- determinism ---------------------------------------------------------


def test_the_same_session_gates_identically_every_time():
    founder = _founder(SAAS_ID)
    first = [q.question_id for q in _engine().candidate_questions(_session(), founder)]
    for _ in range(5):
        assert [q.question_id
                for q in _engine().candidate_questions(_session(), founder)] == first


# --- the rule itself, without a database ---------------------------------


def test_excluded_question_ids_is_pure_and_readable():
    assert excluded_question_ids(_OWNED, "saas") == frozenset(
        {LOG_OPS, LOG_SALES, MFG_OPS})
    assert excluded_question_ids(_OWNED, "logistics") == frozenset(
        {SAS_SALES, SAS_OPS, MFG_OPS})


def test_an_unknown_industry_excludes_every_industry_owned_question():
    assert excluded_question_ids(_OWNED, None) == frozenset(_OWNED)
    assert excluded_question_ids(_OWNED, "") == frozenset(_OWNED)


def test_an_empty_ownership_map_excludes_nothing():
    assert excluded_question_ids({}, "saas") == frozenset()
    assert excluded_question_ids(None, "saas") == frozenset()


def test_industry_codes_are_matched_case_and_space_insensitively():
    assert excluded_question_ids(_OWNED, "  SaaS  ") == frozenset(
        {LOG_OPS, LOG_SALES, MFG_OPS})


def test_a_question_shared_by_two_industries_is_kept_by_both():
    shared = {SAS_SALES: frozenset({"saas", "logistics"})}
    assert excluded_question_ids(shared, "saas") == frozenset()
    assert excluded_question_ids(shared, "logistics") == frozenset()
    assert excluded_question_ids(shared, "manufacturing") == frozenset({SAS_SALES})


def test_industry_id_for_prefers_the_session_and_never_raises():
    assert industry_id_for(_session(SAAS_ID), _founder(LOGISTICS_ID)) == SAAS_ID
    assert industry_id_for(_session(None), _founder(LOGISTICS_ID)) == LOGISTICS_ID
    assert industry_id_for(_session(None), _founder(None)) is None
    assert industry_id_for(None, None) is None
    assert industry_id_for(_session("not-a-number"), _founder(None)) is None
