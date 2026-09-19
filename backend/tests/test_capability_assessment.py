"""Step 7C: CAPABILITY EVIDENCE -> CURRENT CAPABILITY ASSESSMENT.

THE TWO INVARIANTS THIS FILE PROTECTS ABOVE ALL OTHERS:

  UNASSESSED != ABSENT.  A capability with zero (or zero CONFIDENT) evidence
  gets `current_level is None`, never `CapabilityLevel.ABSENT`. Every "no
  evidence" test asserts `is_assessed is False`, not `current_level == 0`.

  The lowest confident reading is not a statistic. `assess_capability` is
  proved against the step brief's OWN worked examples verbatim (Level 3/2/3 ->
  2; Level 3 + a sub-threshold Level 0 -> 3, unmoved), and separately against
  order-independence and immutability of the underlying evidence.

Everything here is pure-function testing plus a thin repository composition --
there is no new table, so there is nothing to migrate, round-trip, or leak
across a transaction boundary the way earlier steps' schemas needed to.
"""

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.capability_assessment import (
    CapabilityAssessment,
    assess_capabilities,
    assess_capability,
)
from app.api.v1.diagnosis.capability_evidence import MIN_CONFIDENCE
from app.api.v1.diagnosis.capability_levels import UNASSESSED, CapabilityLevel, is_assessed
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


def row(evidence_id, level, confidence, capability_id=1, capability_code="X"):
    return {"evidence_id": evidence_id, "capability_id": capability_id,
            "capability_code": capability_code, "observed_level": level,
            "confidence": confidence}


# =========================================================== 1-2: UNASSESSED
def test_no_evidence_is_unassessed_not_level_0():
    """Case 1. The single most important assertion in this file."""
    a = assess_capability(1, "X", [])
    assert a.is_assessed is False
    assert a.status == UNASSESSED
    assert a.current_level is None
    assert a.current_level != 0                      # explicit: None, not 0


def test_not_applicable_produces_no_evidence_therefore_unassessed(db):
    """Case 2, end to end: N/A -> no capability_evidence row (Step 7B's own
    invariant) -> assess_capabilities sees nothing -> UNASSESSED.

    Constructed exactly like Step 7B's own N/A pipeline test: the gate lives in
    `_extract_capability_evidence`, before the extractor is ever called, so
    there is no row to aggregate regardless of what the answer text said.
    """
    from app.api.v1.diagnosis.service import DiagnosisService
    from app.models.enums import ScoreLabel
    import asyncio

    row_ = db.execute(text(
        "SELECT a.answer_id, a.question_id, a.session_id FROM answers a"
        "  JOIN question_capabilities qc ON qc.question_id = a.question_id"
        " LIMIT 1")).first()
    if row_ is None:
        pytest.skip("no answer to a mapped question in this database")
    answer_id, question_id, session_id = row_

    class _NeverCalled:
        async def extract(self, **kw):
            raise AssertionError("N/A must never reach the extractor")

    na_answer = SimpleNamespace(
        answer_id=answer_id, question_id=question_id,
        score_label=ScoreLabel.NOT_APPLICABLE.value, answer_text="not applicable to us")
    question = SimpleNamespace(question_id=question_id, question_text="q")
    svc = DiagnosisService(db, capability_evidence_extractor=_NeverCalled())
    asyncio.run(svc._extract_capability_evidence(
        SimpleNamespace(session_id=session_id), na_answer, question))

    repo = DiagnosisRepository(db)
    assessments = repo.current_capability_assessments(session_id)
    mapped_capability_ids = {a.capability_id for a in assessments}
    capability_id = db.execute(text(
        "SELECT capability_id FROM question_capabilities WHERE question_id = :q"),
        {"q": question_id}).scalar()
    assert capability_id not in mapped_capability_ids, (
        "N/A must not produce even an UNASSESSED-with-excluded-evidence row -- "
        "it must produce NOTHING"
    )


# =========================================================== 3-6: the levels
def test_explicit_level_0_evidence_yields_level_0():
    """Case 3. Level 0 is a stored, confident, positive claim -- trusted as-is."""
    a = assess_capability(1, "X", [row(1, 0, 0.9)])
    assert a.is_assessed is True
    assert a.current_level == CapabilityLevel.ABSENT
    assert a.supporting_evidence_ids == (1,)


def test_level_1_evidence_yields_level_1():
    a = assess_capability(1, "X", [row(1, 1, 0.85)])
    assert a.current_level == CapabilityLevel.PERSONAL


def test_level_2_evidence_yields_level_2():
    a = assess_capability(1, "X", [row(1, 2, 0.85)])
    assert a.current_level == CapabilityLevel.DOCUMENTED


def test_level_3_evidence_yields_level_3():
    a = assess_capability(1, "X", [row(1, 3, 0.85)])
    assert a.current_level == CapabilityLevel.OWNED


# =========================================================== 7-10: aggregation
def test_multiple_same_level_observations_agree():
    """Case 7."""
    a = assess_capability(1, "X", [row(1, 1, 0.8), row(2, 1, 0.9), row(3, 1, 0.75)])
    assert a.current_level == CapabilityLevel.PERSONAL
    assert a.considered_evidence_ids == (1, 2, 3)
    assert a.supporting_evidence_ids == (1, 2, 3)


def test_the_briefs_own_worked_example_level_3_2_3_resolves_to_2():
    """Case 8. Verbatim from section 4 of the step brief."""
    a = assess_capability(1, "X", [row(1, 3, 0.95), row(2, 2, 0.90), row(3, 3, 0.92)])
    assert a.current_level == CapabilityLevel.DOCUMENTED
    assert a.supporting_evidence_ids == (2,)
    assert a.considered_evidence_ids == (1, 2, 3)      # nothing silently dropped


def test_level_2_plus_level_1_sufficiently_confident_resolves_to_1():
    """Case 9."""
    a = assess_capability(1, "X", [row(1, 2, 0.9), row(2, 1, 0.85)])
    assert a.current_level == CapabilityLevel.PERSONAL


def test_a_weak_contradictory_observation_below_threshold_does_not_downgrade():
    """Case 10. Verbatim from section 4: Level 3 @ .95, Level 0 @ .31 -> 3."""
    a = assess_capability(1, "X", [row(1, 3, 0.95), row(2, 0, 0.31)])
    assert a.current_level == CapabilityLevel.OWNED
    assert a.excluded_evidence_ids == (2,)
    assert 2 not in a.considered_evidence_ids          # never entered the MIN


def test_the_confidence_floor_is_exactly_step_7bs_own_constant():
    """The threshold is Step 7B's, reused -- not a second number invented here."""
    assert MIN_CONFIDENCE == 0.6
    at_floor = assess_capability(1, "X", [row(1, 2, MIN_CONFIDENCE)])
    just_below = assess_capability(1, "X", [row(1, 2, MIN_CONFIDENCE - 0.01)])
    assert at_floor.is_assessed is True                 # inclusive
    assert just_below.is_assessed is False


# =========================================================== 11-13: determinism/traceability
def test_insertion_order_does_not_change_the_assessment():
    """Case 11."""
    rows = [row(1, 3, 0.95), row(2, 2, 0.90), row(3, 3, 0.92)]
    forward = assess_capability(1, "X", rows)
    backward = assess_capability(1, "X", list(reversed(rows)))
    shuffled = assess_capability(1, "X", [rows[1], rows[2], rows[0]])
    assert forward == backward == shuffled


def test_evidence_rows_are_never_mutated(db):
    """Case 12. `assess_capability` reads dict-like rows; it must not write
    back to them, and the underlying capability_evidence table has no UPDATE
    path anywhere in the codebase (Step 7B's own repository only INSERTs)."""
    import subprocess
    updates = subprocess.run(
        ["grep", "-rn", "UPDATE capability_evidence", "app/"],
        capture_output=True, text=True).stdout
    assert updates == "", f"something writes to stored evidence: {updates}"
    original = row(1, 2, 0.9)
    snapshot = dict(original)
    assess_capability(1, "X", [original])
    assert original == snapshot


def test_assessment_traces_to_the_supporting_evidence_and_onward_to_the_answer(db):
    """Case 13. Assessment -> evidence_id -> answer_id -> question_id, in one
    hop plus one lookup -- not a chain of joins through mutable state."""
    repo = DiagnosisRepository(db)
    answer_row = db.execute(text(
        "SELECT a.answer_id, a.question_id, a.session_id FROM answers a"
        "  JOIN question_capabilities qc ON qc.question_id = a.question_id"
        " WHERE a.score_label = 'green' LIMIT 1")).first()
    if answer_row is None:
        pytest.skip("no green answer to a mapped question in this database")
    answer_id, question_id, session_id = answer_row
    capability_id = db.execute(text(
        "SELECT capability_id FROM question_capabilities WHERE question_id = :q"),
        {"q": question_id}).scalar()

    repo.record_capability_evidence(
        capability_id=capability_id, question_id=question_id, answer_id=answer_id,
        observed_level=1, confidence=0.85, evidence_text="traceability probe")

    assessments = repo.current_capability_assessments(session_id)
    match = next(a for a in assessments if a.capability_id == capability_id)
    assert match.current_level == CapabilityLevel.PERSONAL
    assert len(match.supporting_evidence_ids) == 1
    evidence_id = match.supporting_evidence_ids[0]

    traced = db.execute(text(
        "SELECT answer_id, question_id FROM capability_evidence WHERE evidence_id = :e"),
        {"e": evidence_id}).first()
    assert traced == (answer_id, question_id)


# =========================================================== 14-15: cannot fabricate
def test_an_unmapped_question_cannot_produce_an_assessment(db):
    """Case 14. There is no path from an unmapped question to evidence at all
    (Step 7B's own gate), so there is nothing here to aggregate -- restated at
    this layer rather than assumed."""
    row_ = db.execute(text(
        "SELECT a.answer_id FROM answers a"
        "  LEFT JOIN question_capabilities qc ON qc.question_id = a.question_id"
        " WHERE qc.question_id IS NULL LIMIT 1")).first()
    if row_ is None:
        pytest.skip("no answer to an unmapped question in this database")
    (answer_id,) = row_
    count = db.execute(text(
        "SELECT count(*) FROM capability_evidence WHERE answer_id = :a"),
        {"a": answer_id}).scalar()
    assert count == 0


def test_an_unknown_capability_cannot_produce_an_assessment(db):
    """Case 15. The FK on capability_id already refuses this at write time
    (Step 7B); confirmed here rather than assumed."""
    answer_id = db.execute(text("SELECT answer_id FROM answers LIMIT 1")).scalar()
    question_id = db.execute(text("SELECT question_id FROM questions LIMIT 1")).scalar()
    with pytest.raises(Exception):
        db.execute(text(
            "INSERT INTO capability_evidence"
            " (capability_id, question_id, answer_id, observed_level, confidence,"
            "  evidence_text) VALUES (999999, :q, :a, 2, 0.9, 'x')"),
            {"q": question_id, "a": answer_id})
        db.flush()


# =========================================================== 16-17: isolation
def test_assessment_for_one_founder_does_not_leak_into_another(db):
    """Case 16. Evidence is joined to a session's own answers only."""
    founders = db.execute(text(
        "SELECT DISTINCT founder_id FROM answers ORDER BY founder_id LIMIT 2")).all()
    if len(founders) < 2:
        pytest.skip("need two distinct founders with answers")
    (f1,), (f2,) = founders
    session1 = db.execute(text(
        "SELECT session_id FROM answers WHERE founder_id = :f LIMIT 1"), {"f": f1}).scalar()
    session2 = db.execute(text(
        "SELECT session_id FROM answers WHERE founder_id = :f LIMIT 1"), {"f": f2}).scalar()

    repo = DiagnosisRepository(db)
    a1 = db.execute(text(
        "SELECT a.answer_id, a.question_id FROM answers a"
        "  JOIN question_capabilities qc ON qc.question_id = a.question_id"
        " WHERE a.session_id = :s LIMIT 1"), {"s": session1}).first()
    if a1 is None:
        pytest.skip("founder 1's session has no mapped-question answer")
    capability_id = db.execute(text(
        "SELECT capability_id FROM question_capabilities WHERE question_id = :q"),
        {"q": a1[1]}).scalar()
    repo.record_capability_evidence(
        capability_id=capability_id, question_id=a1[1], answer_id=a1[0],
        observed_level=3, confidence=0.9, evidence_text="founder 1 only")

    leaked = [a for a in repo.current_capability_assessments(session2)
              if a.capability_id == capability_id]
    assert leaked == [], "founder 2's assessment must not see founder 1's evidence"


def test_assessment_is_scoped_to_one_session_at_a_time(db):
    """Case 17. `current_capability_assessments` takes a session_id and reads
    only that session's answers -- this is the repository's chosen semantics
    (session-scoped `current state`, matching how the rest of the diagnosis
    pipeline -- confidence, root-cause detection -- is already session-scoped),
    not founder-lifetime aggregation."""
    sessions = db.execute(text(
        "SELECT DISTINCT session_id FROM answers ORDER BY session_id LIMIT 2")).all()
    if len(sessions) < 2:
        pytest.skip("need two distinct sessions")
    (s1,), (s2,) = sessions
    repo = DiagnosisRepository(db)
    a1 = db.execute(text(
        "SELECT a.answer_id, a.question_id FROM answers a"
        "  JOIN question_capabilities qc ON qc.question_id = a.question_id"
        " WHERE a.session_id = :s LIMIT 1"), {"s": s1}).first()
    if a1 is None:
        pytest.skip("session 1 has no mapped-question answer")
    capability_id = db.execute(text(
        "SELECT capability_id FROM question_capabilities WHERE question_id = :q"),
        {"q": a1[1]}).scalar()
    repo.record_capability_evidence(
        capability_id=capability_id, question_id=a1[1], answer_id=a1[0],
        observed_level=3, confidence=0.9, evidence_text="session 1 only")

    leaked = [a for a in repo.current_capability_assessments(s2) if a.capability_id == capability_id]
    assert leaked == []


# =========================================================== 18-23: no regressions
@pytest.mark.parametrize("module,forbidden", [
    ("app/api/v1/reasoning/engines/diagnostic.py", "capability_assessment"),
    ("app/api/v1/reasoning/engines/root_cause.py", "capability"),
    ("app/api/v1/diagnosis/engine.py", "capability_assessment"),
    ("app/api/v1/diagnosis/advisor.py", "capability_assessment"),
    ("app/api/v1/diagnosis/target_state.py", "capability_assessment"),
    ("app/api/v1/reasoning/engines/recommendation.py", "capability_assessment"),
])
def test_existing_module_has_no_dependency_on_the_assessment(module, forbidden):
    """Cases 18-23, structurally. Diagnosis scoring, root-cause ranking,
    question selection, the budget, target-state requirements and
    recommendations must not have grown a dependency on a module that exists
    to be read by something LATER (Step 8+), not by anything that exists
    today."""
    source = open(module).read()
    assert forbidden not in source, f"{module} references {forbidden!r}"


def test_no_gap_is_generated_by_this_step(db):
    """Case 24. Structural: CapabilityAssessment has no gap-shaped field, and
    nothing calls it alongside capability_requirements anywhere in app/."""
    fields = set(CapabilityAssessment.__dataclass_fields__)
    for forbidden in ("gap", "required_level", "severity", "is_gap", "deficit"):
        assert forbidden not in fields
    import subprocess
    # An IMPORT, not a docstring mention -- the module's own comment explains
    # ITS relationship to target_state.py in prose, which is documentation,
    # not a dependency.
    cross_reference = subprocess.run(
        ["grep", "-nE", "^(from|import) app.api.v1.diagnosis.target_state",
         "app/api/v1/diagnosis/capability_assessment.py"],
        capture_output=True, text=True).stdout
    assert cross_reference == "", (
        f"the assessment module must not import target-state resolution yet: {cross_reference}"
    )


# =========================================================== golden case
def test_golden_gtm_own_founder_dependent_sales(db):
    """Section 16. GTM-OWN, the capability Step 7A identified as thin (4
    mapped questions total). Uses the REAL question -> capability mapping from
    Step 7A's own migration (questions 969-972 -> GTM-OWN) -- not invented --
    with three constructed observations matching the step brief's own worked
    example (Level 3 @ .95, Level 2 @ .90, Level 3 @ .92 -> Level 2), attached
    to REAL rows created in this rolled-back transaction because no founder in
    this database has answered these specific questions yet (capability
    evidence extraction is off by default and has never run against real
    traffic -- see Step 7B).
    """
    gtm_own_id = db.execute(text(
        "SELECT capability_id FROM capabilities WHERE capability_code = 'GTM-OWN'")).scalar()
    assert gtm_own_id is not None

    mapped_questions = [q for (q,) in db.execute(text(
        "SELECT question_id FROM question_capabilities WHERE capability_id = :c"
        " ORDER BY question_id"), {"c": gtm_own_id}).all()]
    assert set(mapped_questions) >= {969, 970, 971}, (
        "the golden scenario's premise -- these questions map to GTM-OWN -- no "
        "longer holds against the live curation"
    )

    founder_id = db.execute(text("SELECT founder_id FROM founders LIMIT 1")).scalar()
    marker = uuid.uuid4().hex[:8]
    session_id = db.execute(text(
        "INSERT INTO sessions (founder_id, status) VALUES (:f, 'in_progress')"
        " RETURNING session_id"), {"f": founder_id}).scalar()

    answer_ids = []
    for qid in (969, 970, 971):
        aid = db.execute(text(
            "INSERT INTO answers (session_id, founder_id, question_id, answer_text,"
            "  score_label) VALUES (:s, :f, :q, :t, 'amber') RETURNING answer_id"),
            {"s": session_id, "f": founder_id, "q": qid,
             "t": f"golden scenario answer {marker}"}).scalar()
        answer_ids.append(aid)
    db.flush()

    repo = DiagnosisRepository(db)
    # The brief's own worked example, attached to real (answer, question) pairs.
    for answer_id, qid, level, confidence in zip(
        answer_ids, (969, 970, 971), (3, 2, 3), (0.95, 0.90, 0.92)
    ):
        repo.record_capability_evidence(
            capability_id=gtm_own_id, question_id=qid, answer_id=answer_id,
            observed_level=level, confidence=confidence,
            evidence_text=f"golden observation for question {qid}")

    assessments = repo.current_capability_assessments(session_id)
    gtm_own = next(a for a in assessments if a.capability_id == gtm_own_id)

    assert gtm_own.current_level == CapabilityLevel.DOCUMENTED  # min(3, 2, 3) = 2
    assert len(gtm_own.supporting_evidence_ids) == 1
    assert len(gtm_own.considered_evidence_ids) == 3

    # The exact evidence row supporting the result, traced back to its answer.
    supporting_answer = db.execute(text(
        "SELECT answer_id FROM capability_evidence WHERE evidence_id = :e"),
        {"e": gtm_own.supporting_evidence_ids[0]}).scalar()
    assert supporting_answer == answer_ids[1]          # the Level-2 @ .90 answer
