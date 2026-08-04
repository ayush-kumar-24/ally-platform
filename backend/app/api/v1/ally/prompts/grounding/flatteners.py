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

from app.api.v1.ally.context.schemas import AllyContext
from app.api.v1.ally.kg.schemas import GraphView
from app.api.v1.ally.memory.schemas import MemoryItem
from app.api.v1.ally.rag.schemas import RetrievalResult

_MAX_MEMORY = 6
_MAX_RETRIEVAL = 5
_MAX_GRAPH_LINES = 8
_CLAMP = 280
_DIAGNOSIS_SUMMARY_CLAMP = 600


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


def diagnosis_block(ctx: AllyContext | None) -> str:
    """Compact diagnosis summary for a GENERAL-purpose chat turn, where the
    diagnosis is supporting context rather than the entire answer. Returns ""
    when there is no diagnosis yet -- the variable assembler substitutes an
    absence sentinel, same convention as the other grounding blocks."""
    if ctx is None or not ctx.has_diagnosis or ctx.diagnosis is None:
        return ""
    d = ctx.diagnosis
    lines: list[str] = []
    if ctx.founder.stage_name:
        lines.append(f"Stage: {ctx.founder.stage_name}")
    if d.overall_confidence is not None:
        lines.append(f"Diagnostic confidence: {d.overall_confidence}/100")
    if d.executive_summary:
        lines.append(f"Summary: {_clamp(d.executive_summary, _DIAGNOSIS_SUMMARY_CLAMP)}")
    top = sorted((r for r in ctx.root_causes if r.is_top_finding), key=lambda r: r.rank)
    if top:
        lines.append(
            "Top root causes: "
            + "; ".join(f"{r.rank}. {r.name}" for r in top)
        )
    if ctx.business_health is not None and ctx.business_health.band:
        lines.append(f"Business health: {ctx.business_health.band}")
    return "\n".join(lines)


_MAX_ATTACHMENT_TEXT = 1500


def attachments_block(entries: tuple[tuple[str, str, int, str | None], ...]) -> str:
    """Format uploaded-file entries (filename, attachment_type, size_bytes,
    text_content_or_None) into a readable block. Files with extracted/decoded
    text (txt, csv, pdf, docx -- see ContextWindowBuilder._extract_text) get
    their content inlined and clamped; everything else (images; scanned PDFs
    with no text layer; extraction failures) is listed by name only, so the
    model is told a file exists without fabricating what's in it."""
    if not entries:
        return ""
    lines: list[str] = []
    for filename, attachment_type, size_bytes, text in entries:
        kb = max(1, size_bytes // 1024)
        if text:
            lines.append(
                f"- {filename} ({attachment_type}, {kb} KB):\n"
                f"{_clamp(text, _MAX_ATTACHMENT_TEXT)}"
            )
        else:
            lines.append(
                f"- {filename} ({attachment_type}, {kb} KB) -- uploaded, but its "
                "contents cannot be read yet; you only know it exists."
            )
    return "\n".join(lines)


def tasks_block(entries: tuple[tuple[str, str, str, object], ...]) -> str:
    """Format the founder's not-done Plan Your Day tasks (title, status, priority,
    due_date) into a readable block, so Ally can recognise when a message relates
    to something already on the founder's plan -- e.g. "finish the pitch deck" --
    without inventing tasks that were never actually created."""
    if not entries:
        return ""
    lines: list[str] = []
    for title, status, priority, due_date in entries:
        bits = [priority]
        if status == "in_progress":
            bits.append("in progress")
        if due_date:
            bits.append(f"due {due_date.isoformat()}")
        lines.append(f"- {title} ({', '.join(bits)})")
    return "\n".join(lines)
