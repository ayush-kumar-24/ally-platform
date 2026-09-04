"""Admin Panel Proposal, gap #3: "Health is invisible."

    If the database, the AI provider or report generation breaks, we find
    out from a customer.

A health endpoint already existed (`GET /api/v1/health`), but it only ever
checked the database and the PDF renderer, for App Runner's own traffic
routing -- and it was never shown anywhere in the panel. This is the richer,
panel-facing check the proposal actually asked for: database, AI provider,
report engine, storage, and error rate, each green/amber/red -- plus the
alert that fires when any of them turns red.

Same honesty contract as app/admin/insights.py: each component is checked
independently and wrapped, so one broken check degrades only that card
(amber/red with a reason), never the whole page.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Protocol

from sqlalchemy import text

from app.core.logger import logger

# How far back "error rate" looks, and the two thresholds that turn it amber
# then red. 15 minutes is long enough to not flap on a single failed call,
# short enough that a real outage shows red within one page refresh.
ERROR_RATE_WINDOW = timedelta(minutes=15)
ERROR_RATE_AMBER = 0.05   # 5% of calls failing
ERROR_RATE_RED = 0.20     # 20% of calls failing


class HealthStatus(str, Enum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"


@dataclass(frozen=True)
class ComponentHealth:
    key: str
    label: str
    status: HealthStatus
    detail: str = ""


@dataclass(frozen=True)
class HealthReport:
    status: HealthStatus          # worst of every component
    components: list[ComponentHealth]
    checked_at: datetime

    @property
    def is_red(self) -> bool:
        return self.status is HealthStatus.RED


def overall_status(components: list[ComponentHealth]) -> HealthStatus:
    """Worst-of, not an average -- one red component is enough to call the
    whole platform not-green, the same way one red CI check blocks a PR
    regardless of how many others passed."""
    if any(c.status is HealthStatus.RED for c in components):
        return HealthStatus.RED
    if any(c.status is HealthStatus.AMBER for c in components):
        return HealthStatus.AMBER
    return HealthStatus.GREEN


class HealthChecker(abc.ABC):
    @abc.abstractmethod
    def check(self) -> HealthReport: ...


class SystemHealthChecker(HealthChecker):
    """The real, DB- and process-backed implementation.

    `ai_provider_health`/`report_engine_available`/`storage_ping` are
    injected callables, not hardcoded -- same collaborator pattern
    AdminPanelService already uses for `report_regenerator` -- so this class
    is testable without a real LLM provider, Gotenberg sidecar, or S3 bucket.
    `None` for any of them means "not wired in this environment", reported
    as amber ("not configured"), not a crash.
    """

    def __init__(
        self,
        db,
        *,
        ai_provider_health: Callable[[], tuple[bool, str]] | None = None,
        report_engine_available: Callable[[], bool] | None = None,
        storage_ping: Callable[[], tuple[bool | None, str]] | None = None,
        clock: Callable[[], datetime] | None = None,
    ):
        self.db = db
        self.ai_provider_health = ai_provider_health
        self.report_engine_available = report_engine_available
        self.storage_ping = storage_ping
        self._now = clock or (lambda: datetime.now(timezone.utc))

    def check(self) -> HealthReport:
        now = self._now()
        components = [
            self._database(),
            self._ai_provider(),
            self._report_engine(),
            self._storage(),
            self._error_rate(now),
        ]
        return HealthReport(status=overall_status(components), components=components, checked_at=now)

    # --- components --------------------------------------------------------

    def _database(self) -> ComponentHealth:
        try:
            self.db.execute(text("SELECT 1"))
            return ComponentHealth("database", "Database", HealthStatus.GREEN, "connected")
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            return ComponentHealth("database", "Database", HealthStatus.RED, f"unreachable: {exc}")

    def _ai_provider(self) -> ComponentHealth:
        if self.ai_provider_health is None:
            return ComponentHealth("ai_provider", "AI provider", HealthStatus.AMBER, "not configured")
        try:
            healthy, detail = self.ai_provider_health()
        except Exception as exc:  # noqa: BLE001
            return ComponentHealth("ai_provider", "AI provider", HealthStatus.RED,
                                   f"health check failed: {exc}")
        return ComponentHealth("ai_provider", "AI provider",
                               HealthStatus.GREEN if healthy else HealthStatus.RED, detail)

    def _report_engine(self) -> ComponentHealth:
        if self.report_engine_available is None:
            return ComponentHealth("report_engine", "Report engine", HealthStatus.AMBER, "not configured")
        try:
            available = self.report_engine_available()
        except Exception as exc:  # noqa: BLE001
            return ComponentHealth("report_engine", "Report engine", HealthStatus.RED,
                                   f"check failed: {exc}")
        return ComponentHealth(
            "report_engine", "Report engine",
            HealthStatus.GREEN if available else HealthStatus.RED,
            "gotenberg reachable" if available else "gotenberg unreachable -- exports are down",
        )

    def _storage(self) -> ComponentHealth:
        if self.storage_ping is None:
            return ComponentHealth("storage", "Storage", HealthStatus.AMBER, "not configured")
        try:
            ok, detail = self.storage_ping()
        except Exception as exc:  # noqa: BLE001
            return ComponentHealth("storage", "Storage", HealthStatus.RED, f"check failed: {exc}")
        if ok is None:
            # Distinct from a check failure: the storage layer itself reports
            # "there is nothing configured to check" (e.g. no S3 bucket, local
            # fallback in use) -- informational, not an outage.
            return ComponentHealth("storage", "Storage", HealthStatus.AMBER, detail)
        return ComponentHealth("storage", "Storage",
                               HealthStatus.GREEN if ok else HealthStatus.RED, detail)

    def _error_rate(self, now: datetime) -> ComponentHealth:
        since = now - ERROR_RATE_WINDOW
        try:
            row = self.db.execute(
                text(
                    "SELECT count(*) FILTER (WHERE status = 'error') AS errors, "
                    "       count(*) AS total "
                    "FROM llm_call_log WHERE created_at >= :since"
                ),
                {"since": since},
            ).mappings().first()
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            logger.warning("health check: error-rate query failed",
                           extra={"error": str(exc)})
            return ComponentHealth("error_rate", "Error rate", HealthStatus.AMBER, "unavailable")

        total = int((row or {}).get("total") or 0)
        errors = int((row or {}).get("errors") or 0)
        if total == 0:
            return ComponentHealth("error_rate", "Error rate", HealthStatus.GREEN,
                                   "no AI calls in the last 15 minutes")

        rate = errors / total
        detail = f"{rate:.0%} of {total} calls failed in the last 15 minutes"
        if rate >= ERROR_RATE_RED:
            return ComponentHealth("error_rate", "Error rate", HealthStatus.RED, detail)
        if rate >= ERROR_RATE_AMBER:
            return ComponentHealth("error_rate", "Error rate", HealthStatus.AMBER, detail)
        return ComponentHealth("error_rate", "Error rate", HealthStatus.GREEN, detail)


# --- alerting ----------------------------------------------------------------

class AlertChannel(Protocol):
    def send(self, report: HealthReport) -> None: ...


class EmailAlertChannel:
    """The only channel actually wired today -- see HealthAlertService's
    module-level note on WhatsApp."""

    def __init__(self, recipients: list[str], *, send=None):
        self.recipients = recipients
        if send is None:
            from app.services.email import send_email
            send = send_email
        self._send = send

    def send(self, report: HealthReport) -> None:
        if not self.recipients:
            return
        red = [c for c in report.components if c.status is HealthStatus.RED]
        subject = f"[Ally] Health alert: {', '.join(c.label for c in red) or 'system'} red"
        body = "\n".join(f"{c.label}: {c.status.value} -- {c.detail}" for c in report.components)
        for to in self.recipients:
            self._send(to, subject, body)


@dataclass
class HealthAlertService:
    """Alerts once per transition INTO red, not on every poll while it stays
    red -- an external scheduler hitting /internal/jobs/check-health every
    few minutes during a real outage must not send a fresh page every time.

    State (`_was_red`) is process-local. That is a known v1 limitation, not
    an oversight: a durable, cross-instance version needs a table, and this
    is a plain read/notify path with no product decision behind a new
    migration yet -- same reasoning session_store.py gives for why its own
    original in-memory scaffold was acceptable before it got a DB-backed
    upgrade with explicit sign-off. Worst case here is a duplicate or missed
    alert around a restart, not a missed outage: the next check (green or
    red) always reflects the real state, and the panel's Health page is
    always live regardless of this service's memory.
    """

    channels: list[AlertChannel] = field(default_factory=list)
    _was_red: bool = field(default=False, init=False, repr=False)

    def notify(self, report: HealthReport) -> bool:
        """Sends through every channel if this report is a green->red
        transition. Returns whether an alert was actually sent."""
        is_red = report.is_red
        should_alert = is_red and not self._was_red
        self._was_red = is_red
        if should_alert:
            for channel in self.channels:
                channel.send(report)
        return should_alert
