"""Step 7B: FOUNDER ANSWER -> CAPABILITY EVIDENCE. Observation, not assessment.

THE ONE RULE THIS FILE EXISTS TO PROTECT: no evidence is not level 0. Every
"no evidence" test here asserts that NOTHING is stored -- never a row with a
low level, never a row with a hedged confidence. A stored row is a strong
claim, and the extractor's job is to make that claim rarely and only when it is
directly supported, exactly the standard Step 4 already set for N/A.

Levels 3-6 (positive/absent/personal/documented/owned) drive the extractor
purely through its OWN parsing logic (`_parse`, `_coerce_level`), never through
the network -- a `_FakeProvider` stands in, matching the pattern
`test_llm_routing.py` already uses. This proves the CONTRACT (JSON in, a typed
observation or None out) rather than any particular model's behaviour.
"""

import asyncio
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.capability_evidence import (
    CapabilityEvidenceObservation,
    LLMCapabilityEvidenceExtractor,
)
from app.api.v1.diagnosis.capability_levels import CapabilityLevel
from app.api.v1.diagnosis.repository import DiagnosisRepository
from app.api.v1.diagnosis.service import DiagnosisService
from app.db.session import engine as db_engine
from app.models.enums import ScoreLabel
from app.services.llm.base import LLMResponse


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


class _FakeProvider:
    """Matches tests/test_llm_routing.py's own stub exactly."""

    name = "fake"

    def __init__(self, text_: str | None = None, err: Exception | None = None):
        self._text, self._err = text_, err

    async def generate(self, request):
        if self._err:
            raise self._err
        return LLMResponse(text=self._text, model="fake", provider="fake")


def extractor(json_text):
    return LLMCapabilityEvidenceExtractor(_FakeProvider(text_=json_text))


GTM_OWN_CRITERIA = [
    {"criterion_id": 17, "criterion_text": "Someone other than the founder closes business"},
    {"criterion_id": 18, "criterion_text": "Sales targets are owned by a named person"},
    {"criterion_id": 19, "criterion_text": "The founder is not required for a routine deal"},
    {"criterion_id": 20, "criterion_text": "Sales performance is reviewed with the owner"},
]


def run(ext, **kw):
    defaults = dict(
        question_text="How is sales handled?", answer_text="answer",
        capability_id=5, capability_name="Sales Ownership Beyond the Founder",
        criteria=GTM_OWN_CRITERIA,
    )
    defaults.update(kw)
    return asyncio.run(ext.extract(**defaults))


# =========================================================== 1-5: the levels
def test_mapped_question_positive_answer_creates_evidence():
    """Case 1."""
    obs = run(extractor(
        '{"evidence_present":true,"criterion_id":18,"observed_level":3,'
        '"evidence_text":"a named sales lead owns the number","confidence":0.9}'
    ))
    assert obs is not None
    assert obs.observed_level == CapabilityLevel.OWNED
    assert obs.criterion_id == 18
    assert obs.capability_id == 5


def test_explicit_absence_yields_level_0():
    """Case 2. Level 0 is a POSITIVE claim of absence, not a default."""
    obs = run(extractor(
        '{"evidence_present":true,"criterion_id":null,"observed_level":0,'
        '"evidence_text":"founder states nobody else has ever sold anything",'
        '"confidence":0.85}'
    ))
    assert obs.observed_level == CapabilityLevel.ABSENT


def test_founder_dependent_answer_yields_level_1():
    """Case 3."""
    obs = run(extractor(
        '{"evidence_present":true,"criterion_id":19,"observed_level":1,'
        '"evidence_text":"founder personally closes nearly every deal",'
        '"confidence":0.9}'
    ))
    assert obs.observed_level == CapabilityLevel.PERSONAL


def test_documented_process_answer_yields_level_2():
    """Case 4."""
    obs = run(extractor(
        '{"evidence_present":true,"criterion_id":18,"observed_level":2,'
        '"evidence_text":"a written sales process exists but the founder still runs it",'
        '"confidence":0.8}'
    ))
    assert obs.observed_level == CapabilityLevel.DOCUMENTED


def test_organizational_ownership_answer_yields_level_3():
    """Case 5."""
    obs = run(extractor(
        '{"evidence_present":true,"criterion_id":17,"observed_level":3,'
        '"evidence_text":"a sales manager owns the pipeline and reports on it",'
        '"confidence":0.92}'
    ))
    assert obs.observed_level == CapabilityLevel.OWNED


# =========================================================== the no-evidence cases
def test_evidence_present_false_stores_nothing():
    assert run(extractor('{"evidence_present":false}')) is None


def test_low_confidence_produces_no_fabricated_evidence():
    """Case 9. A hedge is not evidence, even with a plausible level attached."""
    obs = run(extractor(
        '{"evidence_present":true,"criterion_id":18,"observed_level":2,'
        '"evidence_text":"maybe implies a process","confidence":0.3}'
    ))
    assert obs is None


def test_evidence_present_true_with_no_level_stores_nothing():
    # A malformed response, not "level unknown" -- there is no such state here.
    assert run(extractor(
        '{"evidence_present":true,"criterion_id":18,"observed_level":null,'
        '"evidence_text":"x","confidence":0.9}'
    )) is None


def test_an_out_of_range_level_is_rejected():
    assert run(extractor(
        '{"evidence_present":true,"observed_level":7,'
        '"evidence_text":"x","confidence":0.9}'
    )) is None


def test_a_provider_timeout_yields_no_evidence_not_an_exception():
    """Fail-open matches advisor.py's own contract exactly: a provider-layer
    failure (timeout, LLMProviderError) is swallowed HERE, inside the
    extractor. An unexpected exception of a different kind is deliberately
    left to propagate to the OUTER `except Exception` in
    `DiagnosisService._extract_capability_evidence`, which is the layer that
    actually guarantees a founder's answer is never put at risk -- exactly the
    two-layer shape `advisor.py` / `submit_answer` already uses."""
    from app.services.llm.base import LLMProviderError
    obs = asyncio.run(LLMCapabilityEvidenceExtractor(_FakeProvider(
        err=LLMProviderError("boom"))).extract(
        question_text="q", answer_text="a", capability_id=1,
        capability_name="x", criteria=[]))
    assert obs is None


def test_an_unexpected_extractor_error_is_caught_one_layer_up(db):
    """The outer guarantee. `_extract_capability_evidence` must not let ANY
    extractor failure reach the caller -- this is what makes a broken
    extractor safe to enable without risking every founder's answer."""

    class _AlwaysBreaks:
        async def extract(self, **kwargs):
            raise RuntimeError("extractor blew up unexpectedly")

    session = SimpleNamespace(session_id=db.execute(
        text("SELECT session_id FROM sessions LIMIT 1")).scalar())
    answer_row = db.execute(text(
        "SELECT answer_id, question_id, score_label FROM answers"
        " WHERE score_label = 'green' LIMIT 1")).first()
    answer = SimpleNamespace(
        answer_id=answer_row[0], question_id=answer_row[1],
        score_label=answer_row[2], answer_text="some real answer",
    )
    question = SimpleNamespace(
        question_id=answer_row[1],
        question_text=db.execute(text(
            "SELECT question_text FROM questions WHERE question_id = :q"),
            {"q": answer_row[1]}).scalar(),
    )
    svc = DiagnosisService(db, capability_evidence_extractor=_AlwaysBreaks())
    # Must not raise.
    asyncio.run(svc._extract_capability_evidence(session, answer, question))


def test_malformed_json_yields_no_evidence():
    assert run(extractor("not json at all")) is None


def test_empty_answer_text_is_never_sent_to_the_model():
    calls = []

    class _Spy:
        async def generate(self, request):
            calls.append(request)
            raise AssertionError("must not be called for empty text")

    obs = asyncio.run(LLMCapabilityEvidenceExtractor(_Spy()).extract(
        question_text="q", answer_text="   ", capability_id=1,
        capability_name="x", criteria=GTM_OWN_CRITERIA))
    assert obs is None
    assert calls == []


# =========================================================== criterion integrity
def test_a_criterion_id_outside_the_offered_set_is_dropped_not_trusted():
    """The taxonomy is authoritative, never the model's memory of it."""
    obs = run(extractor(
        '{"evidence_present":true,"criterion_id":999,"observed_level":2,'
        '"evidence_text":"x","confidence":0.9}'
    ))
    assert obs is not None
    assert obs.criterion_id is None                # dropped, not trusted


def test_a_null_criterion_is_a_valid_capability_level_observation():
    obs = run(extractor(
        '{"evidence_present":true,"criterion_id":null,"observed_level":1,'
        '"evidence_text":"founder does everything personally","confidence":0.8}'
    ))
    assert obs is not None
    assert obs.criterion_id is None


# =========================================================== 10-11: DB integrity
def test_invalid_capability_id_cannot_be_stored(db):
    """Case 10."""
    answer_id = db.execute(text(
        "SELECT answer_id FROM answers WHERE score_label IS NOT NULL LIMIT 1")).scalar()
    question_id = db.execute(text("SELECT question_id FROM questions LIMIT 1")).scalar()
    with pytest.raises(Exception):
        db.execute(text(
            "INSERT INTO capability_evidence"
            " (capability_id, question_id, answer_id, observed_level, confidence,"
            "  evidence_text)"
            " VALUES (999999, :q, :a, 2, 0.9, 'x')"),
            {"q": question_id, "a": answer_id})
        db.flush()


def test_invalid_evidence_criterion_cannot_be_stored(db):
    """Case 11. A criterion belonging to a DIFFERENT capability is rejected by
    the composite FK -- not just one that does not exist at all."""
    cap1, cap2 = db.execute(text(
        "SELECT capability_id FROM capabilities ORDER BY capability_id LIMIT 2")).all()
    wrong_criterion = db.execute(text(
        "SELECT criterion_id FROM capability_evidence_criteria"
        " WHERE capability_id = :c LIMIT 1"), {"c": cap2[0]}).scalar()
    question_id = db.execute(text("SELECT question_id FROM questions LIMIT 1")).scalar()
    answer_id = db.execute(text("SELECT answer_id FROM answers LIMIT 1")).scalar()
    with pytest.raises(Exception):
        db.execute(text(
            "INSERT INTO capability_evidence"
            " (capability_id, question_id, answer_id, criterion_id, observed_level,"
            "  confidence, evidence_text)"
            " VALUES (:cap, :q, :a, :crit, 2, 0.9, 'x')"),
            {"cap": cap1[0], "q": question_id, "a": answer_id, "crit": wrong_criterion})
        db.flush()


# =========================================================== 12: traceability
def test_every_observation_traces_to_answer_question_and_capability(db):
    """Case 12: one SELECT, no join chain, answers 'why did Ally think this'."""
    repo = DiagnosisRepository(db)
    answer_id = db.execute(text(
        "SELECT answer_id FROM answers WHERE score_label = 'green' LIMIT 1")).scalar()
    question_id = db.execute(text(
        "SELECT question_id FROM answers WHERE answer_id = :a"), {"a": answer_id}).scalar()
    capability_id = db.execute(text("SELECT capability_id FROM capabilities LIMIT 1")).scalar()
    stored = repo.record_capability_evidence(
        capability_id=capability_id, question_id=question_id, answer_id=answer_id,
        observed_level=2, confidence=0.85, evidence_text="traceable observation",
    )
    assert stored is True
    row = db.execute(text(
        "SELECT capability_id, question_id, answer_id, criterion_id, observed_level,"
        "       confidence, evidence_text"
        "  FROM capability_evidence WHERE answer_id = :a"), {"a": answer_id}).mappings().first()
    assert row["capability_id"] == capability_id
    assert row["question_id"] == question_id
    assert row["answer_id"] == answer_id
    assert row["criterion_id"] is None
    assert row["observed_level"] == 2
    assert row["evidence_text"] == "traceable observation"


# =========================================================== 13-14: idempotency
def test_reprocessing_the_same_answer_does_not_duplicate(db):
    """Case 13. DB-enforced, not application logic -- see UNIQUE(answer_id)."""
    repo = DiagnosisRepository(db)
    answer_id = db.execute(text(
        "SELECT answer_id FROM answers WHERE score_label = 'green' LIMIT 1")).scalar()
    question_id = db.execute(text(
        "SELECT question_id FROM answers WHERE answer_id = :a"), {"a": answer_id}).scalar()
    capability_id = db.execute(text("SELECT capability_id FROM capabilities LIMIT 1")).scalar()

    first = repo.record_capability_evidence(
        capability_id=capability_id, question_id=question_id, answer_id=answer_id,
        observed_level=1, confidence=0.7, evidence_text="first pass")
    second = repo.record_capability_evidence(
        capability_id=capability_id, question_id=question_id, answer_id=answer_id,
        observed_level=3, confidence=0.99, evidence_text="reprocessed, different result")

    assert first is True
    assert second is False                          # silently skipped, not an error
    count = db.execute(text(
        "SELECT count(*) FROM capability_evidence WHERE answer_id = :a"),
        {"a": answer_id}).scalar()
    assert count == 1
    kept = db.execute(text(
        "SELECT evidence_text FROM capability_evidence WHERE answer_id = :a"),
        {"a": answer_id}).scalar()
    assert kept == "first pass"                      # the first write wins


def test_multiple_observations_for_one_capability_stay_separate(db):
    """Case 14. Q1/Q2/Q3 -> same capability, different answers -> three rows,
    never averaged. Step 7C's job, not this one's."""
    repo = DiagnosisRepository(db)
    capability_id = db.execute(text("SELECT capability_id FROM capabilities LIMIT 1")).scalar()
    answer_ids = [r[0] for r in db.execute(text(
        "SELECT answer_id FROM answers WHERE score_label IS NOT NULL LIMIT 3")).all()]
    assert len(answer_ids) == 3, "need three distinct answers in this database"
    question_ids = {a: db.execute(text(
        "SELECT question_id FROM answers WHERE answer_id = :a"), {"a": a}).scalar()
        for a in answer_ids}

    for level, answer_id in zip((1, 2, 1), answer_ids):
        repo.record_capability_evidence(
            capability_id=capability_id, question_id=question_ids[answer_id],
            answer_id=answer_id, observed_level=level, confidence=0.8,
            evidence_text=f"observation for answer {answer_id}")

    rows = db.execute(text(
        "SELECT observed_level FROM capability_evidence"
        " WHERE capability_id = :c AND answer_id = ANY(:ids)"),
        {"c": capability_id, "ids": answer_ids}).scalars().all()
    assert sorted(rows) == [1, 1, 2]                  # three rows, not one average


# =========================================================== golden test
def test_golden_founder_dependent_sales_answer(db):
    """Section 15. A realistic founder answer, against the ACTUAL Step 7A
    mapping and the ACTUAL Step 5 evidence criteria -- nothing invented.

    Question 969 ("Does your sales compensation actually reward the behaviors
    your business needs most...") is one of the four real questions problem
    SCL-020 seeded, and SCL-020 maps to GTM-OWN (Sales Ownership Beyond the
    Founder) in the migration's own HIGH_CONFIDENCE list -- asserted here
    rather than assumed, so this test breaks loudly if the curation ever
    changes instead of silently testing a stale mapping.
    """
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "qc_migration",
        Path(__file__).resolve().parents[1] / "alembic" / "versions"
        / "2026_09_19_1600-c5e7b1a94f60_question_capability_mapping.py",
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert ("SCL-020", "GTM-OWN") in migration.HIGH_CONFIDENCE, (
        "the golden test's premise -- SCL-020 maps to GTM-OWN -- no longer "
        "holds against the actual seeded curation"
    )

    gtm_own_id = db.execute(text(
        "SELECT capability_id FROM capabilities WHERE capability_code = 'GTM-OWN'"
    )).scalar()
    assert gtm_own_id is not None, "GTM-OWN is missing from the live taxonomy"

    founder_answer = (
        "I personally handle nearly every sales conversation and close most "
        "deals myself. Nobody else on the team really owns the number."
    )
    # The model's plausible, criteria-grounded read of that answer -- level 1
    # (PERSONAL), because the founder explicitly says the capability runs
    # through them and no one else. This is what the extractor's PARSING must
    # produce from such a response; it is not a claim about what any specific
    # model will say.
    llm_json = (
        '{"evidence_present":true,"criterion_id":19,"observed_level":1,'
        '"evidence_text":"founder personally closes nearly every deal; no one '
        'else owns the sales number","confidence":0.88}'
    )
    obs = asyncio.run(LLMCapabilityEvidenceExtractor(_FakeProvider(text_=llm_json)).extract(
        question_text=(
            "Does your sales compensation actually reward the behaviors your "
            "business needs most right now -- like margin or retention -- or "
            "mostly just new deal volume?"
        ),
        answer_text=founder_answer,
        capability_id=gtm_own_id,  # looked up live, never hard-coded
        capability_name="Sales Ownership Beyond the Founder",
        criteria=GTM_OWN_CRITERIA,
    ))
    assert obs is not None
    assert obs.observed_level == CapabilityLevel.PERSONAL
    assert obs.criterion_id == 19
    assert "founder" in obs.evidence_text.lower()
