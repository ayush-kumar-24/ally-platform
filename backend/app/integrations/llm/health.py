"""Rich, mutable provider health tracking.

M5's frozen `ProviderHealth` DTO is a static `{healthy, detail}` snapshot. This adds
the live, observational state a health-aware router needs -- latency, last
success/failure, consecutive failure count -- so failover can prefer healthy
providers (OpenAI unhealthy -> Claude -> Gemini -> Mock) without any M5 change.

Observational only: it records outcomes, it never alters a provider's behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ProviderHealthState:
    """Live health for one provider. Updated on every call outcome."""

    provider: str
    model: str
    healthy: bool = True
    failures: int = 0                       # consecutive failures (reset on success)
    latency_ms: float | None = None         # latency of the last successful call
    last_success: datetime | None = None
    last_failure: datetime | None = None
    failure_threshold: int = 1              # >= this many consecutive failures -> unhealthy

    def record_success(self, latency_ms: float) -> None:
        self.latency_ms = latency_ms
        self.last_success = _now()
        self.failures = 0
        self.healthy = True

    def record_failure(self) -> None:
        self.last_failure = _now()
        self.failures += 1
        self.healthy = self.failures < self.failure_threshold

    def snapshot(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "healthy": self.healthy,
            "failures": self.failures,
            "latency_ms": self.latency_ms,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
        }


class HealthRegistry:
    """Owns one ProviderHealthState per provider; the single source of truth that
    providers write to and the failover chain reads for ordering."""

    def __init__(self) -> None:
        self._states: dict[str, ProviderHealthState] = {}

    def ensure(self, provider: str, model: str, *, failure_threshold: int = 1) -> ProviderHealthState:
        state = self._states.get(provider)
        if state is None:
            state = ProviderHealthState(provider=provider, model=model, failure_threshold=failure_threshold)
            self._states[provider] = state
        return state

    def get(self, provider: str) -> ProviderHealthState | None:
        return self._states.get(provider)

    def all(self) -> dict[str, ProviderHealthState]:
        return dict(self._states)

    def snapshot(self) -> dict[str, dict]:
        return {name: state.snapshot() for name, state in self._states.items()}
