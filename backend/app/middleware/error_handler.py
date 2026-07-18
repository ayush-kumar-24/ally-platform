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
    logger.warning("Handled app error", extra={"request_id": request_id, "path": request.url.path})
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.__class__.__name__, "message": exc.message, "request_id": request_id},
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "HTTPException", "message": str(exc.detail), "request_id": request_id},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "ValidationError", "message": str(exc.errors()), "request_id": request_id},
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.error("Unhandled exception", extra={"request_id": request_id, "path": request.url.path}, exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "InternalServerError", "message": "Something went wrong. We've logged it.", "request_id": request_id},
    )