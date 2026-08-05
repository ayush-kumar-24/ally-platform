from dotenv import load_dotenv

# Must run before any other app import. pydantic-settings (app.core.config)
# reads .env into its own private store and never touches the real process
# environment -- nothing else in this codebase calls load_dotenv() either.
# app.integrations.llm.settings (the Ally chat / voice LLM stack) reads
# ALLY_LLM_PROVIDER, ALLY_LLM_FALLBACK etc. straight from os.environ by design
# (its own docstring: "no coupling to app settings"), so without this call
# those variables were never visible to it, no matter what .env said --
# LLMSettings silently defaulted to "mock" and every chat reply came back
# "Grounded answer from mock-standard." regardless of a real OPENAI_API_KEY
# sitting right there in .env. Confirmed empirically: a bare `os.environ.get
# ("ALLY_LLM_PROVIDER")` with zero app imports returned None even though the
# value was in .env, while a machine-level OPENAI_API_KEY (set outside .env
# entirely) came through fine -- that's what made this look like a key
# problem rather than a loading-order one.
#
# override=True is required, not optional. python-dotenv's default
# (override=False) never overwrites a name that already exists in
# os.environ -- and this machine has a STALE OPENAI_API_KEY set at the
# Windows user/machine level (from some earlier, unrelated setup), fully
# independent of .env. With the default, that dead key silently won every
# time: OpenAIProvider called the real API with it, got a 401, and
# FailoverLLMProvider (routing.py) quietly swallows any provider exception
# and drops to the next link in the chain -- which is MockLLMProvider. That
# produced exactly the symptom reported: a routing decision that correctly
# named "openai"/"gpt-4o-mini", wrapping content that was still
# MockLLMProvider's canned template. Confirmed empirically: os.environ's
# OPENAI_API_KEY (sk-proj-7HXn4B...) did not match backend/.env's
# (sk-proj-k04mJmnb...), and calling OpenAIProvider.generate() directly
# raised LLMAuthError: "openai authentication failed (401)". override=True
# makes .env -- this project's actual source of truth -- win over whatever
# is already sitting in the shell/machine environment.
load_dotenv(override=True)

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
# Composition: bind reasoning as the diagnosis session-completion listener.
# The diagnosis module depends only on its SessionCompletionNotifier port; here
# we wire the reasoning trigger as the concrete listener.
from app.api.v1.diagnosis.notifications import get_session_completion_notifier
from app.api.v1.reasoning.trigger import get_reasoning_trigger

app.dependency_overrides[get_session_completion_notifier] = get_reasoning_trigger

app.include_router(api_router)


@app.get("/")
async def root():
    return {
        "status": "running",
        "message": "Ally Backend Running 🚀"
    }