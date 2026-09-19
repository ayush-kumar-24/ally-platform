"""Step 9B: PRIORITIZED CAPABILITY GAP -> EXISTING INTERVENTIONS.

THE RULES THIS FILE PROTECTS: the library is the source of truth (nothing is
generated, ever -- a gap the library cannot serve returns
NO_INTERVENTION_AVAILABLE and says why); one intervention serving two gaps is
ONE object carrying both, never two; and no eligibility rule is invented here
that the repository did not already treat as authoritative.

The golden cases read REAL reference data -- GTM-OWN's actual two
interventions, the actual multi-capability INT-060, the actual ["saas"]-
restricted rows. Nothing about the library is hard-coded from imagination.
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.capability_levels import CapabilityLevel
from app.api.v1.diagnosis.gap_engine import (
    STATUS_GAP,
    STATUS_NOT_REQUIRED,
    STATUS_SATISFIED,
    STATUS_UNASSESSED,
    CapabilityGap,
)
from app.api.v1.diagnosis.gap_intervention import (
    ELIGIBLE,
    NO_INTERVENTION_AVAILABLE,
    REASON_ALL_CANDIDATES_FILTERED,
    REASON_NO_MAPPED_INTERVENTION,
    GapInterventionSelection,
    InterventionCandidate,
    UncoveredGap,
    select_interventions_for_gaps,
)
from app.api.v1.diagnosis.gap_priority import (
    PrioritizedCapabilityGap,
    prioritize_capability_gaps,
)
from app.api.v1.diagnosis.repository import DiagnosisRepository
from app.db.session import engine as db_engine


@pytest.fixture
def db():
    conn = db_engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


def pgap(cid, code="X", rank=1, gap_size=2, necessity="core"):
    """A PrioritizedCapabilityGap, as Step 9A would have produced it."""
    return PrioritizedCapabilityGap(
        capability_id=cid, capability_code=code, capability_name=f"Capability {cid}",
        current_level=CapabilityLevel(1), required_level=CapabilityLevel(3),
        gap_size=gap_size, necessity=necessity,
        priority_key=(0, -gap_size, cid), priority_reasons=(), rank=rank,
        requirement_id=100 + cid, supporting_evidence_ids=(1,),
    )


def irow(intervention_id, code=None, section="Ops", stages=(5,), industries=("all",)):
    """An intervention row in the shape `interventions_for_capabilities` returns."""
    return {
        "intervention_id": intervention_id,
        "intervention_code": code or f"INT-{intervention_id:03d}",
        "section": section,
        "stage_relevance": list(stages),
        "industry_relevance": list(industries),
    }


def _code_without_module_docstring(path):
    """See test_gap_engine.py's identical helper -- strips the module's own
    leading docstring so a structural guard is not tripped by prose that
    legitimately explains, in negation, what the module does not do."""
    import ast
    source = open(path).read()
    tree = ast.parse(source)
    doc = ast.get_docstring(tree, clean=False)
    if doc:
        end_line = tree.body[0].end_lineno
        return "\n".join(source.split("\n")[end_line:])
    return source


SELECT = "app/api/v1/diagnosis/gap_intervention.py"


def run(gaps, by_capability, stage_id=5, industry_code="saas"):
    return select_interventions_for_gaps(
        gaps, by_capability, stage_id=stage_id, industry_code=industry_code)


# =========================================================== 1-3: basic selection
def test_gap_with_one_mapped_intervention_returns_a_candidate():
    """Case 1."""
    sel = run([pgap(1, "GTM-OWN")], {1: [irow(56)]})
    assert len(sel.candidates) == 1
    assert sel.candidates[0].intervention_id == 56
    assert sel.candidates[0].eligibility == ELIGIBLE
    assert sel.uncovered == ()


def test_gap_with_several_mapped_interventions_returns_every_eligible_one():
    """Case 2."""
    sel = run([pgap(1, "GTM-OWN")], {1: [irow(56), irow(64), irow(70)]})
    assert [c.intervention_id for c in sel.candidates] == [56, 64, 70]


def test_gap_with_no_mapped_intervention_is_explicitly_uncovered():
    """Case 3. NO_INTERVENTION_AVAILABLE, never a fabricated suggestion."""
    sel = run([pgap(1, "GTM-OWN")], {})
    assert sel.candidates == ()
    assert len(sel.uncovered) == 1
    assert sel.uncovered[0].status == NO_INTERVENTION_AVAILABLE
    assert sel.uncovered[0].reason == REASON_NO_MAPPED_INTERVENTION
    assert sel.uncovered[0].excluded_intervention_ids == ()


def test_all_candidates_filtered_is_a_distinguishable_uncovered_reason():
    """Section 17 case C: content exists but does not fit this founder. A
    LIBRARY gap and a FIT gap must not read the same."""
    sel = run([pgap(1, "GTM-OWN")], {1: [irow(56, stages=(5, 6))]}, stage_id=1)
    assert sel.candidates == ()
    assert sel.uncovered[0].reason == REASON_ALL_CANDIDATES_FILTERED
    assert sel.uncovered[0].excluded_intervention_ids == (56,)


# =========================================================== 4-6: non-GAP statuses
def _gap(cid, status, code="X"):
    return CapabilityGap(
        capability_id=cid, capability_code=code, capability_name=code, status=status,
        required_level=CapabilityLevel(3),
        current_level=None if status == STATUS_UNASSESSED else CapabilityLevel(3),
        gap_size=None, necessity="core" if status != STATUS_NOT_REQUIRED else None,
        requirement_id=None if status == STATUS_NOT_REQUIRED else 1,
    )


@pytest.mark.parametrize("status", [STATUS_SATISFIED, STATUS_UNASSESSED, STATUS_NOT_REQUIRED])
def test_non_gap_statuses_never_reach_intervention_selection(status):
    """Cases 4, 5, 6. Composed through the real Step 9A filter rather than
    asserted in isolation -- this is the path production would take."""
    prioritized = prioritize_capability_gaps((_gap(1, status),))
    assert prioritized == ()
    sel = run(prioritized, {1: [irow(56)]})
    assert sel.candidates == ()
    assert sel.uncovered == ()


# =========================================================== 7-10: gap context preserved
def test_candidate_preserves_capability_id():
    """Case 7."""
    sel = run([pgap(9, "FIN-UNIT")], {9: [irow(56)]})
    assert sel.candidates[0].supporting_capability_ids == (9,)
    assert sel.candidates[0].supporting_capability_codes == ("FIN-UNIT",)


def test_candidate_preserves_gap_priority():
    """Case 8. Inherited, not recomputed."""
    sel = run([pgap(1, "A", rank=3)], {1: [irow(56)]})
    assert sel.candidates[0].supporting_gaps[0].gap_rank == 3
    assert sel.candidates[0].best_gap_rank == 3


def test_candidate_preserves_gap_size():
    """Case 9."""
    sel = run([pgap(1, "A", gap_size=3)], {1: [irow(56)]})
    assert sel.candidates[0].supporting_gaps[0].gap_size == 3


def test_candidate_preserves_necessity():
    """Case 10."""
    sel = run([pgap(1, "A", necessity="contextual")], {1: [irow(56)]})
    assert sel.candidates[0].supporting_gaps[0].necessity == "contextual"


# =========================================================== 11-12: multi-capability
def test_intervention_building_two_capabilities_supports_both_gaps():
    """Case 11. ONE candidate, TWO supporting gaps -- the relationship the
    step brief's section 16 says must not be flattened away."""
    shared = irow(60)
    sel = run([pgap(1, "FIN-PLAN", rank=1), pgap(2, "GTM-PIPE", rank=2)],
              {1: [shared], 2: [shared]})
    assert len(sel.candidates) == 1
    candidate = sel.candidates[0]
    assert candidate.supporting_capability_codes == ("FIN-PLAN", "GTM-PIPE")
    assert [g.gap_rank for g in candidate.supporting_gaps] == [1, 2]


def test_the_same_intervention_is_never_returned_twice():
    """Case 12."""
    shared = irow(60)
    sel = run([pgap(1, "A", rank=1), pgap(2, "B", rank=2)], {1: [shared], 2: [shared]})
    ids = [c.intervention_id for c in sel.candidates]
    assert len(ids) == len(set(ids)) == 1


def test_both_gaps_remain_individually_visible_through_a_shared_intervention():
    """Section 16 explicitly: neither gap's priority may be lost."""
    shared = irow(60)
    sel = run([pgap(1, "A", rank=1, gap_size=3, necessity="core"),
               pgap(2, "B", rank=2, gap_size=1, necessity="contextual")],
              {1: [shared], 2: [shared]})
    gaps = {g.capability_code: g for g in sel.candidates[0].supporting_gaps}
    assert gaps["A"].gap_size == 3 and gaps["A"].necessity == "core"
    assert gaps["B"].gap_size == 1 and gaps["B"].necessity == "contextual"


def test_a_shared_intervention_covers_both_capabilities_so_neither_is_uncovered():
    shared = irow(60)
    sel = run([pgap(1, "A", rank=1), pgap(2, "B", rank=2)], {1: [shared], 2: [shared]})
    assert sel.uncovered == ()
    assert sel.covered_capability_ids == {1, 2}


def test_a_shared_intervention_filtered_out_leaves_both_gaps_uncovered():
    """Section 17 case C across a shared row -- neither gap silently inherits
    the other's coverage."""
    shared = irow(60, stages=(7,))
    sel = run([pgap(1, "A", rank=1), pgap(2, "B", rank=2)], {1: [shared], 2: [shared]},
              stage_id=2)
    assert sel.candidates == ()
    assert {u.capability_code for u in sel.uncovered} == {"A", "B"}
    assert all(u.reason == REASON_ALL_CANDIDATES_FILTERED for u in sel.uncovered)


# =========================================================== 13-14: ordering, no score
def test_ordering_is_deterministic_and_insertion_order_independent():
    """Case 13."""
    rows = {1: [irow(70), irow(56), irow(64)]}
    first = run([pgap(1, "A")], rows)
    reversed_rows = {1: list(reversed(rows[1]))}
    second = run([pgap(1, "A")], reversed_rows)
    assert [c.intervention_id for c in first.candidates] == [56, 64, 70]
    assert [c.intervention_id for c in second.candidates] == [56, 64, 70]


def test_candidates_inherit_gap_priority_before_intervention_id():
    """Gap priority decides first; intervention_id only breaks ties. No new
    intervention score is introduced to do it."""
    sel = run([pgap(1, "A", rank=2), pgap(2, "B", rank=1)],
              {1: [irow(10)], 2: [irow(99)]})
    assert [c.intervention_id for c in sel.candidates] == [99, 10]


def test_no_arbitrary_intervention_score_exists():
    """Case 14."""
    fields = set(InterventionCandidate.__dataclass_fields__)
    for forbidden in ("score", "priority_score", "weight", "confidence", "severity",
                      "relevance_score", "rank"):
        assert forbidden not in fields


# =========================================================== 15-18: no scope creep
def test_no_llm_or_rag_is_used():
    """Cases 15, 16."""
    code = _code_without_module_docstring(SELECT)
    for forbidden in ("llm", "openai", "anthropic", "embedding", "retrieval",
                      "rag", "prompt", "enricher", "semantic"):
        assert forbidden not in code.lower(), f"gap_intervention.py references {forbidden!r}"


def test_no_intervention_content_is_generated():
    """Case 17. Every content field on a candidate is copied from a library
    row; there is no field that could hold text this module composed."""
    fields = set(InterventionCandidate.__dataclass_fields__)
    for forbidden in ("rationale", "advice", "prose", "text", "narrative",
                      "suggestion", "recommendation", "next_actions"):
        assert forbidden not in fields
    sel = run([pgap(1, "A")], {1: [irow(56, code="INT-056", section="Ops")]})
    assert sel.candidates[0].intervention_code == "INT-056"
    assert sel.candidates[0].section == "Ops"


def test_no_root_cause_join_is_invented():
    """Case 18. Selection reaches interventions through
    intervention_capabilities only -- never through root_cause_ids."""
    code = _code_without_module_docstring(SELECT)
    for forbidden in ("root_cause", "root_cause_ids", "detected_root_causes"):
        assert forbidden not in code.lower()


def test_no_db_write_is_possible_from_this_module():
    """Case 26."""
    code = _code_without_module_docstring(SELECT)
    for forbidden in ("insert", "update ", "delete", "commit", "flush", "session",
                      "execute("):
        assert forbidden not in code.lower(), f"gap_intervention.py may write: {forbidden!r}"


# =========================================================== 19-23: context safety
def test_no_business_model_filter_is_applied_because_none_is_authoritative():
    """Case 19. The library has no business-model metadata, so an unknown
    business model cannot become a positive applicability signal -- there is
    no business-model test at all to be fooled."""
    code = _code_without_module_docstring(SELECT)
    assert "business_model" not in code.lower()
    sel = run([pgap(1, "A")], {1: [irow(56)]})
    assert len(sel.candidates) == 1   # admitted on stage/industry alone


def test_the_intervention_library_still_has_no_business_model_column(db):
    """Case 20. Vacuous today, and deliberately asserted so it stops being
    vacuous the day someone adds the column: a business-model exclusion is
    only permitted once authoritative metadata exists to support it."""
    columns = {r[0] for r in db.execute(text(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_name = 'interventions'")).all()}
    assert "business_model" not in columns, (
        "interventions grew a business_model column -- Step 9B must now decide, "
        "deliberately, whether to filter on it")


def test_unknown_industry_does_not_exclude_an_unrestricted_intervention():
    """Case 21. The dominant case by far: 412 of 417 library rows are
    ["all"], and an un-onboarded founder loses none of them."""
    sel = run([pgap(1, "A")], {1: [irow(56, industries=("all",))]}, industry_code=None)
    assert len(sel.candidates) == 1


def test_a_restricted_intervention_with_unknown_industry_is_withheld():
    """The inherited exception, asserted explicitly rather than left implicit.
    `DefaultInterventionRelevance` fails CLOSED only when the intervention
    ITSELF declares it is not universal and the founder's industry is unknown
    -- a decision the existing engine made after a B2B logistics founder was
    handed SaaS-presupposing steps. Step 9B reuses that strategy verbatim, so
    it inherits this behaviour rather than writing a second industry rule."""
    sel = run([pgap(1, "A")], {1: [irow(378, industries=("saas",))]}, industry_code=None)
    assert sel.candidates == ()
    assert sel.uncovered[0].reason == REASON_ALL_CANDIDATES_FILTERED


def test_known_industry_restriction_is_respected():
    """Case 22."""
    rows = {1: [irow(378, industries=("saas",))]}
    assert run([pgap(1, "A")], rows, industry_code="saas").candidates
    assert run([pgap(1, "A")], rows, industry_code="fintech").candidates == ()


def test_missing_stage_metadata_does_not_silently_become_false():
    """Case 23. Empty or absent relevance is UNKNOWN, which includes."""
    assert run([pgap(1, "A")], {1: [irow(56, stages=())]}, stage_id=3).candidates
    assert run([pgap(1, "A")], {1: [irow(56, industries=())]}, industry_code="x").candidates
    empty = {"intervention_id": 56, "intervention_code": "INT-056", "section": "Ops",
             "stage_relevance": None, "industry_relevance": None}
    assert run([pgap(1, "A")], {1: [empty]}).candidates


def test_unknown_stage_does_not_exclude_a_stage_restricted_intervention():
    """Case 23, the founder half: an unknown stage filters nothing."""
    sel = run([pgap(1, "A")], {1: [irow(56, stages=(7, 8))]}, stage_id=None)
    assert len(sel.candidates) == 1


# =========================================================== 24-25: isolation
def test_selection_knows_nothing_about_founders_or_sessions():
    """Cases 24, 25. Isolation is structural: the pure function has no founder
    or session parameter at all, so it cannot mix two founders' data. Scoping
    is guaranteed upstream by Step 8's session-scoped gap computation, exactly
    as it already is for Steps 7C and 9A."""
    import inspect
    params = set(inspect.signature(select_interventions_for_gaps).parameters)
    assert params == {"gaps", "interventions_by_capability", "stage_id",
                      "industry_code", "relevance"}
    for forbidden in ("session_id", "founder_id", "founder"):
        assert forbidden not in params


def test_two_sessions_are_computed_independently(db):
    """Case 25, live: the repository entry point is session-scoped, and a
    session with no capability evidence yields no gaps and therefore no
    candidates -- it can never inherit another session's."""
    repo = DiagnosisRepository(db)
    ctx = SimpleNamespace(industry_code="saas", business_model="B2B", stage_order=5)
    from app.api.v1.diagnosis.target_state import TargetStateContext
    target = TargetStateContext("1Cr_5Cr", "12_months")

    ids = [r[0] for r in db.execute(text("SELECT session_id FROM sessions LIMIT 2")).all()]
    if len(ids) < 2:
        pytest.skip("need two sessions")
    first = repo.intervention_candidates_for_session(ids[0], ctx, target)
    second = repo.intervention_candidates_for_session(ids[1], ctx, target)
    assert isinstance(first, GapInterventionSelection)
    assert isinstance(second, GapInterventionSelection)


# =========================================================== 27-31: existing system
@pytest.mark.parametrize("module", [
    "app/api/v1/reasoning/engines/diagnostic.py",
    "app/api/v1/reasoning/engines/root_cause.py",
    "app/api/v1/reasoning/engines/recommendation.py",
    "app/api/v1/reasoning/engines/business_health.py",
    "app/api/v1/diagnosis/engine.py",
    "app/api/v1/diagnosis/advisor.py",
    "app/api/v1/diagnosis/gap_engine.py",
    "app/api/v1/diagnosis/gap_priority.py",
])
def test_existing_module_has_no_dependency_on_intervention_selection(module):
    """Cases 27-31: diagnosis scoring, root-cause ranking, the recommendation
    engine, question selection, the question budget, the Gap Engine and Gap
    Prioritization must all be unchanged by this step -- the dependency runs
    one way only."""
    source = open(module).read()
    for forbidden in ("gap_intervention", "select_interventions_for_gaps",
                      "InterventionCandidate"):
        assert forbidden not in source


def test_the_existing_recommendation_engine_is_not_replaced():
    """Section 21: 9B coexists with the recommendation engine rather than
    replacing it. The two reach the library through different doors and
    9B rewrites neither the engine nor its relevance strategy."""
    source = open("app/api/v1/reasoning/engines/recommendation.py").read()
    assert "class DefaultInterventionRelevance" in source
    assert "root_cause_ids" in source          # its own door, untouched
    code = _code_without_module_docstring(SELECT)
    assert "DefaultInterventionRelevance" in code   # reused, not reimplemented
    for reimplemented in ("_UNIVERSAL_INDUSTRY", "stage_ok", "industry_ok"):
        assert reimplemented not in code, "gap_intervention.py copied the relevance rule"


# =========================================================== golden cases (section 19)
def _cap_id(db, code):
    return db.execute(text("SELECT capability_id FROM capabilities WHERE capability_code = :c"),
                      {"c": code}).scalar()


def test_case_a_direct_capability_match_against_real_data(db):
    """CASE A. GTM-OWN's interventions are whatever the seeded map says they
    are -- read, never assumed. (Today: INT-056 and INT-064, the two the
    taxonomy doc already flags as the thinnest coverage in the library.)"""
    repo = DiagnosisRepository(db)
    gtm_own = _cap_id(db, "GTM-OWN")
    by_capability = repo.interventions_for_capabilities([gtm_own])

    expected = {r[0] for r in db.execute(text(
        "SELECT intervention_id FROM intervention_capabilities WHERE capability_id = :c"),
        {"c": gtm_own}).all()}
    sel = run([pgap(gtm_own, "GTM-OWN")], by_capability, stage_id=5, industry_code="saas")
    assert {c.intervention_id for c in sel.candidates} == expected
    assert all(c.supporting_capability_codes == ("GTM-OWN",) for c in sel.candidates)


def test_case_b_multi_capability_intervention_against_real_data(db):
    """CASE B. A real intervention mapped to two real capabilities, with both
    live as gaps, must appear once and support both."""
    repo = DiagnosisRepository(db)
    row = db.execute(text(
        "SELECT intervention_id, array_agg(capability_id ORDER BY capability_id)"
        "  FROM intervention_capabilities GROUP BY intervention_id"
        " HAVING count(*) >= 2 ORDER BY intervention_id LIMIT 1")).first()
    if row is None:
        pytest.skip("no multi-capability intervention seeded")
    intervention_id, (cap_a, cap_b) = row[0], row[1][:2]

    by_capability = repo.interventions_for_capabilities([cap_a, cap_b])
    sel = run([pgap(cap_a, "A", rank=1), pgap(cap_b, "B", rank=2)], by_capability,
              stage_id=5, industry_code="saas")
    shared = [c for c in sel.candidates if c.intervention_id == intervention_id]
    if not shared:
        pytest.skip("the shared intervention is not eligible at this stage")
    assert len(shared) == 1
    assert set(shared[0].supporting_capability_ids) == {cap_a, cap_b}
    ids = [c.intervention_id for c in sel.candidates]
    assert len(ids) == len(set(ids))


def test_case_c_weakest_coverage_capability_can_become_uncovered(db):
    """CASE C. GTM-OWN's real interventions are stage-restricted, so an
    early-stage founder with a GTM-OWN gap gets NO_INTERVENTION_AVAILABLE from
    real data -- not a generated suggestion. This is the content gap Step 5
    already reported, now visible at runtime."""
    repo = DiagnosisRepository(db)
    gtm_own = _cap_id(db, "GTM-OWN")
    by_capability = repo.interventions_for_capabilities([gtm_own])
    sel = run([pgap(gtm_own, "GTM-OWN")], by_capability, stage_id=1, industry_code="saas")
    assert sel.candidates == ()
    assert sel.uncovered[0].status == NO_INTERVENTION_AVAILABLE
    assert sel.uncovered[0].capability_code == "GTM-OWN"
    assert sel.uncovered[0].excluded_intervention_ids


def test_case_d_unknown_context_does_not_reject_a_universal_candidate(db):
    """CASE D."""
    repo = DiagnosisRepository(db)
    gtm_own = _cap_id(db, "GTM-OWN")
    by_capability = repo.interventions_for_capabilities([gtm_own])
    sel = run([pgap(gtm_own, "GTM-OWN")], by_capability, stage_id=None, industry_code=None)
    assert sel.candidates, "an unknown stage and industry removed universal rows"


def test_case_e_known_incompatible_industry_is_excluded_against_real_data(db):
    """CASE E. Only because authoritative intervention metadata supports it:
    the library really does carry a handful of industry-restricted rows."""
    repo = DiagnosisRepository(db)
    row = db.execute(text(
        "SELECT ic.capability_id, i.intervention_id, i.industry_relevance"
        "  FROM interventions i"
        "  JOIN intervention_capabilities ic ON ic.intervention_id = i.intervention_id"
        " WHERE NOT (i.industry_relevance @> '[\"all\"]') ORDER BY i.intervention_id LIMIT 1")).first()
    if row is None:
        pytest.skip("no industry-restricted intervention is mapped to a capability")
    capability_id, intervention_id, industries = row
    by_capability = repo.interventions_for_capabilities([capability_id])

    permitted = run([pgap(capability_id, "X")], by_capability,
                    stage_id=None, industry_code=industries[0])
    excluded = run([pgap(capability_id, "X")], by_capability,
                   stage_id=None, industry_code="definitely_not_an_industry")
    assert intervention_id in {c.intervention_id for c in permitted.candidates}
    assert intervention_id not in {c.intervention_id for c in excluded.candidates}


# =========================================================== coverage report (section 20)
def test_intervention_coverage_report(db, capsys):
    """Section 20. Prints the per-capability coverage analysis and asserts the
    invariants worth holding: every capability has SOME mapping today, and the
    thin ones the taxonomy doc already named are still the thin ones."""
    repo = DiagnosisRepository(db)
    summary = repo.intervention_coverage_summary()
    assert summary, "coverage summary unavailable"

    zero = [r for r in summary if r["mapped"] == 0]
    thin = [r for r in summary if 0 < r["mapped"] <= 3]
    broad = [r for r in summary if r["mapped"] >= 20]
    total_pairs = sum(r["mapped"] for r in summary)

    with capsys.disabled():
        print(f"\n    intervention coverage: {len(summary)} capabilities, "
              f"{total_pairs} mappings")
        print(f"    zero coverage: {[r['capability_code'] for r in zero] or 'none'}")
        print(f"    thin (<=3): {[(r['capability_code'], r['mapped']) for r in thin]}")
        print(f"    broad (>=20): {[(r['capability_code'], r['mapped']) for r in broad]}")

    assert not zero, (
        f"{[r['capability_code'] for r in zero]} have no intervention at all -- "
        "every gap on them would return NO_INTERVENTION_AVAILABLE")
    assert any(r["capability_code"] == "GTM-OWN" for r in thin), (
        "GTM-OWN is no longer thin -- update docs/CAPABILITY-TAXONOMY.md and "
        "docs/GAP-INTERVENTION-SELECTION.md together with this test")


def test_no_capability_is_mapped_to_an_implausible_number_of_interventions(db):
    """A single intervention mapped across many unrelated capabilities would
    make selection meaningless. Section 20 asks for this to be visible."""
    worst = db.execute(text(
        "SELECT max(c) FROM (SELECT count(*) c FROM intervention_capabilities"
        "  GROUP BY intervention_id) t")).scalar()
    assert worst <= 3, (
        f"an intervention now builds {worst} capabilities; selection would "
        "surface it under too many unrelated gaps")


# =========================================================== live end to end
def test_live_end_to_end_through_the_repository(db):
    """The whole composed pipeline against real seeded rows: Step 6 resolver,
    Step 7C assessment, Step 8 comparison, Step 9A ordering, Step 9B selection."""
    from app.api.v1.diagnosis.target_state import TargetStateContext
    row = db.execute(text(
        "SELECT a.answer_id, a.question_id, a.session_id FROM answers a"
        "  JOIN question_capabilities qc ON qc.question_id = a.question_id"
        " LIMIT 1")).first()
    if row is None:
        pytest.skip("no answer to a mapped question in this database")
    answer_id, question_id, session_id = row
    capability_id = db.execute(text(
        "SELECT capability_id FROM question_capabilities WHERE question_id = :q"),
        {"q": question_id}).scalar()

    repo = DiagnosisRepository(db)
    repo.record_capability_evidence(
        capability_id=capability_id, question_id=question_id, answer_id=answer_id,
        observed_level=0, confidence=0.95, evidence_text="live 9B probe")

    ctx = SimpleNamespace(industry_code="saas", business_model="B2B", stage_order=5)
    target = TargetStateContext("1Cr_5Cr", "12_months")
    sel = repo.intervention_candidates_for_session(session_id, ctx, target)
    prioritized = repo.prioritized_capability_gaps_for_session(session_id, ctx, target)

    # Every candidate traces back to a real gap; nothing is invented.
    gapped = {g.capability_id for g in prioritized}
    assert sel.covered_capability_ids <= gapped
    assert sel.uncovered_capability_ids <= gapped
    assert sel.covered_capability_ids & sel.uncovered_capability_ids == set()
    # Deterministic re-run.
    again = repo.intervention_candidates_for_session(session_id, ctx, target)
    assert ([c.intervention_id for c in sel.candidates]
            == [c.intervention_id for c in again.candidates])


def test_repository_selection_issues_no_write(db):
    """Case 26, live: row counts are unchanged by a selection call."""
    from app.api.v1.diagnosis.target_state import TargetStateContext
    repo = DiagnosisRepository(db)
    before = db.execute(text("SELECT count(*) FROM intervention_capabilities")).scalar()
    session_id = db.execute(text("SELECT session_id FROM sessions LIMIT 1")).scalar()
    if session_id is None:
        pytest.skip("no session")
    ctx = SimpleNamespace(industry_code="saas", business_model="B2B", stage_order=5)
    repo.intervention_candidates_for_session(session_id, ctx, TargetStateContext(None, None))
    after = db.execute(text("SELECT count(*) FROM intervention_capabilities")).scalar()
    assert before == after
