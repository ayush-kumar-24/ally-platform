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


def _envelope(error: str, message: str, request_id: str, detail: str | None = None) -> dict:
    """The one error shape this API returns.

    `message` and `detail` carry the same text. `detail` is FastAPI's own
    convention and is what every client we have reads -- the frontend's
    normalizeError() looks for it and nothing else, so an envelope with only
    `message` left founders staring at axios's raw "Request failed with status
    code 422" while the real reason sat unread in the body. `message` stays
    because tests and older consumers read it; neither side has to change.

    `detail` may differ from `message` where the raw text isn't fit to show a
    human -- see the validation handler.
    """
    return {
        "error": error,
        "message": message,
        "detail": detail if detail is not None else message,
        "request_id": request_id,
    }


async def app_error_handler(request: Request, exc: AppError):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.warning("Handled app error", extra={"request_id": request_id, "path": request.url.path})
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(exc.__class__.__name__, exc.message, request_id),
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope("HTTPException", str(exc.detail), request_id),
    )


def _readable_validation_error(exc: RequestValidationError) -> str:
    """Pydantic's error list, as one line a person can act on.

    The raw repr goes in `message` for debugging, but `detail` is rendered
    straight into the UI -- and "[{'type': 'missing', 'loc': ('body', ...)}]" on
    a login screen is worse than no message at all.
    """
    parts = []
    for err in exc.errors():
        # loc is ("body", "field", ...) -- drop the source, keep the field path.
        field = ".".join(str(p) for p in err.get("loc", ())[1:])
        msg = err.get("msg", "Invalid value")
        parts.append(f"{field}: {msg}" if field else msg)
    return "; ".join(parts) or "The request could not be processed."


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_envelope(
            "ValidationError",
            str(exc.errors()),
            request_id,
            detail=_readable_validation_error(exc),
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.error("Unhandled exception", extra={"request_id": request_id, "path": request.url.path}, exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_envelope(
            "InternalServerError", "Something went wrong. We've logged it.", request_id
        ),
    )