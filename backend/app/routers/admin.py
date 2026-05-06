from fastapi import APIRouter, Header, HTTPException
from redis import Redis
from sqlalchemy import text
from app.database import engine, Base
from app.config import settings

router = APIRouter()


@router.post("/reset-limits")
def reset_limits(x_admin_token: str = Header(..., alias="X-Admin-Token")):
    """清空所有限流计数器 (Redis keys: global_relay_count / ip_relay_count / ip_freq)"""
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Forbidden")

    r = Redis.from_url(settings.redis_url)
    deleted = 0
    for prefix in ("global_relay_count", "ip_relay_count", "ip_freq"):
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor=cursor, match=f"{prefix}:*", count=100)
            if keys:
                deleted += r.delete(*keys)
            if cursor == 0:
                break

    return {"status": "ok", "deleted_keys": deleted}


@router.post("/setup-db")
def setup_db(x_admin_token: str = Header(..., alias="X-Admin-Token")):
    """一键安装 pgvector 扩展 + 建表（手动调一次，永久生效）"""
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Forbidden")

    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    Base.metadata.create_all(bind=engine)

    return {"status": "ok", "message": "pgvector extension + tables ready"}