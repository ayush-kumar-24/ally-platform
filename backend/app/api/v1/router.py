from fastapi import APIRouter
from sqlalchemy import text

from app.api.v1.ally.chat.router import router as ally_router
from app.api.v1.chat.router import router as chat_api_router
from app.api.v1.admin.router import router as admin_router
from app.api.v1.planning.router import router as planning_router
from app.api.v1.auth.routes import router as auth_router
from app.api.v1.consents.router import router as consents_router
from app.api.v1.privacy.router import router as privacy_router
from app.api.v1.dashboard.routes import router as dashboard_router
from app.api.v1.diagnosis.router import router as diagnosis_router
from app.api.v1.discovery.routes import router as discovery_router
from app.api.v1.intelligence.routes import router as intelligence_router
from app.api.v1.knowledge.routes import router as knowledge_router
from app.api.v1.notifications.routes import router as notifications_router
from app.api.v1.profile.routes import router as profile_router
from app.api.v1.reference.routes import router as reference_router
from app.api.v1.reports.routes import router as reports_router
from app.api.v1.settings.routes import router as settings_router
from app.api.v1.settings.router import router as settings_preferences_router
from app.db.session import engine

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(profile_router)
api_router.include_router(discovery_router)
api_router.include_router(diagnosis_router)
api_router.include_router(settings_router)
api_router.include_router(settings_preferences_router)
api_router.include_router(notifications_router)
api_router.include_router(knowledge_router)
api_router.include_router(intelligence_router)
api_router.include_router(reference_router)
api_router.include_router(dashboard_router)
api_router.include_router(ally_router)
api_router.include_router(reports_router)
api_router.include_router(chat_api_router)
api_router.include_router(admin_router)
api_router.include_router(planning_router)
api_router.include_router(consents_router)
api_router.include_router(privacy_router)


@api_router.get("/health")
async def health():
    db_status = "connected"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "unreachable"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
    }