"""Context Builder -- assembles AllyContext from persisted diagnosis outputs.

Read-only and additive: it maps the frozen tables into typed context DTOs and
recomputes nothing. A founder with no active report yields a valid, NOT-answerable
context (has_diagnosis=False) rather than an error -- the AI layer decides how to
respond to "no diagnosis yet"; the builder only reports the truth.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy.orm import Session

from app.api.v1.ally.context.errors import FounderNotFoundError
from app.api.v1.ally.context.repository import AllyContextRepository
from app.api.v1.ally.context.schemas import (
    AllyContext,
    BusinessHealthContext,
    DiagnosisContext,
    FounderProfileContext,
    InternalIntelligenceContext,
    RootCauseContext,
)


class AllyContextBuilder:
    def __init__(self, repository: AllyContextRepository):
        self.repository = repository

    def build(self, founder_id: int, session_id: int | None = None) -> AllyContext:
        founder = self.repository.get_founder(founder_id)
        if founder is None:
            raise FounderNotFoundError()

        profile = self._profile(founder)

        report = self.repository.get_latest_active_report(founder_id, session_id)
        if report is None:
            # Valid context, just nothing to ground on yet.
            return AllyContext(founder=profile, has_diagnosis=False)

        session = self.repository.get_session(report.session_id)
        insights: Mapping[str, Any] = report.insights or {}

        detections = self.repository.get_detected_root_causes(report.session_id)
        rc_names = self.repository.get_root_causes_by_ids(
            d.root_cause_id for d in detections
        )
        internal = self.repository.get_internal_report(report.session_id)

        return AllyContext(
            founder=profile,
            has_diagnosis=True,
            diagnosis=self._diagnosis(report, session, insights),
            root_causes=self._root_causes(detections, rc_names),
            business_health=self._business_health(insights),
            internal_intelligence=self._internal(internal),
            report_id=report.report_id,
            generated_at=report.generated_at,
        )

    # --- Mappers ----------------------------------------------------------

    def _profile(self, founder) -> FounderProfileContext:
        stage = self.repository.get_stage(getattr(founder, "stage_id", None))
        industry = self.repository.get_industry(getattr(founder, "industry_mapped_id", None))
        return FounderProfileContext(
            founder_id=founder.founder_id,
            full_name=getattr(founder, "full_name", None),
            stage_id=getattr(founder, "stage_id", None),
            stage_name=getattr(stage, "stage_name", None) if stage else None,
            industry=getattr(industry, "industry_name", None) if industry else None,
        )

    def _diagnosis(self, report, session, insights: Mapping[str, Any]) -> DiagnosisContext:
        return DiagnosisContext(
            session_id=report.session_id,
            overall_confidence=getattr(session, "overall_confidence_score", None) if session else None,
            routing_state=getattr(session, "routing_state", None) if session else None,
            distress_mode=bool(getattr(session, "distress_mode_triggered", False)) if session else False,
            session_state=(
                getattr(session, "session_state", None) if session
                else report.session_state_at_generation
            ),
            executive_summary=insights.get("executive_summary") or report.summary,
            priority_actions=self._action_strings(insights.get("priority_actions")),
            next_steps=tuple(insights.get("next_steps") or ()),
        )

    def _action_strings(self, actions) -> tuple[str, ...]:
        if not isinstance(actions, Sequence):
            return ()
        out: list[str] = []
        for a in actions:
            if isinstance(a, Mapping):
                text = a.get("action") or a.get("rationale")
                if text:
                    out.append(str(text))
            elif a:
                out.append(str(a))
        return tuple(out)

    def _root_causes(self, detections, rc_names) -> tuple[RootCauseContext, ...]:
        out: list[RootCauseContext] = []
        for d in detections:
            rc = rc_names.get(d.root_cause_id)
            out.append(
                RootCauseContext(
                    root_cause_id=d.root_cause_id,
                    code=getattr(rc, "root_cause_code", None) if rc else None,
                    name=getattr(rc, "root_cause_name", None) if rc else f"RC-{d.root_cause_id}",
                    category=getattr(rc, "category", None) if rc else None,
                    rank=d.rank,
                    confirmation_status=d.confirmation_status,
                    weighted_score=d.final_weighted_score,
                    is_top_finding=bool(d.is_top_finding),
                )
            )
        return tuple(out)

    def _business_health(self, insights: Mapping[str, Any]) -> BusinessHealthContext | None:
        bhs = insights.get("business_health_score")
        if not isinstance(bhs, Mapping):
            return None
        pillars = bhs.get("pillars")
        red_flags = bhs.get("red_flags")
        return BusinessHealthContext(
            overall_score=bhs.get("overall_score"),
            band=bhs.get("band"),
            pillars=tuple(p for p in pillars if isinstance(p, Mapping)) if isinstance(pillars, Sequence) else (),
            red_flags=tuple(str(r) for r in red_flags) if isinstance(red_flags, Sequence) else (),
        )

    def _internal(self, internal) -> InternalIntelligenceContext | None:
        if internal is None:
            return None
        signals = getattr(internal, "distress_signals", None)
        blind = getattr(internal, "blind_spot_ids", None)
        return InternalIntelligenceContext(
            psychological_state=getattr(internal, "psychological_state", None),
            distress_signals=tuple(s for s in signals if isinstance(s, Mapping)) if isinstance(signals, Sequence) else (),
            consultant_notes=getattr(internal, "internal_notes", None),
            blind_spot_ids=tuple(int(b) for b in blind) if isinstance(blind, Sequence) else (),
        )


def build_ally_context(db: Session, founder_id: int, session_id: int | None = None) -> AllyContext:
    """Convenience factory: build a context in one call from a DB session."""
    return AllyContextBuilder(AllyContextRepository(db)).build(founder_id, session_id)
