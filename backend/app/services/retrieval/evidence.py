"""Structured results returned by the Retrieval Engine.

Kept dependency-free (no engine, no reasoning imports) so any layer -- including
the reasoning DTOs -- can reference RetrievalEvidence without import cycles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class RetrievalSource(str, Enum):
    """The embedded tables the Retrieval Engine can search."""

    ROOT_CAUSES = "root_causes"
    PROBLEMS = "problems"
    QUESTIONS = "questions"
    AGENT_INTERPRETATIONS = "agent_interpretations"
    RAG_CHUNKS = "rag_chunks"


@dataclass(frozen=True)
class RetrievalEvidence:
    """One semantic neighbour found by cosine similarity search.

    `similarity` is cosine similarity in [-1, 1] (1 - cosine_distance); for the
    normalised gte-small vectors used here it is effectively [0, 1], higher =
    closer. `content` is the human-readable text of the matched row; `metadata`
    carries source-specific extras (category, linked ids, ...) for downstream use.
    """

    source: RetrievalSource
    source_id: int
    similarity: Decimal
    content: str
    metadata: dict = field(default_factory=dict)
