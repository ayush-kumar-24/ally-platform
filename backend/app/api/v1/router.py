from fastapi import APIRouter
from sqlalchemy import text

from app.api.v1.auth.routes import router as auth_router
from app.api.v1.profile.routes import router as profile_router
from app.db.session import engine

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(profile_router)


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