"""Industry relevance: which question represents a pillar's turn.

The companion to `test_industry_scope_gate`. That one is a FILTER -- another
industry's questions are not this founder's. This one is a PREFERENCE -- among
the questions that are legitimately theirs, the ones their industry says matter
most come first.

The whole design is in where the term sits: FOURTH in the selection key, below
`answered_in_that_pillar` and `answered_in_that_(pillar, category)`, above
`_sort_key`. So it decides WHICH question fills a round and never how many
rounds a pillar gets. Half the tests below exist to hold that line, because the
failure mode is not subtle: 60 seeded CORE questions per industry, against a
30-question budget, would happily eat a pillar that has not been asked about at
all -- the exact starvation `_round_robin_key_for` was written to stop.

Two signals feed it, and they are deliberately different in kind:

  * `question_industry_mapping` -- written FOR this industry (primary/supporting)
  * `industries.top_pain_point_weights` -- a UNIVERSAL question whose problem
    this industry says goes wrong more than average

The second is what makes a SaaS founder get the general churn question ahead of
the general supply-chain one, without either being industry-owned. It matters
that it keeps working when absent: only four of the thirty industries carry
weights today, so "mapping signal only" is the live case for twenty-six of them
and is tested as a first-class path, not an edge case.
"""

import contextlib
from decimal import Decimal
from types import SimpleNamespace

from app.api.v1.diagnosis.engine import QuestionSelectionEngine
from app.api.v1.diagnosis.industry_scope import (
    PRIMARY_RANK,
    STRONG_WEIGHT_RANK,
    SUPPORTING_RANK,
    UNIVERSAL_RANK,
    WEAK_WEIGHT_RANK,
    normalise_weights,
    relevance_ranker,
)

SAAS_ID = 3
SALES, OPERATIONS, FOUNDER = 4, 3, 1

# One (pillar, category) cell, five questions, so ONLY the relevance term can
# separate them. Ids ascend in the order _sort_key would pick them, so any test
# that passes by accident of the tie-break would pick SAS_PRIMARY last, not
# first.
SAS_PRIMARY, SAS_SUPPORTING = 9001, 9002
U_STRONG, U_WEAK, U_PLAIN = 9003, 9004, 9005

_APPLICABILITY = {SAS_PRIMARY: "primary", SAS_SUPPORTING: "supporting"}

#: Real SaaS weights, from 02_industries.sql.
_WEIGHTS_RAW = {
    "IVA-001": 1.5, "SAL-005": 1.5, "GTM-002": 1.3, "SAL-003": 1.3,
    "PRD-001": 1.15, "FND-006": 1.05, "GTM-007": 1.05, "SAL-001": 1.05,
}

_PROBLEM_CODE = {
    21: "SAS-007",   # industry-owned, no weight of its own
    22: "SAS-006",
    31: "SAL-005",   # universal, weighted 1.5  -> strong
    32: "SAL-001",   # universal, weighted 1.05 -> weak
    33: "SAL-002",   # universal, unweighted    -> plain
}
_PILLAR_MAP = {21: SALES, 22: SALES, 31: SALES, 32: SALES, 33: SALES}


def _q(qid, problem_id, category="Sales & Revenue", priority="CORE", difficulty=1):
    return SimpleNamespace(
        question_id=qid, problem_id=problem_id, root_cause_id=None,
        category=category, priority=priority, difficulty_level=difficulty,
    )


_BANK = [
    _q(SAS_PRIMARY, 21), _q(SAS_SUPPORTING, 22),
    _q(U_STRONG, 31), _q(U_WEAK, 32), _q(U_PLAIN, 33),
]


def _founder(industry_mapped_id=SAAS_ID):
    return SimpleNamespace(
        founder_id=1,
        stage=SimpleNamespace(stage_order=5),
        industry_mapped_id=industry_mapped_id,
    )


def _session(founder_industry_id=SAAS_ID, routing_state="continue"):
    return SimpleNamespace(
        session_id=1, routing_state=routing_state,
        founder_industry_id=founder_industry_id,
    )


def _engine(
    *, bank=None, weights=None, applicability=None, answered=None,
    pillar_map=None, raises=False, detected=(),
):
    def guard(value):
        if raises:
            raise RuntimeError("db down")
        return value

    fake_db = SimpleNamespace(begin_nested=lambda: contextlib.nullcontext())
    return QuestionSelectionEngine(SimpleNamespace(
        db=fake_db,
        list_candidate_questions=lambda **kw: list(_BANK if bank is None else bank),
        problem_to_pillar=lambda: dict(_PILLAR_MAP if pillar_map is None else pillar_map),
        problem_to_dimension=lambda: {},
        problem_to_code=lambda: guard(dict(_PROBLEM_CODE)),
        root_cause_to_code=lambda: {},
        # Step 1's gate: nothing owned by another industry in these banks.
        question_owned_by_industry=lambda: {
            SAS_PRIMARY: frozenset({"saas"}), SAS_SUPPORTING: frozenset({"saas"}),
        },
        industry_code=lambda industry_id: guard("saas"),
        question_applicability_for_industry=lambda code: guard(
            dict(_APPLICABILITY if applicability is None else applicability)),
        industry_pain_point_weights=lambda industry_id: guard(
            dict(_WEIGHTS_RAW if weights is None else weights)),
        answered_count_per_pillar_category=lambda session_id: dict(answered or {}),
        get_detected_root_cause_ids=lambda session_id: set(detected),
    ))


def _order(founder=None, session=None, **kw):
    engine = _engine(**kw)
    founder = founder if founder is not None else _founder()
    session = session if session is not None else _session()
    return [q.question_id
            for q in engine.order_candidates(
                engine.candidate_questions(session, founder), session, founder)]


# --- the ordering itself -------------------------------------------------


def test_relevance_orders_a_single_pillar_cell_strongest_first():
    """All five sit in one (pillar, category), so the coverage terms are level
    and this is purely the relevance term against the id tie-break."""
    assert _order() == [SAS_PRIMARY, SAS_SUPPORTING, U_STRONG, U_WEAK, U_PLAIN]


def test_an_industrys_own_question_outranks_a_weighted_general_one():
    """A question written for the industry is a stronger statement of relevance
    than a weight applied to a general one."""
    order = _order()
    assert order.index(SAS_PRIMARY) < order.index(U_STRONG)


def test_a_heavily_weighted_problem_outranks_a_mildly_weighted_one():
    order = _order()
    assert order.index(U_STRONG) < order.index(U_WEAK) < order.index(U_PLAIN)


def test_the_first_question_asked_is_the_industrys_own():
    engine = _engine()
    picked = engine.select_next_question(_session(), _founder())
    assert picked.question_id == SAS_PRIMARY


# --- what the term must NEVER do -----------------------------------------


def test_pillar_coverage_still_outranks_industry_relevance():
    """The line this whole design is built on. An unasked pillar's PLAIN
    question must beat an already-covered pillar's industry-owned one --
    otherwise a 60-question industry bank starves the pillars it has nothing
    to say about."""
    covered, unasked = SALES, OPERATIONS
    bank = [_q(SAS_PRIMARY, 21), _q(U_PLAIN, 99, "Operations & Systems")]
    order = _order(
        bank=bank,
        pillar_map={21: covered, 99: unasked},
        answered={(covered, "Sales & Revenue"): 3},
    )
    assert order == [U_PLAIN, SAS_PRIMARY]


def test_category_coverage_within_a_pillar_still_outranks_relevance():
    """Second line of the same defence: a pillar must not be read off one
    narrow slice just because that slice is industry-flavoured."""
    bank = [_q(SAS_PRIMARY, 21), _q(U_PLAIN, 33, "Financial Management")]
    order = _order(
        bank=bank,
        pillar_map={21: SALES, 33: SALES},
        answered={(SALES, "Sales & Revenue"): 2},
    )
    assert order == [U_PLAIN, SAS_PRIMARY]


def test_validate_mode_confirmation_still_outranks_industry_relevance():
    """Once there are candidate causes, confirming one is worth more than
    industry fit -- that bias is the FIRST term and must stay there."""
    confirms = _q(U_PLAIN, 33)
    confirms.root_cause_id = 77
    order = _order(
        bank=[_q(SAS_PRIMARY, 21), confirms],
        session=_session(routing_state="validate"),
        detected=(77,),
    )
    assert order == [U_PLAIN, SAS_PRIMARY]


def test_relevance_never_removes_a_question():
    """It is a preference, not a filter. Every candidate must survive it."""
    assert set(_order()) == {q.question_id for q in _BANK}


# --- degrade paths -------------------------------------------------------


def test_no_weights_still_uses_the_mapping_signal():
    """The live case for twenty-six of the thirty industries, not an edge
    case: no top_pain_point_weights, but question_industry_mapping is there."""
    order = _order(weights={})
    assert order[:2] == [SAS_PRIMARY, SAS_SUPPORTING]
    assert order[2:] == [U_STRONG, U_WEAK, U_PLAIN]   # untouched, by id


def test_no_industry_data_at_all_reproduces_the_previous_order():
    """With neither signal the term must contribute nothing -- the key
    degrades to exactly what it was before industry existed."""
    assert _order(weights={}, applicability={}) == sorted(q.question_id for q in _BANK)


#: What survives Step 1's gate once the industry cannot be established: the
#: universal bank, in plain id order. The two SaaS-owned questions are correctly
#: withheld by `_industry_gated`, not by anything in this module -- see
#: test_industry_scope_gate.
_UNIVERSAL_IN_ID_ORDER = [U_STRONG, U_WEAK, U_PLAIN]


def test_an_unknown_industry_does_not_reorder_anything():
    """The gate withholds the industry-owned pair; among what is left, the
    relevance term must contribute nothing at all."""
    assert _order(
        founder=_founder(None), session=_session(None),
    ) == _UNIVERSAL_IN_ID_ORDER


def test_a_database_failure_falls_back_to_the_default_order():
    assert _order(raises=True) == _UNIVERSAL_IN_ID_ORDER


# --- determinism ---------------------------------------------------------


def test_the_order_is_identical_on_every_request():
    first = _order()
    for _ in range(5):
        assert _order() == first


# --- the rule itself, without a database ---------------------------------


def test_ranker_grades_both_signals():
    rank = relevance_ranker(_APPLICABILITY, _PROBLEM_CODE,
                            normalise_weights(_WEIGHTS_RAW))
    assert rank(_q(SAS_PRIMARY, 21)) == PRIMARY_RANK
    assert rank(_q(SAS_SUPPORTING, 22)) == SUPPORTING_RANK
    assert rank(_q(U_STRONG, 31)) == STRONG_WEIGHT_RANK
    assert rank(_q(U_WEAK, 32)) == WEAK_WEIGHT_RANK
    assert rank(_q(U_PLAIN, 33)) == UNIVERSAL_RANK


def test_a_question_with_no_problem_code_is_universal_not_an_error():
    rank = relevance_ranker({}, {}, normalise_weights(_WEIGHTS_RAW))
    assert rank(_q(1, None)) == UNIVERSAL_RANK
    assert rank(_q(1, 999)) == UNIVERSAL_RANK


def test_the_strong_threshold_splits_the_seeded_values_two_and_two():
    """1.05 / 1.15 mild, 1.3 / 1.5 strong -- the only four values seeded, so
    the boundary never cuts through a cluster. 1.3 itself is strong."""
    weights = normalise_weights({"A-001": 1.05, "A-002": 1.15,
                                 "A-003": 1.3, "A-004": 1.5})
    codes = {1: "A-001", 2: "A-002", 3: "A-003", 4: "A-004"}
    rank = relevance_ranker({}, codes, weights)
    assert [rank(_q(0, pid)) for pid in (1, 2, 3, 4)] == [
        WEAK_WEIGHT_RANK, WEAK_WEIGHT_RANK, STRONG_WEIGHT_RANK, STRONG_WEIGHT_RANK]


def test_normalise_weights_survives_anything_the_column_might_hold():
    """The column's shape was never formalised and twenty-six rows are '{}'.
    Nothing here may raise."""
    assert normalise_weights(None) == {}
    assert normalise_weights({}) == {}
    assert normalise_weights([1, 2]) == {}
    assert normalise_weights("nonsense") == {}
    assert normalise_weights({"A-001": "1.5"}) == {"A-001": Decimal("1.5")}
    assert normalise_weights({"a-001": 1.5}) == {"A-001": Decimal("1.5")}
    assert normalise_weights({"A-001": None, "A-002": "x", "": 1.5,
                              "A-003": True, 7: 1.5}) == {}


def test_no_signal_ranks_everything_the_same():
    rank = relevance_ranker(None, None, None)
    assert {rank(_q(qid, pid)) for qid, pid in ((1, 21), (2, 31), (3, 99))} == {
        UNIVERSAL_RANK}
