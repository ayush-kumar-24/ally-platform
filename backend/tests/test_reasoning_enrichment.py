from decimal import Decimal
from types import SimpleNamespace

from app.api.v1.reasoning.enrichment import RetrievalRootCauseEnricher
from app.api.v1.reasoning.schemas import RootCauseDetection
from app.models.enums import ConfirmationStatus
from app.services.retrieval.evidence import RetrievalEvidence, RetrievalSource


class FakeRepository:
    def get_root_causes_by_ids(self, ids):
        return {
            109: SimpleNamespace(
                root_cause_id=109,
                root_cause_code="RC-109",
                root_cause_name="Unclear customer problem",
                explanation="The founder has not validated an acute problem.",
            )
        }


class FakeRetrieval:
    def __init__(self):
        self.filters = None

    def search(self, query, **kwargs):
        self.filters = kwargs["filters"]
        return [
            RetrievalEvidence(
                source=RetrievalSource.RAG_CHUNKS,
                source_id=47,
                similarity=Decimal("0.91"),
                content="Problem-first evidence",
                metadata={
                    "metadata_tags": {
                        "maps_to_root_causes": ["RC-109", "RC-170"]
                    }
                },
            )
        ]


def test_diagnosis_rag_uses_explicit_root_cause_mapping_without_changing_detection():
    retrieval = FakeRetrieval()
    enricher = RetrievalRootCauseEnricher(retrieval, FakeRepository())

    detection = RootCauseDetection(
        root_cause_id=109,
        category="Market",
        confirmation_status=ConfirmationStatus.UNCONFIRMED,
        detection_score=Decimal("0.70"),
        detection_confidence=Decimal("0.80"),
        evidence=(),
        contributing_factors=(),
        category_risk_score=Decimal("0.60"),
    )

    result = enricher.enrich([detection], SimpleNamespace())[0]

    assert retrieval.filters["root_cause_code"] == "RC-109"

    # RAG is supporting evidence only; deterministic diagnosis stays unchanged.
    assert result.root_cause_id == detection.root_cause_id
    assert result.detection_score == detection.detection_score
    assert result.detection_confidence == detection.detection_confidence
    assert result.confirmation_status == detection.confirmation_status

    assert len(result.semantic_evidence) == 1
    assert result.semantic_evidence[0].source == RetrievalSource.RAG_CHUNKS
