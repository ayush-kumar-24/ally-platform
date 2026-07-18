from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine

api_router = APIRouter(prefix="/api/v1")


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