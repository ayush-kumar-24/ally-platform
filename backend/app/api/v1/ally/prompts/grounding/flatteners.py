"""Deterministic, read-only flatteners: subsystem DTOs -> grounding text blocks.

Each function turns one grounding source (M6 memory, M3 retrieval, M4 graph) into a
compact, human-readable block for the prompt. Strictly read-only -- it consumes the
frozen DTOs and NEVER calls into or mutates Memory / Retrieval / Knowledge Graph.

Determinism: stable sort keys, bounded size, whitespace-normalised content, no
timestamps or randomness. Fail-closed: returns "" when there is nothing to say (the
variable assembler substitutes an explicit absence sentinel), so nothing is ever
fabricated.
"""

from __future__ import annotations

from app.api.v1.ally.kg.schemas import GraphView
from app.api.v1.ally.memory.schemas import MemoryItem
from app.api.v1.ally.rag.schemas import RetrievalResult

_MAX_MEMORY = 6
_MAX_RETRIEVAL = 5
_MAX_GRAPH_LINES = 8
_CLAMP = 280


def _clamp(text: str, limit: int = _CLAMP) -> str:
    collapsed = " ".join((text or "").split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1].rstrip() + "…"


def memory_summary(items: tuple[MemoryItem, ...]) -> str:
    """Most-important active memories first (importance desc, then memory_id for a
    stable tiebreak)."""
    active = [m for m in items if m.is_active]
    if not active:
        return ""
    ordered = sorted(active, key=lambda m: (-m.metadata.importance, m.memory_id))[:_MAX_MEMORY]
    return "\n".join(
        f"- ({m.memory_type.value}, importance {m.metadata.importance}) {_clamp(m.content)}"
        for m in ordered
    )


def retrieved_knowledge(result: RetrievalResult | None) -> str:
    """Ranked retrieved chunks in rank order (the Ranker already ordered them)."""
    if result is None or result.is_empty:
        return ""
    ordered = sorted(result.items, key=lambda k: k.rank)[:_MAX_RETRIEVAL]
    return "\n".join(f"- [{k.rank}] {k.chunk.source}: {_clamp(k.chunk.content)}" for k in ordered)


def graph_expansion(graph: GraphView | None) -> str:
    """Edges as readable relationships (source label -> relationship -> target
    label). Falls back to a node listing when the subgraph has nodes but no edges.
    Node/edge order is already deterministic from the traversal."""
    if graph is None or graph.is_empty:
        return ""
    labels = {n.node_id: n.label for n in graph.nodes}
    lines = [
        f"- {labels.get(e.source, e.source)} —[{e.relationship.value.replace('_', ' ')}]→ "
        f"{labels.get(e.target, e.target)}"
        for e in graph.edges[:_MAX_GRAPH_LINES]
    ]
    if not lines:
        lines = [f"- {n.node_type.value}: {n.label}" for n in graph.nodes[:_MAX_GRAPH_LINES]]
    return "\n".join(lines)
