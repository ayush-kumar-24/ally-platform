"""Unit tests for the Ally Context Builder (Phase 5, Milestone 1).

Hermetic: a fake repository supplies stand-in ORM rows, so the builder's mapping
and grounding logic are exercised without a database.
"""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.api.v1.ally.context.builder import AllyContextBuilder
from app.api.v1.ally.context.errors import FounderNotFoundError
from app.api.v1.ally.context.schemas import ALLY_CONTEXT_SCHEMA_VERSION

D = Decimal
GEN_AT = datetime(2026, 7, 27, 12, 0, 0)


def founder(**kw):
    base = dict(founder_id=1, full_name="Asha Rao", stage_id=5, industry_mapped_id=3)
    base.update(kw)
    return SimpleNamespace(**base)


def report(**kw):
    base = dict(report_id=99, session_id=42, is_active=True, generated_at=GEN_AT,
                summary="fallback summary", session_state_at_generation="stable",
                insights={
                    "executive_summary": "Asha, your diagnosis is complete.",
                    "business_health_score": {
                        "overall_score": "68", "band": "Developing",
                        "pillars": [{"pillar_name": "Revenue Maturity", "score": "40", "red_flag_triggered": True}],
                        "red_flags": ["Revenue Maturity"],
                    },
                    "priority_actions": [
                        {"priority": 1, "action": "Interview 5 churned customers"},
                        {"priority": 2, "action": "Instrument activation funnel"},
                    ],
                    "next_steps": ["Book a strategy call", "Review pricing"],
                })
    base.update(kw)
    return SimpleNamespace(**base)


def session(**kw):
    base = dict(overall_confidence_score=D("72"), routing_state="validate",
                distress_mode_triggered=False, session_state="stable")
    base.update(kw)
    return SimpleNamespace(**base)


def detection(rcid, rank, top=True, status="unconfirmed", score="0.8"):
    return SimpleNamespace(root_cause_id=rcid, rank=rank, is_top_finding=top,
                           confirmation_status=status, final_weighted_score=D(score))


def rc(rcid, name, code="RC-X", category="Sales & Revenue"):
    return SimpleNamespace(root_cause_id=rcid, root_cause_name=name,
                           root_cause_code=code, category=category)


def internal(**kw):
    base = dict(psychological_state="stable", internal_notes="# Consultant report...",
                distress_signals=[{"category": "Founder Psychology", "severity": "0.7"}],
                blind_spot_ids=[3, 7])
    base.update(kw)
    return SimpleNamespace(**base)


class FakeRepo:
    def __init__(self, *, f=None, rep=None, sess=None, dets=None, rcs=None, intl=None,
                 stage=SimpleNamespace(stage_name="Growth / Scaling"),
                 industry=SimpleNamespace(industry_name="SaaS")):
        self._f, self._rep, self._sess = f, rep, sess
        self._dets, self._rcs, self._intl = dets or [], rcs or {}, intl
        self._stage, self._industry = stage, industry

    def get_founder(self, fid): return self._f
    def get_stage(self, sid): return self._stage
    def get_industry(self, iid): return self._industry
    def get_session(self, sid): return self._sess
    def get_latest_active_report(self, fid, session_id=None): return self._rep
    def get_detected_root_causes(self, sid): return self._dets
    def get_root_causes_by_ids(self, ids): return self._rcs
    def get_internal_report(self, sid): return self._intl


def full_repo(**over):
    cfg = dict(
        f=founder(), rep=report(), sess=session(),
        dets=[detection(10, 1), detection(20, 2, top=False, status="confirmed", score="0.5")],
        rcs={10: rc(10, "Weak activation", "RC-010"), 20: rc(20, "Pricing unclear", "RC-020")},
        intl=internal(),
    )
    cfg.update(over)
    return FakeRepo(**cfg)


# --- Happy path ------------------------------------------------------------


def test_full_context_is_answerable_and_grounded():
    ctx = AllyContextBuilder(full_repo()).build(1, session_id=42)
    assert ctx.is_answerable is True
    assert ctx.has_diagnosis is True
    assert ctx.report_id == 99 and ctx.generated_at == GEN_AT
    assert ctx.founder.full_name == "Asha Rao"
    assert ctx.founder.stage_name == "Growth / Scaling"
    assert ctx.founder.industry == "SaaS"
    assert ctx.diagnosis.overall_confidence == D("72")
    assert ctx.diagnosis.routing_state == "validate"
    assert ctx.diagnosis.executive_summary.startswith("Asha")
    assert ctx.diagnosis.priority_actions == ("Interview 5 churned customers", "Instrument activation funnel")
    assert ctx.diagnosis.next_steps == ("Book a strategy call", "Review pricing")


def test_root_causes_mapped_and_ordered_by_rank():
    ctx = AllyContextBuilder(full_repo()).build(1)
    assert [r.root_cause_id for r in ctx.root_causes] == [10, 20]
    assert ctx.root_causes[0].name == "Weak activation"
    assert ctx.root_causes[0].is_top_finding is True
    assert ctx.root_causes[1].confirmation_status == "confirmed"


def test_business_health_extracted_from_insights():
    ctx = AllyContextBuilder(full_repo()).build(1)
    assert ctx.business_health.overall_score == "68"
    assert ctx.business_health.band == "Developing"
    assert ctx.business_health.red_flags == ("Revenue Maturity",)
    assert ctx.business_health.pillars[0]["pillar_name"] == "Revenue Maturity"


def test_internal_intelligence_surfaced():
    ctx = AllyContextBuilder(full_repo()).build(1)
    assert ctx.internal_intelligence.psychological_state == "stable"
    assert ctx.internal_intelligence.blind_spot_ids == (3, 7)
    assert ctx.internal_intelligence.consultant_notes.startswith("# Consultant")


# --- Edge cases ------------------------------------------------------------


def test_schema_version_is_present_on_every_context():
    # Carried automatically on both answerable and non-answerable contexts.
    full = AllyContextBuilder(full_repo()).build(1)
    empty = AllyContextBuilder(FakeRepo(f=founder(), rep=None)).build(1)
    assert full.schema_version == ALLY_CONTEXT_SCHEMA_VERSION == "v1"
    assert empty.schema_version == "v1"


def test_no_report_is_valid_but_not_answerable():
    ctx = AllyContextBuilder(FakeRepo(f=founder(), rep=None)).build(1)
    assert ctx.has_diagnosis is False
    assert ctx.is_answerable is False
    assert ctx.root_causes == ()
    assert ctx.business_health is None and ctx.diagnosis is None
    assert ctx.founder.founder_id == 1  # profile still present


def test_missing_founder_raises():
    with pytest.raises(FounderNotFoundError):
        AllyContextBuilder(FakeRepo(f=None)).build(999)


def test_distress_is_surfaced_not_suppressed():
    ctx = AllyContextBuilder(full_repo(sess=session(distress_mode_triggered=True))).build(1)
    assert ctx.is_distress is True
    assert ctx.diagnosis.distress_mode is True


def test_root_cause_name_falls_back_when_lookup_missing():
    ctx = AllyContextBuilder(full_repo(rcs={})).build(1)  # names not resolvable
    assert ctx.root_causes[0].name == "RC-10"
    assert ctx.root_causes[0].code is None


def test_business_health_none_when_absent_from_report():
    r = report(insights={"executive_summary": "done"})  # no business_health_score
    ctx = AllyContextBuilder(full_repo(rep=r)).build(1)
    assert ctx.business_health is None
    assert ctx.diagnosis.executive_summary == "done"


def test_executive_summary_falls_back_to_report_summary():
    r = report(insights={})  # empty insights
    ctx = AllyContextBuilder(full_repo(rep=r)).build(1)
    assert ctx.diagnosis.executive_summary == "fallback summary"
    assert ctx.diagnosis.priority_actions == ()
    assert ctx.diagnosis.next_steps == ()
