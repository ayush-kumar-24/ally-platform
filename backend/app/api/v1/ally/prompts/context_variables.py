"""Deterministic AllyContext -> template-variable flattener.

The single bridge from Milestone 1 into the prompt layer. It reads ONLY the
immutable AllyContext (never the database) and produces a flat dict of string
variables for interpolation.

Fail-closed contract: a variable is present in the returned dict ONLY when it has
a real value. Absent/None/empty values are OMITTED, never rendered as "" or a
placeholder default -- so the Manager can detect a missing required variable
rather than silently substituting nothing. Output is deterministic: stable
ordering, no timestamps, no randomness.
"""

from __future__ import annotations

from decimal import Decimal

from app.api.v1.ally.context.schemas import AllyContext


def _put(out: dict[str, str], key: str, value: object) -> None:
    if value is None:
        return
    text = str(value).strip()
    if text:
        out[key] = text


def _num(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def context_variables(context: AllyContext) -> dict[str, str]:
    out: dict[str, str] = {}
    _put(out, "schema_version", context.schema_version)

    f = context.founder
    _put(out, "founder_name", f.full_name)
    _put(out, "stage_name", f.stage_name)
    _put(out, "industry", f.industry)

    d = context.diagnosis
    if d is not None:
        _put(out, "overall_confidence", _num(d.overall_confidence))
        _put(out, "routing_state", d.routing_state)
        _put(out, "session_state", d.session_state)
        _put(out, "executive_summary", d.executive_summary)
        if d.priority_actions:
            _put(out, "priority_actions", "\n".join(f"- {a}" for a in d.priority_actions))
        if d.next_steps:
            _put(out, "next_steps", "\n".join(f"- {s}" for s in d.next_steps))

    top = [r for r in context.root_causes if r.is_top_finding]
    if top:
        _put(
            out,
            "top_root_causes",
            "; ".join(
                f"{r.rank}. {r.name}" + (f" [{r.category}]" if r.category else "")
                for r in top
            ),
        )

    bh = context.business_health
    if bh is not None:
        _put(out, "business_health_overall", bh.overall_score)
        _put(out, "business_health_band", bh.band)
        if bh.red_flags:
            _put(out, "business_health_red_flags", ", ".join(bh.red_flags))

    ii = context.internal_intelligence
    if ii is not None:
        # Consultant-only signal; available to internal templates, not founder ones.
        _put(out, "psychological_state", ii.psychological_state)

    return out
