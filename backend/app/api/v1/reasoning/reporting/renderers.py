"""Report renderers -- turn report DTOs into a target format.

Rendering is kept separate from generation: the ReportGenerator produces typed
DTOs, and a renderer projects them to a concrete surface. Two are provided:

  * DictReportRenderer   -> JSON-safe dict (for API responses / UI state).
  * MarkdownReportRenderer -> markdown text (human reading; a PDF step can render
                              the same markdown later).

Adding a PDF or HTML renderer later means implementing ReportRenderer against the
same DTOs -- no change to generation.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Protocol

from app.api.v1.reasoning.reporting.schemas import FounderReport, InternalReport


def _jsonable(value: Any) -> Any:
    """Recursively convert report DTOs to JSON-safe primitives.

    Decimals become strings (lossless, avoids float drift); enums become their
    value; dataclasses become dicts; tuples/lists/dicts recurse.
    """
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _jsonable(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return value


class ReportRenderer(Protocol):
    def render_founder(self, report: FounderReport) -> Any: ...
    def render_internal(self, report: InternalReport) -> Any: ...


class DictReportRenderer:
    """Renders a report to a JSON-safe dict, ready for an API or UI."""

    def render_founder(self, report: FounderReport) -> dict:
        return _jsonable(report)

    def render_internal(self, report: InternalReport) -> dict:
        return _jsonable(report)


class MarkdownReportRenderer:
    """Renders a report to markdown text."""

    def render_founder(self, report: FounderReport) -> str:
        lines: list[str] = []
        lines.append(f"# Diagnosis Report for {report.generated_for}")
        if report.distress_acknowledged:
            lines.append("> Wellbeing was flagged during this session and is "
                         "acknowledged before any business findings.")
        lines.append("")
        lines.append("## Executive Summary")
        lines.append(report.executive_summary)
        lines.append("")

        stage = report.founder_stage
        lines.append("## Founder Stage")
        lines.append(stage.narrative)
        lines.append("")

        health = report.business_health
        lines.append("## Business Health Snapshot")
        lines.append(health.headline)
        for cat in health.categories:
            flag = " (flagged)" if cat.is_flagged else ""
            lines.append(f"- {cat.category}: {cat.band.value}, risk {cat.risk}{flag}")
        lines.append("")

        bhs = report.business_health_score
        if bhs is not None:
            lines.append("## Business Health Score")
            lines.append(f"Overall: {bhs.overall_score}/100 ({bhs.band or 'n/a'})")
            for p in bhs.pillars:
                if p.score is None:
                    lines.append(f"- {p.pillar_name} (weight {p.weight}%): not assessed")
                else:
                    flag = " ⚠ red flag" if p.red_flag_triggered else ""
                    lines.append(
                        f"- {p.pillar_name} (weight {p.weight}%): {p.score}/100 "
                        f"[{p.band or 'n/a'}]{flag}"
                    )
            if bhs.red_flags:
                lines.append(f"Red flags: {', '.join(bhs.red_flags)}")
            lines.append("")

        lines.append("## Top Root Causes")
        if not report.top_root_causes:
            lines.append("- None identified.")
        for rc in report.top_root_causes:
            lines.append(
                f"{rc.rank}. {rc.label} [{rc.category}] "
                f"({rc.confirmation_status}, score {rc.confidence})"
            )
            for factor in rc.contributing_factors:
                lines.append(f"   - {factor}")
        lines.append("")

        lines.append("## Key Symptoms")
        if not report.key_symptoms:
            lines.append("- None detected.")
        for sym in report.key_symptoms:
            tag = " [distress]" if sym.is_distress else ""
            lines.append(f"- {sym.category} (severity {sym.severity}){tag}")
            for s in sym.symptoms:
                lines.append(f"   - {s}")
        lines.append("")

        lines.append("## Priority Actions")
        if not report.priority_actions:
            lines.append("- None.")
        for action in report.priority_actions:
            lines.append(
                f"{action.priority}. [{action.recommendation_type}] "
                f"{action.action} ({action.intervention_label})"
            )
        lines.append("")

        lines.append("## Recommended Interventions")
        for iv in report.recommended_interventions:
            section = f" - {iv.section}" if iv.section else ""
            lines.append(f"- {iv.label}{section} [{iv.recommendation_type}]")
        lines.append("")

        lines.append("## Next Steps")
        if not report.next_steps:
            lines.append("- None.")
        for step in report.next_steps:
            lines.append(f"- {step}")

        return "\n".join(lines)

    def render_internal(self, report: InternalReport) -> str:
        lines: list[str] = []
        cb = report.confidence_breakdown
        lines.append(f"# Internal Consultant Report (session {report.session_id})")
        lines.append("")
        lines.append("## Confidence Breakdown")
        lines.append(f"- Overall confidence: {cb.overall_confidence}")
        lines.append(f"- Routing: {cb.routing_state}")
        lines.append(f"- Top findings: {cb.top_finding_count}")
        lines.append(f"- Distress mode: {cb.distress_mode} ({cb.distress_signal_count} signals)")
        lines.append("")

        lines.append("## Scoring Audit")
        for s in report.scoring_audit:
            lines.append(
                f"- RC-{s.root_cause_id} rank {s.rank} score {s.final_weighted_score} "
                f"({s.confirmation_status}, x{s.confirmation_multiplier})"
                f"{' [top]' if s.is_top_finding else ''}"
            )
            for comp in s.components:
                avail = "" if comp.available else " (unavailable)"
                lines.append(
                    f"   - {comp.factor}: {comp.weight} x {comp.value} = "
                    f"{comp.contribution}{avail}"
                )
        lines.append("")

        lines.append("## Category Risk Analysis")
        for c in report.category_risk_analysis:
            lines.append(
                f"- {c.category}: {c.raw_score}/{c.max_score} = {c.normalised_risk}"
                f"{' (flagged)' if c.is_flagged else ''}"
            )
        lines.append("")

        stage = report.stage_detection
        lines.append("## Stage Probabilities")
        lines.append(
            f"- Stage {stage.stage_id} ({stage.stage_name}): "
            f"p={stage.probability}, confidence={stage.confidence}"
        )
        for e in stage.evidence:
            lines.append(f"   - {e}")
        lines.append("")

        lines.append("## Recommendation Rationale")
        for rec in report.recommendation_rationale:
            lines.append(
                f"- INT-{rec.intervention_id} (priority {rec.priority}, "
                f"{rec.recommendation_type}): {rec.rationale}"
            )
        lines.append("")

        lines.append("## Retrieval Evidence")
        if not report.retrieval_evidence:
            lines.append("- None (retrieval disabled or no hits).")
        for ev in report.retrieval_evidence:
            lines.append(f"- [{ev.source.value}#{ev.source_id}] sim={ev.similarity}: {ev.content}")
        lines.append("")

        lines.append("## LLM Reasoning")
        if not report.llm_reasoning:
            lines.append("- None (deterministic classification).")
        for r in report.llm_reasoning:
            lines.append(f"- {r.score_label.value} (conf {r.confidence}): {r.explanation}")
            for step in r.reasoning_steps:
                lines.append(f"   - {step}")
        lines.append("")

        lines.append("## Full Diagnostic Trace")
        for d in report.diagnostic_trace:
            lines.append(
                f"- RC-{d.root_cause_id} [{d.category}] detection={d.detection_score} "
                f"conf={d.detection_confidence} ({d.confirmation_status})"
            )
            for factor in d.contributing_factors:
                lines.append(f"   - {factor}")

        return "\n".join(lines)
