"""Retrieval Engine -- cosine similarity search over the pgvector embeddings.

Uses the existing infrastructure: the `*_embedding` columns and their HNSW
indexes (`vector_cosine_ops`). Query text is embedded once via the configured
EmbeddingProvider (gte-small, 384-d), then each requested source is searched with
the cosine-distance operator `<=>`, which the HNSW indexes serve.

No new Python dependency: the query vector is sent as a pgvector text literal and
cast server-side (`CAST(:qvec AS vector)`), so pgvector stays entirely in
Postgres. Table and column names come only from the internal SOURCE_SPECS map
(never from input), and the vector / k / threshold are bound parameters.

Deterministic: ordering is by cosine distance ascending with the primary key as a
stable tiebreak, so identical query vectors return identical, identically-ordered
results.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.embeddings.base import EmbeddingProvider, EmbeddingProviderError
from app.services.retrieval.evidence import RetrievalEvidence, RetrievalSource

_SIM_QUANT = Decimal("0.000001")


class RetrievalError(Exception):
    """Retrieval could not be performed (e.g. embedding dimension mismatch)."""


@dataclass(frozen=True)
class SourceSpec:
    """How to search one embedded table. All identifiers are trusted constants."""

    source: RetrievalSource
    table: str
    id_col: str
    content_col: str
    metadata: dict[str, str]        # output label -> column expression
    extra_where: str | None = None  # additional filter, e.g. "is_active = TRUE"
    # Public filter name -> real column. Only these columns may be pre-filtered on;
    # values are always bound parameters, so the whitelist is the injection guard.
    filter_columns: dict[str, str] = field(default_factory=dict)


SOURCE_SPECS: dict[RetrievalSource, SourceSpec] = {
    RetrievalSource.ROOT_CAUSES: SourceSpec(
        RetrievalSource.ROOT_CAUSES, "root_causes", "root_cause_id", "root_cause_name",
        {"root_cause_category": "root_cause_category", "problem_id": "problem_id"},
        filter_columns={
            "category": "root_cause_category",
            "problem_id": "problem_id",
            "stage_group": "primary_stage_group",
        },
    ),
    RetrievalSource.PROBLEMS: SourceSpec(
        RetrievalSource.PROBLEMS, "problems", "problem_id", "problem_name",
        {"category": "category", "layer": "layer"},
        filter_columns={"category": "category", "problem_id": "problem_id", "pillar_id": "pillar_id"},
    ),
    RetrievalSource.QUESTIONS: SourceSpec(
        RetrievalSource.QUESTIONS, "questions", "question_id", "question_text",
        {"category": "category", "root_cause_id": "root_cause_id"},
        filter_columns={
            "category": "category",
            "problem_id": "problem_id",
            "root_cause_id": "root_cause_id",
            "stage_group": "primary_stage_group",
        },
    ),
    RetrievalSource.AGENT_INTERPRETATIONS: SourceSpec(
        RetrievalSource.AGENT_INTERPRETATIONS, "agent_interpretations", "interpretation_id",
        "founder_statement",
        {"category": "category", "likely_root_cause": "likely_root_cause",
         "linked_root_cause_ids": "linked_root_cause_ids"},
        filter_columns={"category": "category"},
    ),
    RetrievalSource.RAG_CHUNKS: SourceSpec(
        RetrievalSource.RAG_CHUNKS, "rag_chunks", "chunk_id", "chunk_text",
        {"document_id": "document_id", "metadata_tags": "metadata_tags"},
        extra_where="is_active = TRUE",
        filter_columns={"document_id": "document_id"},
    ),
}

DEFAULT_SOURCES: tuple[RetrievalSource, ...] = tuple(SOURCE_SPECS)


class RetrievalEngine:
    def __init__(
        self,
        db: Session,
        embedder: EmbeddingProvider,
        *,
        expected_dimension: int = 384,
    ):
        self.db = db
        self.embedder = embedder
        self.expected_dimension = expected_dimension

    def search(
        self,
        query_text: str,
        *,
        sources: tuple[RetrievalSource, ...] | None = None,
        k: int = 5,
        min_similarity: Decimal | float = 0.0,
        filters: Mapping[str, object] | None = None,
    ) -> list[RetrievalEvidence]:
        """Embed `query_text` once and search each source, returning up to `k`
        hits per source that clear `min_similarity`, best first within a source.

        `filters` pre-scopes the candidate set BEFORE the vector top-k (e.g.
        `{"category": "Sales & Revenue", "stage_group": "Stage 0→1"}`). Each source
        applies only the filter keys it supports (see SourceSpec.filter_columns);
        unsupported keys are ignored for that source. This keeps a search off the
        full corpus, which otherwise returns weak neighbours."""
        vector = self._embed_query(query_text)
        return self.search_by_vector(
            vector, sources=sources, k=k, min_similarity=min_similarity, filters=filters
        )

    def search_by_vector(
        self,
        vector: list[float],
        *,
        sources: tuple[RetrievalSource, ...] | None = None,
        k: int = 5,
        min_similarity: Decimal | float = 0.0,
        filters: Mapping[str, object] | None = None,
    ) -> list[RetrievalEvidence]:
        """Search using a caller-supplied vector (e.g. an existing row embedding),
        bypassing the embedding provider. Same guarantees as `search`."""
        self._validate_vector(vector)
        selected = sources if sources is not None else DEFAULT_SOURCES
        qvec = self._format_vector(vector)
        min_sim = Decimal(str(min_similarity))

        results: list[RetrievalEvidence] = []
        for source in selected:
            spec = SOURCE_SPECS[source]
            results.extend(self._search_one(spec, qvec, k, min_sim, filters))
        return results

    # --- Internals --------------------------------------------------------

    def _active_filters(
        self, spec: SourceSpec, filters: Mapping[str, object] | None
    ) -> dict[str, object]:
        """Keep only filter keys this source supports and whose value is not None.
        The column each key maps to is a trusted constant from filter_columns."""
        if not filters:
            return {}
        return {
            key: value
            for key, value in filters.items()
            if key in spec.filter_columns and value is not None
        }

    def _search_one(
        self,
        spec: SourceSpec,
        qvec: str,
        k: int,
        min_sim: Decimal,
        filters: Mapping[str, object] | None = None,
    ) -> list[RetrievalEvidence]:
        active = self._active_filters(spec, filters)
        sql = self._build_sql(spec, active.keys())
        params: dict[str, object] = {"qvec": qvec, "k": k, "min_sim": min_sim}
        for key in active:
            params[f"flt_{key}"] = active[key]
        rows = self.db.execute(text(sql), params).mappings().all()

        evidence: list[RetrievalEvidence] = []
        for row in rows:
            evidence.append(
                RetrievalEvidence(
                    source=spec.source,
                    source_id=row["source_id"],
                    similarity=Decimal(str(row["similarity"])).quantize(
                        _SIM_QUANT, rounding=ROUND_HALF_UP
                    ),
                    content=row["content"] if row["content"] is not None else "",
                    metadata={label: row[label] for label in spec.metadata},
                )
            )
        return evidence

    def _build_sql(self, spec: SourceSpec, filter_keys=()) -> str:
        meta_inner = "".join(
            f", {expr} AS {label}" for label, expr in spec.metadata.items()
        )
        meta_outer = "".join(f", {label}" for label in spec.metadata)
        extra = f" AND {spec.extra_where}" if spec.extra_where else ""
        # Pre-filters live in the INNER query so they scope the candidate set
        # BEFORE the vector top-k. Column names come from filter_columns (trusted);
        # values bind as :flt_<key>.
        filters = "".join(
            f" AND {spec.filter_columns[key]} = :flt_{key}" for key in filter_keys
        )
        distance = "embedding <=> CAST(:qvec AS vector)"
        return (
            f"SELECT source_id, content, similarity{meta_outer} FROM ("
            f" SELECT {spec.id_col} AS source_id, {spec.content_col} AS content,"
            f" 1 - ({distance}) AS similarity{meta_inner}"
            f" FROM {spec.table}"
            f" WHERE embedding IS NOT NULL{extra}{filters}"
            f" ORDER BY {distance} ASC, {spec.id_col} ASC"
            f" LIMIT :k"
            f" ) s WHERE similarity >= :min_sim"
        )

    def _embed_query(self, query_text: str) -> list[float]:
        try:
            return self.embedder.embed(query_text)
        except EmbeddingProviderError:
            raise
        except Exception as exc:  # normalise unexpected adapter failures
            raise EmbeddingProviderError(str(exc)) from exc

    def _validate_vector(self, vector: list[float]) -> None:
        if len(vector) != self.expected_dimension:
            raise RetrievalError(
                f"Embedding dimension {len(vector)} != expected "
                f"{self.expected_dimension}. The query model does not match the "
                "stored vectors; retrieval would return meaningless neighbours."
            )

    def _format_vector(self, vector: list[float]) -> str:
        return "[" + ",".join(f"{float(v):.8g}" for v in vector) + "]"
