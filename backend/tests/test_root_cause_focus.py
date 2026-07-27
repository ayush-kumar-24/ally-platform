"""Unit tests for root-cause detection focusing (score floor + candidate cap)."""

from decimal import Decimal
from types import SimpleNamespace

from app.api.v1.reasoning.engines.root_cause import StandardRootCauseEngine
from app.api.v1.reasoning.schemas import RootCauseDetection
from app.models.enums import ConfirmationStatus

D = Decimal


def det(rcid, conf, status=ConfirmationStatus.UNCONFIRMED):
    return RootCauseDetection(
        root_cause_id=rcid, category="Cat", confirmation_status=status,
        detection_score=D("0.5"), detection_confidence=D(str(conf)),
        evidence=(), contributing_factors=(), category_risk_score=D("0.5"),
    )


def ctx(floor="0.20", cap=8):
    branching = SimpleNamespace(root_cause_min_detection_confidence=D(floor),
                                root_cause_max_candidates=cap)
    return SimpleNamespace(config=SimpleNamespace(branching=branching))


def test_floor_drops_weakly_corroborated_causes():
    eng = StandardRootCauseEngine(repository=None)
    dets = [det(1, "0.50"), det(2, "0.08"), det(3, "0.30"), det(4, "0.05")]
    kept = eng._focus(dets, ctx(floor="0.20"))
    assert {d.root_cause_id for d in kept} == {1, 3}  # 0.08 and 0.05 dropped


def test_confirmed_cause_survives_the_floor():
    eng = StandardRootCauseEngine(repository=None)
    dets = [det(1, "0.05", ConfirmationStatus.CONFIRMED), det(2, "0.05")]
    kept = eng._focus(dets, ctx(floor="0.20"))
    assert {d.root_cause_id for d in kept} == {1}  # confirmed kept despite low conf


def test_candidate_cap_keeps_strongest_first():
    eng = StandardRootCauseEngine(repository=None)
    dets = [det(i, "0.90") for i in range(1, 13)]  # 12 above floor
    kept = eng._focus(dets, ctx(floor="0.20", cap=8))
    assert len(kept) == 8
    assert [d.root_cause_id for d in kept] == list(range(1, 9))  # order preserved


def test_zero_limits_disable_focusing():
    eng = StandardRootCauseEngine(repository=None)
    dets = [det(i, "0.01") for i in range(1, 21)]
    kept = eng._focus(dets, ctx(floor="0", cap=0))
    assert len(kept) == 20
