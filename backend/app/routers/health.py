from fastapi import APIRouter
from redis import Redis
from sqlalchemy import text
from app.database import engine
from app.config import settings

router = APIRouter()

@router.get("/health")
def health_check():
    checks = {"api": "ok"}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    try:
        r = Redis.from_url(settings.redis_url)
        r.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    status = "healthy" if all(v == "ok" for v in checks.values()) else "unhealthy"
    return {"status": status, "checks": checks}