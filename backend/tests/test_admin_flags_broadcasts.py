"""Feature flags and broadcasts."""

from datetime import datetime, timedelta, timezone

import pytest

from app.admin.broadcasts import (
    Audience,
    InvalidBroadcastError,
    Severity,
    build_broadcast_service,
)
from app.admin.feature_flags import (
    InMemoryFeatureFlagRepository,
    build_feature_flag_service,
)

T0 = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)


# ── Feature flags ───────────────────────────────────────────────────────────


def flags(initial=None):
    return build_feature_flag_service(
        InMemoryFeatureFlagRepository(initial or {}), clock=lambda: T0)


def test_unknown_flag_is_off():
    """Fails closed — a typo must never enable a feature."""
    assert flags().is_enabled("does_not_exist") is False


def test_unknown_flag_honours_explicit_default():
    assert flags().is_enabled("missing", default=True) is True


def test_global_flag():
    s = flags({"enable_gpt": True, "enable_voice": False})
    assert s.is_enabled("enable_gpt") is True
    assert s.is_enabled("enable_voice") is False


def test_per_user_override_beats_global():
    s = flags({"beta": False})
    s.set_override("beta", 7, enabled=True)
    assert s.is_enabled("beta", founder_id=7) is True
    assert s.is_enabled("beta", founder_id=8) is False        # others unaffected
    assert s.is_enabled("beta") is False                      # global unchanged


def test_override_can_disable_for_one_user():
    s = flags({"enable_claude": True})
    s.set_override("enable_claude", 7, enabled=False)
    assert s.is_enabled("enable_claude", founder_id=7) is False
    assert s.is_enabled("enable_claude", founder_id=9) is True


def test_clearing_override_falls_back_to_global():
    s = flags({"beta": False})
    s.set_override("beta", 7, enabled=True)
    s.set_override("beta", 7, enabled=None)
    assert s.is_enabled("beta", founder_id=7) is False


def test_set_flag_creates_and_updates():
    s = flags()
    s.set_flag("new_flag", enabled=True, description="d", admin_id=1)
    assert s.is_enabled("new_flag") is True
    s.set_flag("new_flag", enabled=False, admin_id=1)
    assert s.is_enabled("new_flag") is False


def test_flags_for_founder_merges_overrides():
    s = flags({"a": True, "b": False})
    s.set_override("b", 5, enabled=True)
    assert s.flags_for_founder(5) == {"a": True, "b": True}
    assert s.flags_for_founder(6) == {"a": True, "b": False}


# ── Broadcasts ──────────────────────────────────────────────────────────────


def casts(now=T0):
    from itertools import count
    c = count(1)
    return build_broadcast_service(clock=lambda: now, id_factory=lambda: f"b-{next(c)}")


def test_create_and_list():
    s = casts()
    b = s.create(admin_id=1, title="Maintenance", body="Down 2am–3am",
                 severity=Severity.WARNING)
    assert b.title == "Maintenance" and b.severity is Severity.WARNING and b.active
    assert len(s.list_all()) == 1


@pytest.mark.parametrize("kwargs", [
    {"title": "  ", "body": "x"},
    {"title": "x", "body": "  "},
    {"title": "x" * 201, "body": "y"},
])
def test_validation(kwargs):
    with pytest.raises(InvalidBroadcastError):
        casts().create(admin_id=1, **kwargs)


def test_plan_audience_requires_a_plan():
    with pytest.raises(InvalidBroadcastError):
        casts().create(admin_id=1, title="t", body="b", audience=Audience.PLAN)


def test_end_before_start_rejected():
    with pytest.raises(InvalidBroadcastError):
        casts().create(admin_id=1, title="t", body="b",
                       starts_at=T0, ends_at=T0 - timedelta(hours=1))


def test_targets_all():
    b = casts().create(admin_id=1, title="t", body="b")
    assert b.targets(plan="pro", status="active") is True
    assert b.targets(plan=None, status=None) is True


def test_targets_plan():
    b = casts().create(admin_id=1, title="t", body="b", audience=Audience.PLAN,
                       audience_plan="pro")
    assert b.targets(plan="pro", status="active") is True
    assert b.targets(plan="free", status="active") is False


def test_targets_status():
    b = casts().create(admin_id=1, title="t", body="b", audience=Audience.SUSPENDED)
    assert b.targets(plan=None, status="suspended") is True
    assert b.targets(plan=None, status="active") is False


def test_schedule_window():
    s = casts()
    future = s.create(admin_id=1, title="t", body="b", starts_at=T0 + timedelta(hours=1))
    past = s.create(admin_id=1, title="t", body="b", ends_at=T0 - timedelta(hours=1))
    live = s.create(admin_id=1, title="t", body="b")
    assert future.is_live(T0) is False        # not started
    assert past.is_live(T0) is False          # already ended
    assert live.is_live(T0) is True


def test_for_founder_filters_and_hides_read():
    s = casts()
    s.create(admin_id=1, title="everyone", body="b")
    s.create(admin_id=1, title="pro only", body="b", audience=Audience.PLAN,
             audience_plan="pro")
    free = [b.title for b in s.for_founder(1, plan="free", status="active")]
    pro = [b.title for b in s.for_founder(2, plan="pro", status="active")]
    assert free == ["everyone"]
    assert sorted(pro) == ["everyone", "pro only"]

    seen = s.for_founder(1, plan="free", status="active")[0]
    s.mark_read(seen.broadcast_id, 1)
    assert s.for_founder(1, plan="free", status="active") == []


def test_mark_read_is_idempotent():
    s = casts()
    b = s.create(admin_id=1, title="t", body="b")
    s.mark_read(b.broadcast_id, 1)
    s.mark_read(b.broadcast_id, 1)
    assert s.for_founder(1) == []


def test_deactivate_removes_from_delivery():
    s = casts()
    b = s.create(admin_id=1, title="t", body="b")
    s.deactivate(b.broadcast_id)
    assert s.for_founder(1) == []
    assert len(s.list_all(include_inactive=True)) == 1     # retained for the record
