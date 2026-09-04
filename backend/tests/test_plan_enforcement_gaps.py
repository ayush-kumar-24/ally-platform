"""The four enforcement gaps: call booking, streaming, meter failure, usage metrics."""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from app.credits import InMemoryCreditRepository, build_credit_service
from app.credits.expiry import CreditState
from app.plans import (
    InMemoryUsageRepository,
    NoFreeCallsRemainingError,
    PlanTier,
    build_entitlement_service,
    period_month,
)
from app.plans.reconciliation import (
    InMemoryReconciliationRepository,
    ReconciliationService,
    report_meter_failure,
)

T0 = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
UID = 1


def svc(balance=1000):
    usage = InMemoryUsageRepository()
    credits = build_credit_service(
        InMemoryCreditRepository({UID: CreditState(bonus=balance)}), clock=lambda: T0)
    return build_entitlement_service(usage, credit_service=credits, clock=lambda: T0), usage


# ── 1. free-call release ────────────────────────────────────────────────────


def test_release_returns_a_claimed_free_call():
    """A booking that fails after claiming must not eat the founder's allowance.

    Driven at the repository with an explicit allowance: no tier includes a free
    call today (booking is open to all and every call is paid), so there is no
    plan to claim one through. The release path is kept and tested because it is
    what stops a failed booking eating an allowance if one is ever reinstated.
    """
    _, usage = svc()
    assert usage.try_claim_free_call(UID, period_month(T0), 1, at=T0) is not None
    assert usage.get_calls(UID, period_month(T0)).free_calls_used == 1

    usage.release_free_call(UID, period_month(T0), at=T0)
    assert usage.get_calls(UID, period_month(T0)).free_calls_used == 0


def test_release_floors_at_zero():
    """A double release must not manufacture free calls out of nothing."""
    _, usage = svc()
    for _ in range(3):
        usage.release_free_call(UID, period_month(T0), at=T0)
    assert usage.get_calls(UID, period_month(T0)).free_calls_used == 0


def test_release_restores_exactly_one():
    _, usage = svc()
    for _ in range(2):
        assert usage.try_claim_free_call(UID, period_month(T0), 2, at=T0) is not None
    assert usage.get_calls(UID, period_month(T0)).free_calls_used == 2
    usage.release_free_call(UID, period_month(T0), at=T0)
    assert usage.get_calls(UID, period_month(T0)).free_calls_used == 1


def test_no_tier_can_claim_a_free_call():
    """Booking is open to everyone and every call is charged, so a claim must be
    refused on every tier -- with the price the founder will actually pay."""
    s, _ = svc()
    for tier in PlanTier:
        with pytest.raises(NoFreeCallsRemainingError) as exc:
            s.consume_free_call(UID, tier)
        assert exc.value.price == 300, tier


def test_concurrent_bookings_cannot_both_take_the_last_free_call():
    s, usage = svc()
    barrier = threading.Barrier(2)
    results = []

    def book():
        barrier.wait(timeout=5)
        # An explicit allowance of 1, not a tier: no plan includes a free call
        # today, and the race being guarded lives in the repository claim.
        results.append("free"
                       if usage.try_claim_free_call(UID, period_month(T0), 1, at=T0) is not None
                       else "paid")

    threads = [threading.Thread(target=book) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert sorted(results) == ["free", "paid"]
    assert usage.get_calls(UID, period_month(T0)).free_calls_used == 1


# ── 2. streaming meter ──────────────────────────────────────────────────────


def test_metered_stream_charges_after_completion():
    from app.api.v1.chat.router import metered_stream
    from app.api.v1.plans.dependencies import ChatGate

    s, usage = svc()
    gate = ChatGate(founder_id=UID, tier=PlanTier.PRO, service=s, enforced=True)

    class Usage:
        prompt_tokens, completion_tokens = 400, 600

    class Metrics:
        token_usage = Usage()

    class Event:
        metrics = Metrics()

    list(metered_stream(iter([Event(), Event()]), gate))
    assert usage.get_daily(UID, T0.date()).tokens_used == 1_000


def test_metered_stream_charges_even_if_client_disconnects():
    """Hanging up early must not be a free-usage loophole."""
    from app.api.v1.chat.router import metered_stream
    from app.api.v1.plans.dependencies import ChatGate

    s, usage = svc()
    gate = ChatGate(founder_id=UID, tier=PlanTier.PRO, service=s, enforced=True)

    class Usage:
        prompt_tokens, completion_tokens = 300, 200

    class Event:
        metrics = type("M", (), {"token_usage": Usage()})()

    stream = metered_stream(iter([Event(), Event(), Event()]), gate)
    next(stream)                       # consume one chunk...
    stream.close()                     # ...then abandon the stream

    assert usage.get_daily(UID, T0.date()).tokens_used == 500


def test_metered_stream_with_no_usage_charges_nothing():
    from app.api.v1.chat.router import metered_stream
    from app.api.v1.plans.dependencies import ChatGate

    s, usage = svc()
    gate = ChatGate(founder_id=UID, tier=PlanTier.PRO, service=s, enforced=True)
    list(metered_stream(iter([object(), object()]), gate))
    assert usage.get_daily(UID, T0.date()).tokens_used == 0


# ── 3. meter failure -> reconciliation ──────────────────────────────────────


def test_meter_failure_is_recorded_not_swallowed():
    from app.api.v1.plans.dependencies import ChatGate

    class Broken:
        def record_chat_usage(self, *a, **k):
            raise RuntimeError("meter down")

    recon = InMemoryReconciliationRepository()
    gate = ChatGate(founder_id=UID, tier="pro", service=Broken(), enforced=True,
                    reconciliation=recon)

    assert gate.record(2_500) is None            # user still gets their reply
    pending = recon.list_unresolved()
    assert len(pending) == 1
    assert pending[0].tokens == 2_500 and pending[0].credits_owed == 3
    assert "meter down" in pending[0].error


def test_first_diagnosis_failure_is_not_queued():
    """Nothing was owed, so there is nothing to reconcile."""
    from app.api.v1.plans.dependencies import ChatGate

    class Broken:
        def record_chat_usage(self, *a, **k):
            raise RuntimeError("boom")

    recon = InMemoryReconciliationRepository()
    gate = ChatGate(founder_id=UID, tier="free", service=Broken(), enforced=True,
                    reconciliation=recon)
    gate.record(3_000, is_first_diagnosis=True)
    assert recon.list_unresolved() == []


def test_report_meter_failure_never_raises_even_if_the_queue_is_broken():
    """This runs after a successful reply -- it must not be able to fail the request."""
    class BrokenStore:
        def record(self, **kwargs):
            raise RuntimeError("queue down")

    report_meter_failure(BrokenStore(), founder_id=UID, tokens=100, credits_owed=1,
                         source="chat", error=RuntimeError("original"))
    report_meter_failure(None, founder_id=UID, tokens=100, credits_owed=1,
                         source="chat", error=RuntimeError("original"))


def test_reconciliation_replay_charges_and_resolves():
    recon = InMemoryReconciliationRepository()
    recon.record(founder_id=UID, tokens=2_000, credits_owed=2, source="chat",
                 error="boom", at=T0)
    credits = build_credit_service(
        InMemoryCreditRepository({UID: CreditState(bonus=100)}), clock=lambda: T0)

    service = ReconciliationService(recon, credit_service=credits, clock=lambda: T0)
    assert service.pending() == {"entries": 1, "tokens": 2_000, "credits": 2}

    result = service.replay()
    assert result == {"attempted": 1, "resolved": 1, "failed": 0}
    assert credits.get_balance(UID).balance == 98        # charged
    assert service.pending()["entries"] == 0


def test_replay_leaves_failures_for_the_next_run():
    """One founder's failure must not block the rest of the backlog."""
    recon = InMemoryReconciliationRepository()
    recon.record(founder_id=UID, tokens=1_000, credits_owed=1, source="chat",
                 error="e", at=T0)
    recon.record(founder_id=999, tokens=1_000, credits_owed=1, source="chat",
                 error="e", at=T0)          # unknown founder -> will fail
    credits = build_credit_service(
        InMemoryCreditRepository({UID: CreditState(bonus=100)}), clock=lambda: T0)

    result = ReconciliationService(recon, credit_service=credits, clock=lambda: T0).replay()
    assert result["resolved"] == 1 and result["failed"] == 1
    assert len(recon.list_unresolved()) == 1            # retried next time


# ── 4. usage metrics ────────────────────────────────────────────────────────


def test_cost_estimation_scales_with_tokens():
    from app.admin.usage_metrics import estimate_cost_usd
    assert estimate_cost_usd(0) == 0.0
    assert estimate_cost_usd(1_000) > 0
    assert estimate_cost_usd(2_000) == pytest.approx(estimate_cost_usd(1_000) * 2)


def test_cost_basis_is_configurable(monkeypatch):
    from app.admin import usage_metrics
    monkeypatch.setenv("ALLY_BLENDED_COST_PER_1K", "0.01")
    assert usage_metrics.cost_per_1k() == 0.01
    assert usage_metrics.estimate_cost_usd(1_000) == pytest.approx(0.01)


def test_bad_cost_basis_falls_back_to_default(monkeypatch):
    from app.admin import usage_metrics
    monkeypatch.setenv("ALLY_BLENDED_COST_PER_1K", "not-a-number")
    assert usage_metrics.cost_per_1k() == usage_metrics.DEFAULT_COST_PER_1K_USD


def test_usage_summary_degrades_when_tables_are_missing():
    """A missing table must dim one number, not break the admin dashboard."""
    from app.admin.usage_metrics import UsageMetricsService

    class DeadDB:
        def execute(self, *a, **k):
            raise RuntimeError("relation does not exist")

        def rollback(self):
            pass

    s = UsageMetricsService(DeadDB(), clock=lambda: T0).summary(founder_id=UID)
    assert s.tokens_today == 0 and s.tokens_month == 0
    assert s.avg_tokens_per_request == 0.0
    assert s.estimated_cost_month_usd == 0.0
