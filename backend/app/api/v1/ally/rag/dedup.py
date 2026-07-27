"""Deduplication Layer -- collapse duplicate chunks, keep the best copy.

Two chunks are duplicates when they come from the same (source, source_id). Among
duplicates we keep the highest-quality source, then the highest similarity, then
the lowest chunk_id -- a total, deterministic order, so the survivor never depends
on input ordering. Runs BEFORE ranking so the ranker scores a unique set.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.api.v1.ally.rag.schemas import KnowledgeChunk


def _preference_key(chunk: KnowledgeChunk) -> tuple:
    # Higher is better for quality/similarity; lower chunk_id wins ties.
    return (chunk.source_quality, chunk.similarity, _neg_str(chunk.chunk_id))


def _neg_str(value: str):
    # Sort helper: we want the LOWEST chunk_id to win, so invert the comparison by
    # returning a key that sorts a smaller id as "greater" in the preference max().
    return tuple(-ord(c) for c in value)


def deduplicate(chunks: Iterable[KnowledgeChunk]) -> list[KnowledgeChunk]:
    best: dict[tuple[str, str], KnowledgeChunk] = {}
    for chunk in chunks:
        key = (chunk.source, str(chunk.source_id))
        current = best.get(key)
        if current is None or _preference_key(chunk) > _preference_key(current):
            best[key] = chunk
    # Deterministic output order, independent of dict insertion.
    return sorted(best.values(), key=lambda c: c.chunk_id)
