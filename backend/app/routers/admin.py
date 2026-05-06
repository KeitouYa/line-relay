from fastapi import APIRouter, Header, HTTPException
from redis import Redis
from app.config import settings

router = APIRouter()

ADMIN_TOKEN = "line-relay-reset-2026"


@router.post("/reset-limits")
def reset_limits(x_admin_token: str = Header(..., alias="X-Admin-Token")):
    """清空所有限流计数器 (Redis keys: global_relay_count / ip_relay_count / ip_freq)"""
    if x_admin_token != ADMIN_TOKEN:
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