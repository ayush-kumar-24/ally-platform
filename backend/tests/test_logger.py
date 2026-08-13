"""JSONFormatter -- every extra field a caller passes must survive to the
actual log line, not just a fixed allowlist.

Regression coverage for a live-confirmed bug: the formatter used to allowlist
six specific extra keys and silently drop everything else. The LLM failover
chain's own failure log (`extra={"provider": ..., "error": ...}`), among
dozens of others across the codebase, rendered with no provider name and no
error -- confirmed by breaking both real provider API keys and reading the
actual log line, which said only "llm provider failed in failover chain;
trying next" twice, with nothing to tell the two failures apart.
"""

import json
import logging

from app.core.logger import JSONFormatter


def _format(**extra) -> dict:
    logger = logging.getLogger("test_logger_formatter")
    record = logger.makeRecord(
        "ally", logging.WARNING, __file__, 0, "something failed", (), None, extra=extra,
    )
    return json.loads(JSONFormatter().format(record))


def test_arbitrary_extra_fields_survive():
    payload = _format(stage="llm_failover", provider="openai", error="401 unauthorized")
    assert payload["stage"] == "llm_failover"
    assert payload["provider"] == "openai"
    assert payload["error"] == "401 unauthorized"


def test_allowlisted_fields_still_work():
    """The six fields the old allowlist covered must keep working -- this
    fix widens what's captured, it must not narrow it."""
    payload = _format(request_id="req-1", founder_id=42, path="/x", method="GET",
                      status_code=200, duration_ms=12.5)
    assert payload["request_id"] == "req-1"
    assert payload["founder_id"] == 42
    assert payload["path"] == "/x"
    assert payload["method"] == "GET"
    assert payload["status_code"] == 200
    assert payload["duration_ms"] == 12.5


def test_no_extra_fields_produces_clean_payload():
    payload = _format()
    assert set(payload) == {"timestamp", "level", "logger", "message"}


def test_non_json_native_extra_value_does_not_crash_the_logger():
    """An extra value that isn't natively JSON-serialisable (e.g. an
    exception object, a Decimal) must degrade to its string form, not raise
    -- a crash in the logging path would be strictly worse than the old
    silent-drop behaviour this fix replaces."""
    payload = _format(cause=ValueError("boom"))
    assert "boom" in payload["cause"]


def test_none_valued_extra_is_omitted():
    """Matches the old allowlist's behaviour for None -- an extra field
    that's None (e.g. an optional id not set on this call) shouldn't clutter
    every log line with nulls."""
    payload = _format(founder_id=None)
    assert "founder_id" not in payload
