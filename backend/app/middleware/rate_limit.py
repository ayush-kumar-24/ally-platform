"""In-process request-rate limiting.

Pre-beta audit finding: there was no rate limiting anywhere in this backend --
auth endpoints (session/refresh/resume) were open to unlimited brute-force
attempts, and AI endpoints (chat, diagnosis) had no request-level ceiling
independent of the plan/credit gate (which only kicks in when
PLAN_ENFORCEMENT_ENABLED is on, and doesn't exist at all on the diagnosis
path -- see app/api/v1/plans/dependencies.py).

No Redis or task-queue infrastructure exists in this codebase (confirmed --
see app/api/v1/webhooks/internal_jobs.py's own note on the same gap), and the
beta deployment is single-instance (DEPLOY_AWS.md: App Runner min/max 1/2
instances). A dependency-free, in-process sliding-window limiter is therefore
a real, meaningful backstop today -- not a no-op -- without adding new
infrastructure this stage of the product doesn't otherwise need. It resets on
process restart and does not coordinate across instances; if App Runner is
ever scaled to run more than one instance concurrently for real (not just the
brief overlap during a rolling deploy), replace this with a shared-store
limiter (e.g. slowapi + Redis) so the limit is enforced per-user/IP across
the whole fleet, not per-instance.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from typing import Callable

from fastapi import Depends, HTTPException, Request, status


class _SlidingWindowLimiter:
    """One counter per (bucket) key, a rolling window of hit timestamps.

    Thread-safe: FastAPI's sync dependencies (and the threadpool sync request
    path in general) can call `allow()` from multiple worker threads
    concurrently within one process.
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, *, limit: int, window_seconds: float) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            cutoff = now - window_seconds
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True


_limiter = _SlidingWindowLimiter()


def _client_ip(request: Request) -> str:
    # App Runner (and any proxy in front of it) sets X-Forwarded-For; trust
    # only the first hop, which is the actual client. Falls back to the raw
    # peer address for local dev / tests, where there is no proxy.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def ip_rate_limit(*, key: str, limit: int, window_seconds: float):
    """Dependency factory for pre-auth endpoints (login, refresh, resume) --
    there is no founder identity yet to key on, so this limits by client IP.

    Usage: `Depends(ip_rate_limit(key="auth-session", limit=10, window_seconds=60))`
    `key` namespaces the bucket per route so one endpoint's limit can't be
    exhausted by traffic to a different one.
    """

    def _dependency(request: Request) -> None:
        bucket = f"{key}:ip:{_client_ip(request)}"
        if not _limiter.allow(bucket, limit=limit, window_seconds=window_seconds):
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please slow down and try again shortly.",
            )

    return _dependency


def founder_rate_limit(
    *, key: str, limit: int, window_seconds: float, founder_id_dependency: Callable
):
    """Dependency factory for authenticated endpoints (chat, diagnosis) --
    keyed by founder_id so the limit follows the account, not a shared/NAT'd
    IP (which would either wrongly throttle unrelated founders behind the
    same IP, or let one abusive founder dodge the limit by rotating IPs).

    `founder_id_dependency` is the SAME founder-resolving dependency the
    route already uses (e.g. get_current_founder_id for chat,
    get_founder_record for diagnosis) rather than a hardcoded one -- routers
    in this codebase resolve the founder through different dependency
    chains, and reusing theirs avoids decoding/verifying the token twice per
    request. It may resolve to either an int founder_id directly or an
    object with a `.founder_id` attribute (the Founder domain model).

    Usage:
        Depends(founder_rate_limit(key="chat-message", limit=20,
                                   window_seconds=60,
                                   founder_id_dependency=get_current_founder_id))
    """

    def _dependency(resolved=Depends(founder_id_dependency)) -> None:
        founder_id = resolved if isinstance(resolved, int) else getattr(resolved, "founder_id", resolved)
        bucket = f"{key}:founder:{founder_id}"
        if not _limiter.allow(bucket, limit=limit, window_seconds=window_seconds):
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please slow down and try again shortly.",
            )

    return _dependency
