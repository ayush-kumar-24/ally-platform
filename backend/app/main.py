from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.logger import configure_logging
from app.core.cors import setup_cors
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.error_handler import (
    AppError,
    app_error_handler,
    http_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
)
from app.api.v1.router import api_router

configure_logging()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
)

# --- Middleware ---
app.add_middleware(RequestLoggingMiddleware)
setup_cors(app)

# --- Error handlers ---
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# --- Routes ---
app.include_router(api_router)


@app.get("/")
async def root():
    return {
        "status": "running",
        "message": "Ally Backend Running 🚀"
    }