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

# Sentry is optional -- with no DSN set (the default in development) this is a
# no-op and nothing is sent anywhere.
if settings.SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        release=settings.VERSION,
        # Sampled, not exhaustive -- full tracing on every request is expensive
        # and rarely what you want in production.
        traces_sample_rate=0.1 if settings.is_production else 1.0,
        # These carry founder data. Turn on deliberately, not by default.
        send_default_pii=False,
    )

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