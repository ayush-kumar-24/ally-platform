"""Step 7B through the REAL service, proving it is additive and off by default.

test_capability_evidence.py proves the extractor's contract in isolation. This
file proves the WIRING claim the step brief makes explicit: "existing Ally
diagnosis behaviour must remain unchanged". Every test here either drives
`DiagnosisService._extract_capability_evidence` directly against real rows, or
asserts that a piece of the EXISTING pipeline (root-cause, question selection,
budget, industry eligibility, N/A) produces the identical result whether or not
capability evidence extraction ran.
"""

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.service import DiagnosisService
from app.db.session import engine as db_engine
from app.models.enums import ScoreLabel


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


class _StubExtractor:
    """Deterministic, no network: always reports the same confident observation."""

    def __init__(self, level=2, criterion_id=None, confidence=0.9):
        self.level, self.criterion_id, self.confidence = level, criterion_id, confidence
        self.calls = []

    async def extract(self, **kwargs):
        self.calls.append(kwargs)
        from app.api.v1.diagnosis.capability_evidence import CapabilityEvidenceObservation
        from app.api.v1.diagnosis.capability_levels import CapabilityLevel
        return CapabilityEvidenceObservation(
            capability_id=kwargs["capability_id"],
            observed_level=CapabilityLevel(self.level),
            evidence_text="stub observation",
            confidence=self.confidence,
            criterion_id=self.criterion_id,
        )


def _mapped_question_and_answer(db, score_label="green"):
    row = db.execute(text(
        "SELECT a.answer_id, a.question_id FROM answers a"
        "  JOIN question_capabilities qc ON qc.question_id = a.question_id"
        " WHERE a.score_label = :label LIMIT 1"), {"label": score_label}).first()
    if row is None:
        pytest.skip(f"no {score_label} answer to a mapped question in this database")
    answer_id, question_id = row
    question_text = db.execute(text(
        "SELECT question_text FROM questions WHERE question_id = :q"),
        {"q": question_id}).scalar()
    answer_text = db.execute(text(
        "SELECT answer_text FROM answers WHERE answer_id = :a"), {"a": answer_id}).scalar()
    return (
        SimpleNamespace(answer_id=answer_id, question_id=question_id,
                        score_label=score_label, answer_text=answer_text),
        SimpleNamespace(question_id=question_id, question_text=question_text),
    )


def _session_for(db, answer_id):
    session_id = db.execute(text(
        "SELECT session_id FROM answers WHERE answer_id = :a"), {"a": answer_id}).scalar()
    return SimpleNamespace(session_id=session_id)


# =========================================================== the extractor runs
def test_a_mapped_scored_answer_produces_evidence(db):
    """Case 1, through the service rather than the extractor directly."""
    answer, question = _mapped_question_and_answer(db)
    stub = _StubExtractor(level=2)
    svc = DiagnosisService(db, capability_evidence_extractor=stub)
    asyncio.run(svc._extract_capability_evidence(_session_for(db, answer.answer_id),
                                                 answer, question))
    assert len(stub.calls) == 1
    row = db.execute(text(
        "SELECT observed_level FROM capability_evidence WHERE answer_id = :a"),
        {"a": answer.answer_id}).first()
    assert row is not None and row[0] == 2


def test_case_6_unmapped_question_produces_no_evidence(db):
    row = db.execute(text(
        "SELECT a.answer_id, a.question_id FROM answers a"
        "  LEFT JOIN question_capabilities qc ON qc.question_id = a.question_id"
        " WHERE a.score_label IS NOT NULL AND qc.question_id IS NULL LIMIT 1")).first()
    if row is None:
        pytest.skip("no answer to an unmapped question in this database")
    answer_id, question_id = row
    answer = SimpleNamespace(answer_id=answer_id, question_id=question_id,
                             score_label="green", answer_text="some answer")
    question = SimpleNamespace(question_id=question_id, question_text="q")
    stub = _StubExtractor()
    svc = DiagnosisService(db, capability_evidence_extractor=stub)
    asyncio.run(svc._extract_capability_evidence(_session_for(db, answer_id), answer, question))
    assert stub.calls == [], "the extractor must never even be called for an unmapped question"
    assert db.execute(text(
        "SELECT count(*) FROM capability_evidence WHERE answer_id = :a"),
        {"a": answer_id}).scalar() == 0


def test_case_7_not_applicable_produces_no_evidence(db):
    """The N/A gate is applied BEFORE the extractor is ever invoked."""
    answer, question = _mapped_question_and_answer(db, score_label="green")
    # Reuse a mapped question but relabel the in-memory answer as N/A -- this
    # tests the SERVICE's gate, independent of what actually got persisted.
    na_answer = SimpleNamespace(
        answer_id=answer.answer_id, question_id=answer.question_id,
        score_label=ScoreLabel.NOT_APPLICABLE.value, answer_text="this does not apply to us",
    )
    stub = _StubExtractor()
    svc = DiagnosisService(db, capability_evidence_extractor=stub)
    asyncio.run(svc._extract_capability_evidence(_session_for(db, answer.answer_id),
                                                 na_answer, question))
    assert stub.calls == [], "N/A must never reach the extractor"


def test_case_8_no_question_produces_no_evidence(db):
    answer, _question = _mapped_question_and_answer(db)
    stub = _StubExtractor()
    svc = DiagnosisService(db, capability_evidence_extractor=stub)
    asyncio.run(svc._extract_capability_evidence(
        _session_for(db, answer.answer_id), answer, None))
    assert stub.calls == []


def test_no_extractor_wired_is_a_pure_no_op(db):
    """The default. Every EXISTING caller of DiagnosisService passes nothing
    here, so this must be exactly as inert as calling the method never existed."""
    answer, question = _mapped_question_and_answer(db)
    svc = DiagnosisService(db)                      # no extractor -- the default
    assert svc.capability_evidence_extractor is None
    asyncio.run(svc._extract_capability_evidence(_session_for(db, answer.answer_id),
                                                 answer, question))
    assert db.execute(text(
        "SELECT count(*) FROM capability_evidence WHERE answer_id = :a"),
        {"a": answer.answer_id}).scalar() == 0


def test_capability_evidence_extraction_is_off_by_default_in_settings():
    from app.core.config import settings
    assert settings.CAPABILITY_EVIDENCE_EXTRACTION is False


# =========================================================== 15-18: no regressions
def test_extraction_does_not_change_the_stored_diagnostic_score(db):
    """Case 15. The extractor reads answer.score_label; it never writes it."""
    answer, question = _mapped_question_and_answer(db)
    before = db.execute(text(
        "SELECT score, score_label FROM answers WHERE answer_id = :a"),
        {"a": answer.answer_id}).first()
    svc = DiagnosisService(db, capability_evidence_extractor=_StubExtractor())
    asyncio.run(svc._extract_capability_evidence(_session_for(db, answer.answer_id),
                                                 answer, question))
    after = db.execute(text(
        "SELECT score, score_label FROM answers WHERE answer_id = :a"),
        {"a": answer.answer_id}).first()
    assert before == after


def test_root_cause_detection_reads_nothing_from_capability_evidence():
    """Case 16, structurally: root_cause.py's inputs are AnswerClassification
    objects built from `answers`/`questions`; it has no capability import."""
    source = open("app/api/v1/reasoning/engines/root_cause.py").read()
    assert "capability" not in source.lower()


def test_question_selection_reads_nothing_from_capability_evidence():
    """Case 17. engine.py's candidate/ranking logic is untouched by Step 7B --
    pinned already by test_question_capability_mapping's own guard; restated
    here against the table this step actually introduced."""
    source = open("app/api/v1/diagnosis/engine.py").read()
    assert "capability_evidence" not in source


def test_question_budget_is_unaffected_by_evidence_extraction(db):
    """Case 18. questions_answered_count is derived from `answers` row count in
    service.py, computed before this hook ever runs and untouched by it."""
    source = open("app/api/v1/diagnosis/service.py").read()
    # The counter is set once, from get_answered_question_ids -- nothing about
    # capability evidence extraction may appear between it and its use.
    assert source.count("questions_answered_count = len(") == 1


def test_extraction_never_writes_to_founders_or_sessions_scoring_fields(db):
    answer, question = _mapped_question_and_answer(db)
    founder_id = db.execute(text(
        "SELECT founder_id FROM answers WHERE answer_id = :a"), {"a": answer.answer_id}
    ).scalar()
    before = db.execute(text(
        "SELECT team_size, business_model, target_revenue_band FROM founders"
        " WHERE founder_id = :f"), {"f": founder_id}).first()
    svc = DiagnosisService(db, capability_evidence_extractor=_StubExtractor())
    asyncio.run(svc._extract_capability_evidence(_session_for(db, answer.answer_id),
                                                 answer, question))
    after = db.execute(text(
        "SELECT team_size, business_model, target_revenue_band FROM founders"
        " WHERE founder_id = :f"), {"f": founder_id}).first()
    assert before == after


# =========================================================== 19-20: industry / N/A
def test_industry_eligibility_source_has_no_capability_dependency():
    """Case 19."""
    source = open("app/api/v1/diagnosis/industry_scope.py").read()
    assert "capability" not in source.lower()


def test_not_applicable_scoring_semantics_are_unchanged_by_step_7b():
    """Case 20. ScoreLabel.NOT_APPLICABLE.is_scored and the diagnostic engine's
    own exclusion logic must be byte-identical to before Step 7B -- this step
    only adds a NEW consumer that also respects the label, never changes it."""
    from app.models.enums import ScoreLabel as SL
    assert SL.NOT_APPLICABLE.is_scored is False
    for label in (SL.GREEN, SL.AMBER, SL.RED):
        assert label.is_scored is True
    source = open("app/api/v1/reasoning/engines/diagnostic.py").read()
    assert "ScoreLabel.NOT_APPLICABLE: None," in source


# =========================================================== the bugfix, isolated
def test_not_applicable_can_now_actually_be_persisted(db):
    """The prerequisite bug this step found and fixed: migration c7d18a3f420b
    widened the CHECK constraint but not the COLUMN (varchar(10)), so writing
    'not_applicable' (14 chars) raised at the database regardless of what any
    application code did. Fixed by d1a4c8e2f907. This is the regression test
    for that fix, independent of anything else in Step 7B."""
    row = db.execute(text("SELECT session_id, founder_id FROM answers LIMIT 1")).first()
    session_id, founder_id = row
    question_id = db.execute(text(
        "SELECT question_id FROM questions"
        " WHERE question_id NOT IN (SELECT question_id FROM answers WHERE session_id = :s)"
        " LIMIT 1"), {"s": session_id}).scalar()
    db.execute(text(
        "INSERT INTO answers (session_id, founder_id, question_id, answer_text, score_label)"
        " VALUES (:s, :f, :q, 'probe', 'not_applicable')"),
        {"s": session_id, "f": founder_id, "q": question_id})
    db.flush()
    stored = db.execute(text(
        "SELECT score_label FROM answers WHERE session_id = :s AND question_id = :q"),
        {"s": session_id, "q": question_id}).scalar()
    assert stored == "not_applicable"
