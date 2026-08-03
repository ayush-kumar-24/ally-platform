"""Plan catalog, entitlement gates, daily token meter and call allowances."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import pytest

from app.credits import InMemoryCreditRepository, build_credit_service
from app.credits.expiry import CreditState
from app.plans import (
    CALL_PRICE_INR,
    DailyTokenLimitError,
    Feature,
    FeatureNotInPlanError,
    InMemoryUsageRepository,
    NoFreeCallsRemainingError,
    OutOfCreditsError,
    PlanTier,
    all_plans,
    build_entitlement_service,
    credits_for_tokens,
    get_plan,
    period_month,
)

T0 = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
UID = 1


def svc(tier=PlanTier.FREE, balance=1000, now=T0):
    usage = InMemoryUsageRepository()
    credits = build_credit_service(
        InMemoryCreditRepository({UID: CreditState(bonus=balance)}), clock=lambda: now)
    return build_entitlement_service(usage, credit_service=credits, clock=lambda: now), usage


# ── catalog ─────────────────────────────────────────────────────────────────


def test_three_tiers_in_price_order():
    plans = all_plans()
    assert [p.tier for p in plans] == [PlanTier.FREE, PlanTier.STARTER, PlanTier.PRO]
    assert [p.price_inr for p in plans] == [0, 450, 999]


def test_credit_ladder_ascends():
    """Free's one-time grant must not out-number a paid monthly allowance, or the
    pricing page reads as though paying gives you less."""
    free, starter, pro = all_plans()
    assert free.signup_credits == 120 and free.monthly_credits == 0
    assert starter.monthly_credits == 180
    assert pro.monthly_credits == 240
    assert free.signup_credits < starter.monthly_credits < pro.monthly_credits


def test_daily_limits():
    free, starter, pro = all_plans()
    assert (free.daily_token_limit, starter.daily_token_limit, pro.daily_token_limit) \
        == (4_000, 6_000, 8_000)


def test_monthly_credits_are_reachable_under_the_daily_ceiling():
    """The whole point of the 'smaller tank' decision: nothing strands."""
    from app.plans import TOKENS_PER_CREDIT
    for plan in all_plans():
        if plan.monthly_credits:
            granted_tokens = plan.monthly_credits * TOKENS_PER_CREDIT
            assert granted_tokens <= plan.reachable_monthly_tokens, plan.name


def test_free_call_allowances():
    free, starter, pro = all_plans()
    assert (free.free_calls_per_month, starter.free_calls_per_month,
            pro.free_calls_per_month) == (0, 1, 2)


def test_unknown_tier_falls_back_to_free():
    """Fails closed -- a typo must not hand someone Pro."""
    assert get_plan("enterprise").tier is PlanTier.FREE
    assert get_plan(None).tier is PlanTier.FREE
    assert get_plan("").tier is PlanTier.FREE


@pytest.mark.parametrize("tokens,expected", [(0, 0), (1, 1), (999, 1), (1000, 1),
                                             (1001, 2), (5500, 6)])
def test_credits_round_up(tokens, expected):
    """Rounding down would make many small requests free."""
    assert credits_for_tokens(tokens) == expected


# ── feature gates ───────────────────────────────────────────────────────────


def test_everyone_gets_chat_diagnosis_and_voice_in_diagnosis():
    s, _ = svc()
    for tier in PlanTier:
        for feature in (Feature.ALLY_CHAT, Feature.DIAGNOSIS, Feature.VOICE_DIAGNOSIS,
                        Feature.CALL_BOOKING, Feature.FOUNDER_DNA, Feature.BUSINESS_DNA):
            assert s.has_feature(tier, feature), (tier, feature)


def test_voice_in_chat_is_paid_only():
    s, _ = svc()
    assert not s.has_feature(PlanTier.FREE, Feature.VOICE_CHAT)
    assert s.has_feature(PlanTier.STARTER, Feature.VOICE_CHAT)
    assert s.has_feature(PlanTier.PRO, Feature.VOICE_CHAT)


def test_plan_your_day_is_paid_only():
    s, _ = svc()
    assert not s.has_feature(PlanTier.FREE, Feature.PLAN_YOUR_DAY)
    assert s.has_feature(PlanTier.STARTER, Feature.PLAN_YOUR_DAY)


def test_know_my_energy_is_pro_only():
    s, _ = svc()
    assert not s.has_feature(PlanTier.FREE, Feature.KNOW_MY_ENERGY)
    assert not s.has_feature(PlanTier.STARTER, Feature.KNOW_MY_ENERGY)
    assert s.has_feature(PlanTier.PRO, Feature.KNOW_MY_ENERGY)


def test_require_feature_names_the_upgrade():
    s, _ = svc()
    with pytest.raises(FeatureNotInPlanError) as exc:
        s.require_feature(PlanTier.FREE, Feature.PLAN_YOUR_DAY)
    assert exc.value.required_plan == "Starter"
    with pytest.raises(FeatureNotInPlanError) as exc:
        s.require_feature(PlanTier.STARTER, Feature.KNOW_MY_ENERGY)
    assert exc.value.required_plan == "Pro"


# ── chat gate ordering ──────────────────────────────────────────────────────


def test_free_user_blocked_from_voice_chat_with_403_not_429():
    """Order matters: telling a Free user 'out of tokens' would be useless, since
    tomorrow's reset still would not let them use voice."""
    s, usage = svc(PlanTier.FREE)
    usage.add_tokens(UID, T0.date(), 99_999, at=T0)      # also over the daily cap
    with pytest.raises(FeatureNotInPlanError):
        s.check_chat_allowed(UID, PlanTier.FREE, voice=True)


def test_daily_limit_blocks_before_credits():
    s, usage = svc(PlanTier.FREE, balance=0)
    usage.add_tokens(UID, T0.date(), 4_000, at=T0)
    with pytest.raises(DailyTokenLimitError):
        s.check_chat_allowed(UID, PlanTier.FREE)


def test_out_of_credits_blocks():
    s, _ = svc(PlanTier.FREE, balance=0)
    with pytest.raises(OutOfCreditsError):
        s.check_chat_allowed(UID, PlanTier.FREE)


def test_allowed_when_under_all_limits():
    s, _ = svc(PlanTier.STARTER, balance=50)
    s.check_chat_allowed(UID, PlanTier.STARTER, voice=True)     # no raise


def test_first_diagnosis_bypasses_credits_and_daily_limit():
    """It is the hook -- a founder must never hit a paywall midway through it."""
    s, usage = svc(PlanTier.FREE, balance=0)
    usage.add_tokens(UID, T0.date(), 999_999, at=T0)
    s.check_chat_allowed(UID, PlanTier.FREE, is_first_diagnosis=True)   # no raise


# ── metering / charging ─────────────────────────────────────────────────────


def test_usage_records_tokens_and_charges_credits():
    s, usage = svc(PlanTier.STARTER, balance=100)
    result = s.record_chat_usage(UID, PlanTier.STARTER, tokens=2_500)
    assert result["tokens_used"] == 2_500
    assert result["credits_charged"] == 3                    # 2,500 -> 3 credits
    assert result["daily_used"] == 2_500
    assert result["daily_remaining"] == 3_500                # 6,000 - 2,500
    assert usage.get_daily(UID, T0.date()).tokens_used == 2_500


def test_first_diagnosis_records_tokens_but_charges_nothing():
    s, usage = svc(PlanTier.FREE, balance=100)
    result = s.record_chat_usage(UID, PlanTier.FREE, tokens=3_000, is_first_diagnosis=True)
    assert result["credits_charged"] == 0
    assert usage.get_daily(UID, T0.date()).tokens_used == 3_000   # ceiling still protected


def test_usage_accumulates_within_a_day():
    s, _ = svc(PlanTier.PRO, balance=1000)
    s.record_chat_usage(UID, PlanTier.PRO, tokens=1_000)
    result = s.record_chat_usage(UID, PlanTier.PRO, tokens=2_000)
    assert result["daily_used"] == 3_000 and result["daily_remaining"] == 5_000


def test_a_new_day_is_a_new_key_not_a_reset():
    """Yesterday's row survives; today simply starts at zero."""
    usage = InMemoryUsageRepository()
    usage.add_tokens(UID, date(2026, 8, 1), 4_000, at=T0)
    assert usage.get_daily(UID, date(2026, 8, 1)).tokens_used == 4_000
    assert usage.get_daily(UID, date(2026, 8, 2)).tokens_used == 0


# ── calls ───────────────────────────────────────────────────────────────────


def test_free_user_always_pays_for_calls():
    s, _ = svc(PlanTier.FREE)
    q = s.quote_call(UID, PlanTier.FREE)
    assert q.is_free is False and q.price_inr == CALL_PRICE_INR and q.free_remaining == 0
    with pytest.raises(NoFreeCallsRemainingError):
        s.consume_free_call(UID, PlanTier.FREE)


def test_starter_gets_one_free_call_then_pays():
    s, _ = svc(PlanTier.STARTER)
    assert s.quote_call(UID, PlanTier.STARTER).is_free is True
    s.consume_free_call(UID, PlanTier.STARTER)
    after = s.quote_call(UID, PlanTier.STARTER)
    assert after.is_free is False and after.price_inr == CALL_PRICE_INR
    with pytest.raises(NoFreeCallsRemainingError):
        s.consume_free_call(UID, PlanTier.STARTER)


def test_pro_gets_two_free_calls():
    s, _ = svc(PlanTier.PRO)
    s.consume_free_call(UID, PlanTier.PRO)
    assert s.quote_call(UID, PlanTier.PRO).is_free is True      # second still free
    s.consume_free_call(UID, PlanTier.PRO)
    assert s.quote_call(UID, PlanTier.PRO).is_free is False


def test_free_calls_reset_next_month():
    usage = InMemoryUsageRepository()
    august = build_entitlement_service(usage, clock=lambda: T0)
    august.consume_free_call(UID, PlanTier.STARTER)
    assert august.quote_call(UID, PlanTier.STARTER).is_free is False

    september = build_entitlement_service(usage, clock=lambda: T0 + timedelta(days=31))
    assert september.quote_call(UID, PlanTier.STARTER).is_free is True


def test_period_month_key():
    assert period_month(datetime(2026, 8, 2, tzinfo=timezone.utc)) == "2026-08"
    assert period_month(datetime(2026, 12, 31, tzinfo=timezone.utc)) == "2026-12"


# ── summary ─────────────────────────────────────────────────────────────────


def test_entitlements_summary():
    s, usage = svc(PlanTier.PRO, balance=240)
    usage.add_tokens(UID, T0.date(), 1_000, at=T0)
    s.consume_free_call(UID, PlanTier.PRO)
    e = s.entitlements(UID, PlanTier.PRO)
    assert e.plan_name == "Pro" and e.credits_balance == 240
    assert e.daily_token_limit == 8_000 and e.daily_tokens_remaining == 7_000
    assert e.free_calls_allowance == 2 and e.free_calls_remaining == 1
    assert "know_my_energy" in e.features


# ── concurrency ─────────────────────────────────────────────────────────────


def test_concurrent_token_recording_does_not_lose_counts():
    s, usage = svc(PlanTier.PRO, balance=100_000)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: s.record_chat_usage(UID, PlanTier.PRO, tokens=100),
                      range(40)))

    assert usage.get_daily(UID, T0.date()).tokens_used == 4_000


def test_concurrent_free_call_claims_do_not_exceed_allowance():
    s, _ = svc(PlanTier.PRO)
    claimed, refused = [], []

    def claim(_):
        try:
            s.consume_free_call(UID, PlanTier.PRO)
            claimed.append(1)
        except NoFreeCallsRemainingError:
            refused.append(1)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(claim, range(15)))

    assert len(claimed) == 2 and len(refused) == 13


def test_free_call_claim_is_atomic_under_forced_interleaving():
    """Threads alone rarely hit the window, so force it.

    A repository that reads the count, yields, then increments is the check-then-act
    bug this guards against: both callers would see "1 remaining" and both claim the
    last free call. The claim must be one indivisible operation.
    """
    import threading
    from app.plans.usage import InMemoryUsageRepository

    barrier = threading.Barrier(2)

    class SlowRepo(InMemoryUsageRepository):
        def try_claim_free_call(self, founder_id, period, allowance, *, at):
            barrier.wait(timeout=5)      # both threads arrive together
            return super().try_claim_free_call(founder_id, period, allowance, at=at)

    repo = SlowRepo()
    s = build_entitlement_service(repo, clock=lambda: T0)
    results = []

    def claim():
        try:
            s.consume_free_call(UID, PlanTier.STARTER)     # allowance of exactly 1
            results.append("claimed")
        except NoFreeCallsRemainingError:
            results.append("refused")

    threads = [threading.Thread(target=claim) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert sorted(results) == ["claimed", "refused"]
    assert repo.get_calls(UID, period_month(T0)).free_calls_used == 1


# ── rollout flag ────────────────────────────────────────────────────────────


def test_enforcement_is_off_by_default():
    """The gate ships dormant: its storage tables do not exist until the blocked
    migrations run, so enabling it early would 500 every chat request."""
    import os
    from app.api.v1.plans.dependencies import enforcement_enabled
    os.environ.pop("PLAN_ENFORCEMENT_ENABLED", None)
    assert enforcement_enabled() is False


@pytest.mark.parametrize("value,expected", [("1", True), ("true", True), ("YES", True),
                                            ("0", False), ("", False), ("off", False)])
def test_enforcement_flag_parsing(value, expected, monkeypatch):
    from app.api.v1.plans.dependencies import enforcement_enabled
    monkeypatch.setenv("PLAN_ENFORCEMENT_ENABLED", value)
    assert enforcement_enabled() is expected


def test_disabled_gate_is_a_pass_through_that_charges_nothing():
    from app.api.v1.plans.dependencies import ChatGate
    gate = ChatGate(founder_id=UID, tier="free", service=None, enforced=False)
    assert gate.record(5_000) is None
    gate.require_voice()                      # must not raise while dormant


def test_enabled_gate_charges_and_meters():
    from app.api.v1.plans.dependencies import ChatGate
    s, usage = svc(PlanTier.STARTER, balance=100)
    gate = ChatGate(founder_id=UID, tier=PlanTier.STARTER, service=s, enforced=True)
    result = gate.record(2_500)
    assert result["credits_charged"] == 3
    assert usage.get_daily(UID, T0.date()).tokens_used == 2_500


def test_enabled_gate_enforces_voice():
    from app.api.v1.plans.dependencies import ChatGate
    s, _ = svc(PlanTier.FREE)
    with pytest.raises(FeatureNotInPlanError):
        ChatGate(founder_id=UID, tier=PlanTier.FREE, service=s, enforced=True).require_voice()
    # paid tier passes
    ChatGate(founder_id=UID, tier=PlanTier.PRO, service=s, enforced=True).require_voice()


def test_metering_failure_does_not_fail_the_users_request():
    """The reply already exists and provider tokens are already spent -- a broken
    counter must not turn a successful answer into an error for the founder."""
    from app.api.v1.plans.dependencies import ChatGate

    class Broken:
        def record_chat_usage(self, *a, **k):
            raise RuntimeError("meter down")

    gate = ChatGate(founder_id=UID, tier="pro", service=Broken(), enforced=True)
    assert gate.record(1_000) is None          # swallowed, not raised
