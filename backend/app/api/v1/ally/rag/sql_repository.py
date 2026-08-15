"""SQL-backed RetrievalRepository -- cosine similarity search over rag_chunks.

The production implementation of the abstract seam in `repository.py`. Unlike
`services/retrieval/engine.py` (which searches several embedded tables generically
for the reasoning pipeline's root-cause enrichment), this repository is scoped to
`rag_chunks` JOIN `rag_documents` specifically -- that pairing is the one place the
document-level tags this layer's KnowledgeChunk needs (stage_relevance,
industry_tag, review/active gating) actually live. Sources beyond rag_chunks
(problems, root_causes, ...) are already surfaced to chat directly through
AllyContext.diagnosis; duplicating them into "retrieved knowledge" would blur where
a fact came from.

Stage/industry are SOFT pre-filters, matching passes_filters()'s own semantics: an
untagged document (NULL stage_relevance / industry_tag) is general knowledge and is
never wrongly excluded, only a document tagged for a DIFFERENT stage/industry is
dropped. The sales-collateral gate (content_class / retrieval_scope in
metadata_tags) is enforced in SQL, before the top-k -- same fail-closed convention
as SOURCE_SPECS[RAG_CHUNKS].restricted_where in the reasoning-side engine.

Query embedding reuses the same EmbeddingProvider/EMBEDDING_DIMENSION settings as
the reasoning pipeline's RetrievalEngine, so both paths stay pointed at the same
embedding model (currently OpenAI text-embedding-3-small, 1536-d) by construction,
not by convention.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.ally.rag.repository import RetrievalRepository
from app.api.v1.ally.rag.schemas import KnowledgeChunk, RetrievalRequest
from app.services.embeddings.base import EmbeddingProvider, EmbeddingProviderError
from app.services.retrieval.engine import RetrievalError

_SIM_QUANT = Decimal("0.000001")
# Candidate pool fetched per search, ahead of the service's own dedup/rank/top_k --
# wide enough that ranking has real choices, bounded so one query stays cheap.
_CANDIDATE_MULTIPLE = 4
_MAX_CANDIDATES = 40

_SQL = """
SELECT
    c.chunk_id, c.chunk_text, c.document_id, c.metadata_tags,
    d.document_type, d.industry_tag, d.stage_relevance,
    1 - (c.embedding <=> CAST(:qvec AS vector)) AS similarity
FROM rag_chunks c
JOIN rag_documents d ON d.document_id = c.document_id
WHERE c.embedding IS NOT NULL
  AND c.is_active = TRUE
  AND d.is_active = TRUE
  AND d.review_status = 'approved'
  {restricted}
  {stage_filter}
  {industry_filter}
ORDER BY c.embedding <=> CAST(:qvec AS vector) ASC, c.chunk_id ASC
LIMIT :limit
"""

_RESTRICTED_CLAUSE = (
    "AND (c.metadata_tags->>'retrieval_scope' IS DISTINCT FROM 'recommendation_only' "
    "AND c.metadata_tags->>'content_class' IS DISTINCT FROM 'sales_collateral')"
)
_STAGE_CLAUSE = (
    "AND (d.stage_relevance IS NULL OR d.stage_relevance = 'All' "
    "OR d.stage_relevance = ANY(:stages))"
)
_INDUSTRY_CLAUSE = "AND (d.industry_tag IS NULL OR d.industry_tag = :industry)"


class SqlVectorRetrievalRepository(RetrievalRepository):
    def __init__(self, db: Session, embedder: EmbeddingProvider, *, expected_dimension: int = 1536):
        self.db = db
        self.embedder = embedder
        self.expected_dimension = expected_dimension

    def search(self, request: RetrievalRequest) -> tuple[KnowledgeChunk, ...]:
        vector = self._embed(request.query)
        qvec = self._format_vector(vector)
        f = request.filters

        sql = _SQL.format(
            restricted="" if f.allow_sales_collateral else _RESTRICTED_CLAUSE,
            stage_filter=_STAGE_CLAUSE if f.stages else "",
            industry_filter=_INDUSTRY_CLAUSE if f.industry else "",
        )
        params: dict[str, object] = {
            "qvec": qvec,
            "limit": min(max(request.top_k, 1) * _CANDIDATE_MULTIPLE, _MAX_CANDIDATES),
        }
        if f.stages:
            params["stages"] = list(f.stages)
        if f.industry:
            params["industry"] = f.industry

        rows = self.db.execute(text(sql), params).mappings().all()
        chunks = tuple(self._to_chunk(row) for row in rows)
        min_sim = Decimal(str(f.min_similarity))
        return tuple(c for c in chunks if c.similarity >= min_sim)

    # --- mapping -----------------------------------------------------------

    def _to_chunk(self, row) -> KnowledgeChunk:
        tags = row["metadata_tags"] or {}
        return KnowledgeChunk(
            chunk_id=str(row["chunk_id"]),
            source="rag_chunks",
            source_id=row["chunk_id"],
            content=row["chunk_text"] or "",
            similarity=Decimal(str(row["similarity"])).quantize(_SIM_QUANT, rounding=ROUND_HALF_UP),
            stage=row["stage_relevance"],
            industry=row["industry_tag"],
            category=row["document_type"],
            # metadata_tags carries founder-facing root-cause codes (e.g. "RC-114"),
            # not the integer root_cause_id this field expects -- left empty rather
            # than fabricating a lookup; the sales-collateral gate below is the tag
            # that actually matters for safety.
            root_cause_ids=(),
            metadata={"document_id": row["document_id"], "tags": tags},
            content_class=tags.get("content_class"),
            retrieval_scope=tags.get("retrieval_scope"),
        )

    # --- embedding -----------------------------------------------------------

    def _embed(self, query_text: str) -> list[float]:
        try:
            vector = self.embedder.embed(query_text)
        except EmbeddingProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 -- normalise unexpected adapter failures
            raise EmbeddingProviderError(str(exc)) from exc
        if len(vector) != self.expected_dimension:
            raise RetrievalError(
                f"Embedding dimension {len(vector)} != expected {self.expected_dimension}. "
                "The query model does not match the stored vectors; retrieval would "
                "return meaningless neighbours."
            )
        return vector

    @staticmethod
    def _format_vector(vector: list[float]) -> str:
        return "[" + ",".join(f"{float(v):.8g}" for v in vector) + "]"
