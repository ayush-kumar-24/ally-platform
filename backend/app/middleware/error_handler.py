import uuid
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logger import logger


class AppError(Exception):
    """Base class for our own domain errors (e.g. DiagnosisNotFoundError)."""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code


async def app_error_handler(request: Request, exc: AppError):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    # Every AppError subclass across the app funnels through this one handler
    # -- AuthError, diagnosis errors, OutOfCreditsError/DailyTokenLimitError/
    # FeatureNotInPlanError, privacy, admin, all of it. The log line used to
    # carry only request_id + path, so "Handled app error" told you nothing
    # about WHAT happened or WHO it happened to, even though both were sitting
    # right here (exc.__class__.__name__/exc.message, and founder_id already
    # set on request.state by the auth dependency by this point in the
    # request -- confirmed live: the very next "Request handled" log line for
    # the same request_id already had it). Same info the response body always
    # had; the log just wasn't given a copy of it.
    extra = {
        "request_id": request_id,
        "path": request.url.path,
        "error_type": exc.__class__.__name__,
        "error_message": exc.message,
        "status_code": exc.status_code,
    }
    founder_id = getattr(request.state, "founder_id", None)
    if founder_id:
        extra["founder_id"] = founder_id
    logger.warning("Handled app error", extra=extra)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.__class__.__name__, "message": exc.message, "request_id": request_id},
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "HTTPException", "message": str(exc.detail), "request_id": request_id},
        # HTTPException carries headers for responses where the header IS part of
        # the answer -- Retry-After on a 503, WWW-Authenticate on a 401. Building
        # a fresh JSONResponse without them dropped every one of those silently;
        # the raiser had no way to tell, since the status and body still looked
        # right. Currently only the report export sets any, which is how this was
        # noticed.
        headers=getattr(exc, "headers", None),
    )


#: Wrapper segments of a Pydantic error `loc` that name WHERE the value came
#: from rather than which field it was. Dropped when naming the field, so a
#: founder reads "title" and not "body -> title".
_LOC_WRAPPERS = frozenset({"body", "query", "path", "header", "cookie"})


def _field_name(loc) -> str | None:
    """The founder-facing field name from a Pydantic error `loc`, or None.

    `loc` is a tuple like ("body", "title") or ("body", 0, "tasks", "due_time").
    Integers are list indices; taking the last STRING skips them, so a nested
    error still names a field rather than a position.
    """
    parts = [p for p in loc if isinstance(p, str) and p not in _LOC_WRAPPERS]
    return parts[-1] if parts else None


def _validation_message(errors) -> str:
    """One human-readable sentence built from Pydantic's first error.

    Never interpolates the error dict itself, and in particular never the
    `input` key -- see validation_exception_handler for why that matters.
    """
    first = next(iter(errors), None)
    if not isinstance(first, dict):
        return "Some of that wasn't valid — please check and try again."

    msg = first.get("msg")
    if not isinstance(msg, str) or not msg:
        return "Some of that wasn't valid — please check and try again."

    field = _field_name(first.get("loc") or ())
    return f"{field}: {msg}" if field else msg


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """422s reach the founder as a sentence, not as Python.

    This used to send `str(exc.errors())` -- the repr of Pydantic's error list
    -- straight through as `message`. services/api.js reads `data.message`
    first, so that repr was what the founder actually saw. Captured live on
    goxlally.ai, in a toast on Plan Your Day:

        [{'type': 'string_too_long', 'loc': ('body', 'title'), 'msg': 'String
        should have at most 200 characters', 'input': 'I want to spend the
        whole day working through the pricing conversation problem with my
        three pilot factory owners because ...', 'ctx': {'max_length': 200}}]

    Two separate problems, and the second is the reason this is not merely
    cosmetic:

      * It is app-wide. EVERY Pydantic failure anywhere -- sign-up, profile,
        goals, tasks -- renders like this, and none of them tell the founder
        what to actually do about it.
      * `exc.errors()` carries an `input` key holding the value that failed.
        Echoing the whole list back put that value in the response body, so a
        validation failure on a password, token or any other secret-bearing
        field would return it to the client. Nothing about the old line was
        specific to harmless fields.

    api.js already knew how to read FastAPI's native 422 shape
    (`data.detail[0].msg`), but that branch was unreachable: this backend
    sends `message`, never `detail`. Fixing the message here is what makes
    that path moot rather than requiring the client to change.

    The full errors are logged instead, with `input` dropped for the same
    reason it is kept out of the response -- request_id ties a founder's
    report of the message back to this line.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    errors = exc.errors()

    logger.warning(
        "Request failed validation",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            # type/loc/msg only -- deliberately NOT `input` or `ctx`, which can
            # carry the submitted value.
            "errors": [
                {k: v for k, v in e.items() if k in ("type", "loc", "msg")}
                for e in errors
                if isinstance(e, dict)
            ],
        },
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "message": _validation_message(errors),
            "request_id": request_id,
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.error("Unhandled exception", extra={"request_id": request_id, "path": request.url.path}, exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "InternalServerError", "message": "Something went wrong. We've logged it.", "request_id": request_id},
    )