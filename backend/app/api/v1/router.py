from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.api.v1.chat.router import router as chat_api_router
from app.api.v1.admin.router import router as admin_router
from app.api.v1.planning.router import router as planning_router
from app.api.v1.founder_goals.router import router as founder_goals_router
from app.api.v1.auth.routes import router as auth_router
from app.api.v1.consents.router import router as consents_router
from app.api.v1.privacy.router import router as privacy_router
from app.api.v1.plans.router import router as plans_router
from app.api.v1.admin.panel_router import router as admin_panel_router
from app.api.v1.admin.panel_router_v2 import router as admin_panel_router_v2
from app.api.v1.dashboard.routes import router as dashboard_router
from app.api.v1.diagnosis.router import router as diagnosis_router
from app.api.v1.current_problem.router import router as current_problem_router
from app.api.v1.founder_dna.router import router as founder_dna_router
from app.api.v1.discovery.routes import router as discovery_router
from app.api.v1.intelligence.routes import router as intelligence_router
from app.api.v1.knowledge.routes import router as knowledge_router
from app.api.v1.notifications.routes import router as notifications_router
from app.api.v1.feedback.router import router as feedback_router
from app.api.v1.frontend_errors.router import router as frontend_errors_router
from app.api.v1.impression.router import router as impression_router
from app.api.v1.profile.routes import router as profile_router
from app.api.v1.reference.routes import router as reference_router
from app.api.v1.reports.routes import router as reports_router
from app.api.v1.settings.routes import router as settings_router
from app.api.v1.settings.router import router as settings_preferences_router
from app.api.v1.voice.router import router as voice_router
from app.api.v1.webhooks.supabase import router as webhooks_supabase_router
from app.api.v1.webhooks.internal_jobs import router as internal_jobs_router
from app.api.v1.reports.gotenberg import is_available as gotenberg_available
from app.core.config import settings
from app.db.session import engine

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(profile_router)
api_router.include_router(impression_router)
api_router.include_router(feedback_router)
api_router.include_router(frontend_errors_router)
api_router.include_router(discovery_router)
api_router.include_router(founder_dna_router)
api_router.include_router(current_problem_router)
api_router.include_router(diagnosis_router)
api_router.include_router(settings_router)
api_router.include_router(settings_preferences_router)
api_router.include_router(notifications_router)
api_router.include_router(knowledge_router)
api_router.include_router(intelligence_router)
api_router.include_router(reference_router)
api_router.include_router(dashboard_router)
api_router.include_router(reports_router)
api_router.include_router(chat_api_router)
api_router.include_router(admin_router)
api_router.include_router(planning_router)
api_router.include_router(founder_goals_router)
api_router.include_router(consents_router)
api_router.include_router(privacy_router)
api_router.include_router(voice_router)
api_router.include_router(plans_router)
# Registered after the Phase 12 admin router; paths are distinct (/admin/users,
# /admin/credits, /admin/audit vs /admin/founders, /admin/announcements).
api_router.include_router(admin_panel_router)
api_router.include_router(admin_panel_router_v2)
api_router.include_router(webhooks_supabase_router)
api_router.include_router(internal_jobs_router)


@api_router.get("/health")
async def health(response: Response):
    db_status = "connected"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "unreachable"

    # This is the endpoint infrastructure (App Runner) should be polling for
    # instance health/traffic routing -- see DEPLOY_AWS.md. A non-2xx status
    # code is what actually gets App Runner to stop routing traffic to (and
    # eventually recycle) an instance; a 200 with "degraded" in the body would
    # be invisible to a health check that only looks at the status code, which
    # is the common case. The bare `/` root endpoint intentionally does NOT do
    # this check -- it exists only as an unauthenticated liveness ping, not a
    # readiness check.
    if db_status != "connected":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    # Which renderer report exports will actually use. INFORMATIONAL ONLY -- it
    # deliberately does not affect `status` or the status code.
    #
    # A broken PDF renderer must not take the API out of rotation: App Runner
    # would stop routing to a healthy instance over a feature that degrades
    # gracefully, and founders who cannot sign in is a far worse outcome than
    # founders whose PDF looks plain. But it must be VISIBLE, because nothing
    # else makes it so -- the export returns 200 with a real PDF either way.
    #
    # `gotenberg` means exports match the on-screen report. `reportlab-fallback`
    # means every founder is getting the plain two-page document instead; see
    # DEPLOY_AWS.md section 3a.
    pdf_renderer = (
        "gotenberg"
        if gotenberg_available(base_url=settings.GOTENBERG_URL)
        else "reportlab-fallback"
    )

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "pdf_renderer": pdf_renderer,
    }