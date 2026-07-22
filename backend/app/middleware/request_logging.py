import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logger import logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        # Set by the auth dependency during the request, so it is only present
        # on authenticated routes -- which is exactly when it is worth having.
        extra = {
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }
        founder_id = getattr(request.state, "founder_id", None)
        if founder_id:
            extra["founder_id"] = founder_id

        logger.info("Request handled", extra=extra)
        response.headers["X-Request-ID"] = request_id
        return response