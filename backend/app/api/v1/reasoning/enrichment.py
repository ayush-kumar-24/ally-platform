"""Retrieval-backed root-cause enrichment.

Adapts the generic RetrievalEngine to the `RootCauseEnricher` seam. For each
already-detected root cause it embeds the cause's own text, retrieves supporting
semantic evidence (similar problems, matching founder-statement interpretations,
supporting knowledge chunks), and attaches it as `semantic_evidence` plus a
contributing-factor tag.

Boundary guarantees:
  * It never changes the deterministic fields of a detection (root_cause_id,
    scores, confirmation, order). Enrichment is strictly additive.
  * It never adds or removes detections -- same causes in, same causes out.
  * The Root Cause Engine is untouched; this plugs in only through the enricher
    interface the engine already accepts.

`fail_open` (default True): if retrieval/embedding fails, log and return the
detections un-enriched rather than breaking the diagnosis -- semantic context is
an enhancement, not a correctness dependency.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from app.api.v1.reasoning.interfaces import ReasoningContext
from app.api.v1.reasoning.repository import ReasoningRepository
from app.api.v1.reasoning.schemas import RootCauseDetection
from app.core.logger import logger
from app.services.embeddings.base import EmbeddingError
from app.services.retrieval.engine import RetrievalEngine, RetrievalError
from app.services.retrieval.evidence import RetrievalSource

# Sources that provide *supporting* context for a detected cause (deliberately
# excludes root_causes itself -- we are corroborating a known cause, not
# re-finding it).
DEFAULT_ENRICHMENT_SOURCES: tuple[RetrievalSource, ...] = (
    RetrievalSource.AGENT_INTERPRETATIONS,
    RetrievalSource.PROBLEMS,
    RetrievalSource.RAG_CHUNKS,
)


class RetrievalRootCauseEnricher:
    """Implements the RootCauseEnricher protocol using the RetrievalEngine."""

    def __init__(
        self,
        retrieval: RetrievalEngine,
        repository: ReasoningRepository,
        *,
        top_k: int = 5,
        min_similarity: Decimal | float = 0.0,
        sources: tuple[RetrievalSource, ...] = DEFAULT_ENRICHMENT_SOURCES,
        fail_open: bool = True,
    ):
        self.retrieval = retrieval
        self.repository = repository
        self.top_k = top_k
        self.min_similarity = min_similarity
        self.sources = sources
        self.fail_open = fail_open

    def enrich(
        self,
        detections: list[RootCauseDetection],
        context: ReasoningContext,
    ) -> list[RootCauseDetection]:
        if not detections:
            return detections

        root_causes = self.repository.get_root_causes_by_ids(
            d.root_cause_id for d in detections
        )

        enriched: list[RootCauseDetection] = []
        for detection in detections:
            root_cause = root_causes.get(detection.root_cause_id)
            query = self._query_text(root_cause)
            if not query:
                enriched.append(detection)
                continue
            enriched.append(self._enrich_one(detection, query))
        return enriched

    # --- Internals --------------------------------------------------------

    def _enrich_one(self, detection: RootCauseDetection, query: str) -> RootCauseDetection:
        try:
            evidence = self.retrieval.search(
                query,
                sources=self.sources,
                k=self.top_k,
                min_similarity=self.min_similarity,
            )
        except (RetrievalError, EmbeddingError) as exc:
            if not self.fail_open:
                raise
            logger.warning(
                "Retrieval enrichment skipped for root cause",
                extra={"root_cause_id": detection.root_cause_id},
                exc_info=exc,
            )
            return detection

        if not evidence:
            return detection

        factors = detection.contributing_factors + (f"Semantic Support ({len(evidence)})",)
        return replace(
            detection,
            semantic_evidence=tuple(evidence),
            contributing_factors=factors,
        )

    def _query_text(self, root_cause) -> str:
        if root_cause is None:
            return ""
        parts = [root_cause.root_cause_name, root_cause.explanation]
        return ". ".join(p for p in parts if p).strip()
