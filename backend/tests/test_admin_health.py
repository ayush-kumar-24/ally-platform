"""Admin Panel Proposal, gap #3: "Health is invisible."

    If the database, the AI provider or report generation breaks, we find
    out from a customer.

`GET /api/v1/health` already existed but only checked database + PDF
renderer, for App Runner's own routing, and was never shown in the panel.
These tests cover the richer, panel-facing check: database, AI provider,
report engine, storage, error rate -- and the alert that fires once when any
of them turns red.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.admin.health import (
    ERROR_RATE_AMBER,
    ERROR_RATE_RED,
    ComponentHealth,
    EmailAlertChannel,
    HealthAlertService,
    HealthReport,
    HealthStatus,
    SystemHealthChecker,
    overall_status,
)

NOW = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)


# --- a scriptable DB stand-in ------------------------------------------------

class FakeDb:
    def __init__(self, *, select_1_ok=True, error_rate_row=None, raise_on_error_rate=False):
        self.select_1_ok = select_1_ok
        self.error_rate_row = error_rate_row or {"errors": 0, "total": 0}
        self.raise_on_error_rate = raise_on_error_rate
        self.rolled_back = False

    def execute(self, clause, params=None):
        sql = str(clause)
        if "llm_call_log" in sql:
            if self.raise_on_error_rate:
                raise RuntimeError("simulated: llm_call_log unavailable")
            return _MappingResult(self.error_rate_row)
        # the SELECT 1 database check
        if not self.select_1_ok:
            raise RuntimeError("simulated: database unreachable")
        return None

    def rollback(self):
        self.rolled_back = True


class _MappingResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


def _checker(db=None, **overrides) -> SystemHealthChecker:
    return SystemHealthChecker(db or FakeDb(), clock=lambda: NOW, **overrides)


def _find(report: HealthReport, key: str) -> ComponentHealth:
    return next(c for c in report.components if c.key == key)


# --- overall_status: worst-of, not an average -------------------------------

def test_all_green_is_green():
    components = [ComponentHealth("a", "A", HealthStatus.GREEN),
                 ComponentHealth("b", "B", HealthStatus.GREEN)]
    assert overall_status(components) is HealthStatus.GREEN


def test_one_amber_makes_the_whole_report_amber():
    components = [ComponentHealth("a", "A", HealthStatus.GREEN),
                 ComponentHealth("b", "B", HealthStatus.AMBER)]
    assert overall_status(components) is HealthStatus.AMBER


def test_one_red_wins_over_everything_else():
    components = [ComponentHealth("a", "A", HealthStatus.RED),
                 ComponentHealth("b", "B", HealthStatus.GREEN),
                 ComponentHealth("c", "C", HealthStatus.AMBER)]
    assert overall_status(components) is HealthStatus.RED


# --- database ----------------------------------------------------------------

def test_database_green_when_select_1_succeeds():
    report = _checker(FakeDb(select_1_ok=True)).check()
    assert _find(report, "database").status is HealthStatus.GREEN


def test_database_red_and_rolls_back_when_unreachable():
    db = FakeDb(select_1_ok=False)
    report = _checker(db).check()
    assert _find(report, "database").status is HealthStatus.RED
    assert db.rolled_back is True


# --- AI provider ---------------------------------------------------------

def test_ai_provider_not_configured_is_amber_not_a_crash():
    report = _checker(ai_provider_health=None).check()
    ai = _find(report, "ai_provider")
    assert ai.status is HealthStatus.AMBER
    assert "not configured" in ai.detail


def test_ai_provider_healthy_is_green():
    report = _checker(ai_provider_health=lambda: (True, "auto healthy via claude")).check()
    assert _find(report, "ai_provider").status is HealthStatus.GREEN


def test_ai_provider_unhealthy_is_red():
    report = _checker(ai_provider_health=lambda: (False, "all providers unhealthy")).check()
    ai = _find(report, "ai_provider")
    assert ai.status is HealthStatus.RED
    assert "unhealthy" in ai.detail


def test_ai_provider_check_raising_is_red_not_a_500():
    def boom():
        raise RuntimeError("provider registry exploded")
    report = _checker(ai_provider_health=boom).check()
    assert _find(report, "ai_provider").status is HealthStatus.RED


# --- report engine -------------------------------------------------------

def test_report_engine_not_configured_is_amber():
    report = _checker(report_engine_available=None).check()
    assert _find(report, "report_engine").status is HealthStatus.AMBER


def test_report_engine_reachable_is_green():
    report = _checker(report_engine_available=lambda: True).check()
    assert _find(report, "report_engine").status is HealthStatus.GREEN


def test_report_engine_unreachable_is_red():
    report = _checker(report_engine_available=lambda: False).check()
    engine = _find(report, "report_engine")
    assert engine.status is HealthStatus.RED
    assert "exports are down" in engine.detail


# --- storage ---------------------------------------------------------------

def test_storage_not_configured_is_amber_informational():
    """None means the storage layer itself says 'nothing to check' (local
    fallback in use) -- not the same as a check that failed."""
    report = _checker(storage_ping=lambda: (None, "no S3 bucket configured")).check()
    storage = _find(report, "storage")
    assert storage.status is HealthStatus.AMBER
    assert "no S3 bucket" in storage.detail


def test_storage_reachable_is_green():
    report = _checker(storage_ping=lambda: (True, "s3://ally-uploads reachable")).check()
    assert _find(report, "storage").status is HealthStatus.GREEN


def test_storage_unreachable_is_red():
    report = _checker(storage_ping=lambda: (False, "access denied")).check()
    assert _find(report, "storage").status is HealthStatus.RED


def test_storage_check_raising_is_red():
    def boom():
        raise RuntimeError("boto3 not installed")
    report = _checker(storage_ping=boom).check()
    assert _find(report, "storage").status is HealthStatus.RED


# --- error rate --------------------------------------------------------------

def test_error_rate_no_calls_is_green_not_a_false_alarm():
    db = FakeDb(error_rate_row={"errors": 0, "total": 0})
    report = _checker(db).check()
    rate = _find(report, "error_rate")
    assert rate.status is HealthStatus.GREEN
    assert "no AI calls" in rate.detail


def test_error_rate_below_amber_threshold_is_green():
    db = FakeDb(error_rate_row={"errors": 1, "total": 100})  # 1%
    assert _find(_checker(db).check(), "error_rate").status is HealthStatus.GREEN


def test_error_rate_between_thresholds_is_amber():
    db = FakeDb(error_rate_row={"errors": 10, "total": 100})  # 10%
    assert ERROR_RATE_AMBER < 0.10 < ERROR_RATE_RED
    assert _find(_checker(db).check(), "error_rate").status is HealthStatus.AMBER


def test_error_rate_above_red_threshold_is_red():
    db = FakeDb(error_rate_row={"errors": 30, "total": 100})  # 30%
    assert 0.30 > ERROR_RATE_RED
    assert _find(_checker(db).check(), "error_rate").status is HealthStatus.RED


def test_error_rate_query_failure_degrades_only_that_card():
    db = FakeDb(select_1_ok=True, raise_on_error_rate=True)
    report = _checker(db).check()
    assert _find(report, "error_rate").status is HealthStatus.AMBER
    assert _find(report, "database").status is HealthStatus.GREEN  # unaffected
    assert db.rolled_back is True


# --- the composed report -----------------------------------------------------

def test_all_five_components_are_always_present():
    report = _checker().check()
    assert {c.key for c in report.components} == {
        "database", "ai_provider", "report_engine", "storage", "error_rate"
    }


def test_report_overall_status_matches_worst_component():
    report = _checker(FakeDb(select_1_ok=False)).check()  # database red
    assert report.status is HealthStatus.RED
    assert report.is_red is True


def test_all_healthy_report_is_green_and_not_red():
    report = _checker(
        FakeDb(select_1_ok=True, error_rate_row={"errors": 0, "total": 0}),
        ai_provider_health=lambda: (True, "ok"),
        report_engine_available=lambda: True,
        storage_ping=lambda: (True, "ok"),
    ).check()
    assert report.status is HealthStatus.GREEN
    assert report.is_red is False


# --- alerting: email channel --------------------------------------------------

def test_email_channel_sends_to_every_recipient():
    sent = []
    channel = EmailAlertChannel(["ops@goxl.in", "viraj@goxl.in"],
                                send=lambda to, subject, body: sent.append((to, subject, body)))
    report = HealthReport(status=HealthStatus.RED, checked_at=NOW, components=[
        ComponentHealth("database", "Database", HealthStatus.RED, "unreachable"),
    ])
    channel.send(report)
    assert {to for to, _, _ in sent} == {"ops@goxl.in", "viraj@goxl.in"}
    assert all("Database" in subject for _, subject, _ in sent)


def test_email_channel_with_no_recipients_sends_nothing():
    sent = []
    channel = EmailAlertChannel([], send=lambda *a: sent.append(a))
    report = HealthReport(status=HealthStatus.RED, checked_at=NOW, components=[])
    channel.send(report)
    assert sent == []


# --- alerting: edge-triggered notify ------------------------------------------

def _report(status: HealthStatus) -> HealthReport:
    return HealthReport(status=status, checked_at=NOW, components=[
        ComponentHealth("database", "Database", status, ""),
    ])


def test_first_red_report_alerts():
    service = HealthAlertService([])
    assert service.notify(_report(HealthStatus.RED)) is True


def test_staying_red_does_not_alert_again():
    service = HealthAlertService([])
    assert service.notify(_report(HealthStatus.RED)) is True
    assert service.notify(_report(HealthStatus.RED)) is False
    assert service.notify(_report(HealthStatus.RED)) is False


def test_green_never_alerts():
    service = HealthAlertService([])
    assert service.notify(_report(HealthStatus.GREEN)) is False


def test_recovering_then_going_red_again_alerts_a_second_time():
    service = HealthAlertService([])
    assert service.notify(_report(HealthStatus.RED)) is True
    assert service.notify(_report(HealthStatus.GREEN)) is False
    assert service.notify(_report(HealthStatus.RED)) is True  # a genuinely new incident


def test_notify_actually_invokes_every_channel_only_on_the_transition():
    calls = []

    class _Channel:
        def send(self, report):
            calls.append(report.status)

    service = HealthAlertService([_Channel(), _Channel()])
    service.notify(_report(HealthStatus.RED))
    assert calls == [HealthStatus.RED, HealthStatus.RED]  # both channels, once each

    calls.clear()
    service.notify(_report(HealthStatus.RED))  # still red -- no repeat page
    assert calls == []
