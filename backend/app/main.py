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
# OPENAI_API_KEY did not match backend/.env's key, and calling
# OpenAIProvider.generate() directly raised LLMAuthError: "openai
# authentication failed (401)". override=True
# makes .env -- this project's actual source of truth -- win over whatever
# is already sitting in the shell/machine environment.
load_dotenv(override=True)

from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.logger import configure_logging, logger
from app.core.cors import setup_cors
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
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
# no-op and nothing is sent anywhere. That's fine in development, but it was
# previously silent in every environment: a production deploy that forgot to
# set SENTRY_DSN got no error tracking and no signal that error tracking was
# off. Both branches below now log loudly at startup specifically so "is
# Sentry actually on in prod" is answerable from the boot log alone, not by
# assuming the env var made it into the App Runner console.
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
    logger.info("sentry_initialized", extra={"environment": settings.ENVIRONMENT})
elif settings.is_production:
    # Not raising: a missing SENTRY_DSN shouldn't take the whole app down when
    # the alternative is "founders can't sign up." But this must never be a
    # silent gap in production -- log at ERROR so it surfaces in CloudWatch
    # and (once Sentry itself is fixed) would page on its own irony.
    logger.error(
        "sentry_not_configured_in_production",
        extra={"environment": settings.ENVIRONMENT},
    )
else:
    logger.info("sentry_disabled", extra={"environment": settings.ENVIRONMENT})

# Nothing writes answers.score_label unless ADAPTIVE_QUESTIONS is on (the
# submit-time advisor is the only writer -- DiagnosisService._apply_insight), and
# nothing derives it at report time unless ANSWER_CLASSIFIER is "llm". With both
# off, every answer reaches the reasoning pipeline unscored, every one is skipped
# as unclassifiable, and the diagnosis produces a report with no evidence behind
# it. That combination is what backend/.env.example ships and what
# DEPLOY_AWS.md's "values that must differ" table does not mention, so a deploy
# that follows the documentation lands on it.
#
# NoClassifiableAnswersError now stops such a run from persisting an empty
# report, but that fires 30 questions too late -- after a founder has spent an
# assessment they may only get one of. Logged at ERROR here so the misconfigured
# state is answerable from the boot log, before anyone takes the diagnosis. Same
# rule as the Sentry branch above: refuse to be a silent gap, but do not refuse
# to boot -- a founder who cannot sign up at all is a worse outcome, and the
# other phases of the product are unaffected.
# Report PDFs render through Gotenberg (headless Chromium), and there is no
# second renderer -- see app/api/v1/reports/routes.py::export_pdf. When the
# sidecar is unreachable the export answers 503 and queues a backfill, so a
# founder gets their real report or an honest "not yet", never a lookalike.
#
# That makes this probe more important than it was, not less. The old fallback
# at least produced a document; today a missing sidecar means downloads simply
# do not work, and the founder-facing message ("still being prepared, try again
# shortly") describes a momentary outage. If the sidecar was never deployed,
# that message is a lie that repeats forever, and nothing else in the system
# says so.
#
# GOTENBERG_URL defaults to http://localhost:3000, which is empty inside the API
# container, so the misconfigured state is also the DEFAULT state. Probed once at
# boot so it is answerable from the startup log rather than from a founder
# noticing their report looks like a text file.
#
# Checked in production only: locally the sidecar is usually not running and
# nobody is downloading reports, so an ERROR on every dev boot would be noise
# that teaches people to ignore this line.
if settings.is_production:
    from app.api.v1.reports.gotenberg import is_available as _gotenberg_available

    if _gotenberg_available(base_url=settings.GOTENBERG_URL):
        logger.info("gotenberg_reachable", extra={"url": settings.GOTENBERG_URL})
    else:
        logger.error(
            "gotenberg_unreachable",
            extra={
                "url": settings.GOTENBERG_URL,
                "impact": (
                    "every report export will silently fall back to a plain "
                    "reportlab PDF instead of the founder's actual report -- "
                    "see DEPLOY_AWS.md section 3a"
                ),
            },
        )

if not settings.diagnosis_scoring_configured:
    logger.error(
        "diagnosis_scoring_disabled",
        extra={
            "adaptive_questions": settings.ADAPTIVE_QUESTIONS,
            "answer_classifier": settings.ANSWER_CLASSIFIER,
            "impact": (
                "no answer will be scored, so every diagnosis will fail to "
                "produce a report -- set ADAPTIVE_QUESTIONS=true (preferred) "
                "or ANSWER_CLASSIFIER=llm"
            ),
        },
    )

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    # Interactive docs expose the full API surface (routes, schemas, and in
    # AUTH_PROVIDER=dev they're even directly callable with no token). Fine
    # in development; a production API has no business publishing its own
    # schema to anyone who finds the URL.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

# --- Middleware ---
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
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

# Local disk storage for uploaded profile photos (see api/v1/profile/avatar.py).
# A real cloud bucket (S3 / Supabase Storage) is the right home for this in
# production -- files here do not survive a redeploy on infrastructure with an
# ephemeral filesystem (e.g. a container replaced rather than updated in
# place). Swapping the storage backend is scoped to that one module; nothing
# else references the filesystem path directly.
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
(UPLOAD_DIR / "avatars").mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/")
async def root():
    return {
        "status": "running",
        "message": "Ally Backend Running 🚀"
    }