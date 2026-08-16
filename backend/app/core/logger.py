import logging
import sys
import json
from datetime import datetime, timezone

from app.core.config import settings

# Every attribute a bare `logging.LogRecord` carries before any `extra={}` is
# merged in. Anything on the record NOT in this set is something a caller
# explicitly passed via `extra=` -- which is exactly the diagnostic context
# structured logging exists to keep.
#
# The formatter used to allowlist six specific extra keys (request_id,
# founder_id, path, method, status_code, duration_ms) and silently drop
# everything else. That meant `logger.warning(..., extra={"provider": name,
# "error": str(exc)})` -- the LLM failover chain's own failure log, among
# dozens of others across the codebase -- rendered as just "llm provider
# failed in failover chain; trying next" with no provider name and no error,
# confirmed live: broke both real provider API keys, chat degraded to the
# mock provider correctly (ok=True, no crash -- that part always worked),
# but the log line for *why* carried none of the fields the calling code
# clearly intended to be there. This is the fix -- every extra field now
# survives to the actual log line, not just the ones on a list someone has
# to remember to keep updated.
_STANDARD_RECORD_ATTRS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName", "message",
})


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_ATTRS and value is not None:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # default=str: an extra field that isn't natively JSON-serialisable
        # (a Decimal, a dataclass, an object with no __dict__ shortcut) must
        # not be able to crash the logger itself -- that would be worse than
        # the field being dropped, the same failure mode this fix exists to
        # close for the string/int/bool case.
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


logger = logging.getLogger("ally")