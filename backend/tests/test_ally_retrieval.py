"""Unit tests for the Ally diagnosis-aware Retrieval Layer (Phase 5, Milestone 3).

Hermetic: builds AllyContext DTOs and an in-memory vector repository. No database,
no embeddings, no LLM.
"""

from decimal import Decimal

import pytest

from app.api.v1.ally.context.schemas import (
    AllyContext,
    BusinessHealthContext,
    DiagnosisContext,
    FounderProfileContext,
    RootCauseContext,
)
from app.api.v1.ally.rag import (
    InMemoryVectorRetrievalRepository,
    KnowledgeChunk,
    MatchBreakdown,
    RetrievalRepository,
    RetrievalResult,
    build_filters,
    build_retrieval_service,
)

D = Decimal


def make_ctx(*, conf="80", distress=False, stage="Growth / Scaling", industry="SaaS"):
    founder = FounderProfileContext(1, "Asha", 5, stage, industry)
    diagnosis = DiagnosisContext(
        session_id=42, overall_confidence=D(conf), routing_state="validate",
        distress_mode=distress, session_state="stable", executive_summary="s",
        priority_actions=(), next_steps=(),
    )
    rcs = (
        RootCauseContext(10, "RC-010", "Weak activation", "Sales & Revenue", 1, "unconfirmed", D("0.8"), True),
        RootCauseContext(20, "RC-020", "Unclear pricing", "Product", 2, "unconfirmed", D("0.5"), False),
    )
    bh = BusinessHealthContext(overall_score="68", band="Developing", pillars=(), red_flags=())
    return AllyContext(founder=founder, has_diagnosis=True, diagnosis=diagnosis,
                       root_causes=rcs, business_health=bh)


def chunk(cid, *, sim, source="rag_chunks", source_id=None, stage=None, industry=None,
          category=None, rc_ids=(), quality=0):
    return KnowledgeChunk(
        chunk_id=cid, source=source, source_id=source_id if source_id is not None else cid,
        content=f"content {cid}", similarity=D(str(sim)), stage=stage, industry=industry,
        category=category, root_cause_ids=tuple(rc_ids), source_quality=quality,
    )


def svc(chunks, **kw):
    return build_retrieval_service(InMemoryVectorRetrievalRepository(chunks), **kw)


# --- Filter engine ----------------------------------------------------------


def test_build_filters_from_context():
    f = build_filters(make_ctx(distress=True), top_k=7)
    assert f.stages == ("Growth / Scaling",)
    assert f.industry == "SaaS"
    assert f.root_cause_ids == (10,)                 # top finding only
    assert f.categories == ("Sales & Revenue", "Product")
    assert f.business_health_band == "Developing"
    assert f.distress_mode is True
    assert f.top_k == 7


# --- Pre-filtering (before vector search) -----------------------------------


def test_stage_prefilter_excludes_other_stage():
    chunks = [chunk("match", sim=0.5, stage="Growth / Scaling"),
              chunk("general", sim=0.5, stage=None),
              chunk("other", sim=0.9, stage="Ideation")]
    ids = {r.chunk.chunk_id for r in svc(chunks).retrieve(make_ctx(), "q").items}
    assert ids == {"match", "general"}               # "other" stage dropped


def test_industry_prefilter_excludes_other_industry():
    chunks = [chunk("saas", sim=0.5, industry="SaaS"),
              chunk("agnostic", sim=0.5, industry=None),
              chunk("d2c", sim=0.9, industry="D2C")]
    ids = {r.chunk.chunk_id for r in svc(chunks).retrieve(make_ctx(), "q").items}
    assert ids == {"saas", "agnostic"}


def test_root_cause_prefilter_excludes_unrelated():
    chunks = [chunk("rc10", sim=0.5, rc_ids=[10]),
              chunk("general", sim=0.5, rc_ids=[]),
              chunk("rc99", sim=0.9, rc_ids=[99])]
    ids = {r.chunk.chunk_id for r in svc(chunks).retrieve(make_ctx(), "q").items}
    assert ids == {"rc10", "general"}


def test_min_similarity_filter():
    chunks = [chunk("hi", sim=0.8), chunk("lo", sim=0.2)]
    ids = {r.chunk.chunk_id for r in svc(chunks).retrieve(make_ctx(), "q", min_similarity=D("0.5")).items}
    assert ids == {"hi"}


# --- Ranking (after retrieval) ----------------------------------------------


def test_ranking_prefers_diagnosis_relevance_over_similarity():
    # A: higher similarity, no diagnosis relevance. B: lower similarity, full match.
    a = chunk("A", sim=0.95)
    b = chunk("B", sim=0.50, stage="Growth / Scaling", industry="SaaS",
              category="Sales & Revenue", rc_ids=[10])
    result = svc([a, b]).retrieve(make_ctx(conf="80"), "q")
    assert [r.chunk.chunk_id for r in result.items] == ["B", "A"]


def test_confidence_changes_ranking_order():
    # A and B share stage+industry; B adds diagnosis relevance (scaled by confidence),
    # A has higher similarity. High confidence -> B wins; low confidence -> A wins.
    a = chunk("A", sim=0.90, stage="Growth / Scaling", industry="SaaS")
    b = chunk("B", sim=0.70, stage="Growth / Scaling", industry="SaaS",
              category="Sales & Revenue", rc_ids=[10])
    high = svc([a, b]).retrieve(make_ctx(conf="80"), "q")
    low = svc([a, b]).retrieve(make_ctx(conf="5"), "q")
    assert [r.chunk.chunk_id for r in high.items] == ["B", "A"]
    assert [r.chunk.chunk_id for r in low.items] == ["A", "B"]


def test_ranking_score_components_recorded():
    b = chunk("B", sim=0.50, stage="Growth / Scaling", industry="SaaS",
              category="Sales & Revenue", rc_ids=[10])
    top = svc([b]).retrieve(make_ctx(conf="80"), "q").items[0]
    assert top.score.stage_match == D("1")
    assert top.score.industry_match == D("1")
    assert top.score.root_cause_relevance == D("1")
    assert top.score.category_relevance == D("1")
    assert top.score.confidence == D("0.8")
    assert top.score.total > D("0")
    assert top.rank == 1


def test_deterministic_ranking_repeats_identically():
    chunks = [chunk("A", sim=0.9, rc_ids=[10]), chunk("B", sim=0.9, rc_ids=[10]),
              chunk("C", sim=0.5)]
    s = svc(chunks)
    first = s.retrieve(make_ctx(), "q")
    assert all(s.retrieve(make_ctx(), "q") == first for _ in range(5))


def test_identical_request_produces_identical_result():
    chunks = [chunk("A", sim=0.7, rc_ids=[10]), chunk("B", sim=0.6, category="Sales & Revenue")]
    a = svc(chunks).retrieve(make_ctx(), "same-query")
    b = svc(chunks).retrieve(make_ctx(), "same-query")
    assert a == b


# --- Retrieval provenance (MatchBreakdown) ----------------------------------


def _full_match_item(conf="80"):
    b = chunk("B", sim=0.50, stage="Growth / Scaling", industry="SaaS",
              category="Sales & Revenue", rc_ids=[10])
    return svc([b]).retrieve(make_ctx(conf=conf), "q").items[0]


def test_match_breakdown_exists_and_is_typed():
    item = _full_match_item()
    assert isinstance(item.match_breakdown, MatchBreakdown)


def test_breakdown_similarity_is_correct():
    assert _full_match_item().match_breakdown.similarity_score == D("0.50")


def test_breakdown_stage_and_industry_match_are_correct():
    mb = _full_match_item().match_breakdown
    assert mb.stage_match == D("1")
    assert mb.industry_match == D("1")


def test_breakdown_root_cause_and_category_match_are_correct():
    mb = _full_match_item().match_breakdown
    assert mb.root_cause_match == D("1")
    assert mb.category_match == D("1")


def test_breakdown_confidence_multiplier_matches_ranking():
    item = _full_match_item(conf="80")
    assert item.match_breakdown.confidence_multiplier == item.score.confidence == D("0.8")


def test_breakdown_final_score_equals_ranking_score():
    item = _full_match_item()
    assert item.match_breakdown.final_ranking_score == item.score.total


def test_breakdown_values_all_mirror_ranking_score():
    item = _full_match_item()
    s, mb = item.score, item.match_breakdown
    assert (mb.similarity_score, mb.stage_match, mb.industry_match, mb.root_cause_match,
            mb.category_match, mb.confidence_multiplier, mb.final_ranking_score) == (
        s.similarity, s.stage_match, s.industry_match, s.root_cause_relevance,
        s.category_relevance, s.confidence, s.total)


def test_changing_ranking_changes_breakdown():
    high = _full_match_item(conf="80").match_breakdown
    low = _full_match_item(conf="5").match_breakdown
    assert high.confidence_multiplier != low.confidence_multiplier
    assert high.final_ranking_score != low.final_ranking_score


def test_identical_retrieval_produces_identical_breakdown():
    a = _full_match_item()
    b = _full_match_item()
    assert a.match_breakdown == b.match_breakdown


def test_breakdown_does_not_affect_ranking_order():
    # Adding provenance must not change which items rank where.
    a = chunk("A", sim=0.95)
    b = chunk("B", sim=0.50, stage="Growth / Scaling", industry="SaaS",
              category="Sales & Revenue", rc_ids=[10])
    order = [r.chunk.chunk_id for r in svc([a, b]).retrieve(make_ctx(conf="80"), "q").items]
    assert order == ["B", "A"]


# --- Deduplication ----------------------------------------------------------


def test_duplicate_removal_prefers_higher_quality():
    # Same (source, source_id); the higher-quality copy survives despite lower sim.
    low_q = chunk("keepY_lowqual", sim=0.9, source="root_causes", source_id=10, quality=1)
    high_q = chunk("keepX_highqual", sim=0.6, source="root_causes", source_id=10, quality=5)
    result = svc([low_q, high_q]).retrieve(make_ctx(), "q")
    assert result.candidate_count == 2
    assert result.unique_count == 1
    assert result.items[0].chunk.chunk_id == "keepX_highqual"


# --- Fail-closed ------------------------------------------------------------


def test_empty_vector_response_returns_empty_result():
    # All chunks tagged for a different stage/industry/rc -> filtered out.
    chunks = [chunk("x", sim=0.9, stage="Ideation", industry="D2C", rc_ids=[99])]
    result = svc(chunks).retrieve(make_ctx(), "q")
    assert result.is_empty and result.enabled is True and result.candidate_count == 0


def test_disabled_retrieval_returns_empty():
    result = svc([chunk("A", sim=0.9)], enabled=False).retrieve(make_ctx(), "q")
    assert result.is_empty and result.enabled is False


def test_top_k_zero_returns_empty_items():
    result = svc([chunk("A", sim=0.9)], default_top_k=0).retrieve(make_ctx(), "q")
    assert result.is_empty


def test_repository_failure_fails_closed():
    class Boom(RetrievalRepository):
        def search(self, request):
            raise RuntimeError("vector store down")

    service = build_retrieval_service(Boom())
    result = service.retrieve(make_ctx(), "q")
    assert isinstance(result, RetrievalResult)
    assert result.is_empty and result.enabled is True   # failed, not disabled


def test_top_k_caps_results():
    chunks = [chunk(f"c{i}", sim=0.5 + i / 100, rc_ids=[10]) for i in range(10)]
    result = svc(chunks).retrieve(make_ctx(), "q", top_k=3)
    assert len(result.items) == 3
    assert [r.rank for r in result.items] == [1, 2, 3]
