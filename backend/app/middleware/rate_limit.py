from datetime import date
from fastapi import Request, HTTPException
from redis import Redis
from app.config import settings


def get_redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def get_client_ip(request: Request) -> str:
    """获取真实客户端 IP，兼容 Cloudflare 代理"""
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def check_rate_limits(request: Request, consume: bool = True) -> None:
    """
    检查三层限流，任意一层超限就抛 429。

    consume=False：只读探测（fetch probe 用），不消耗配额。
    consume=True： 消耗配额（正式 EventSource 请求用）。
    """
    redis = get_redis()
    today = date.today().isoformat()
    ip = get_client_ip(request)

    # 层1：全局每日限额
    global_key = f"global_relay_count:{today}"
    if consume:
        global_count = redis.incr(global_key)
        if global_count == 1:
            redis.expire(global_key, 90000)
        global_exceeded = global_count > settings.global_daily_limit
    else:
        val = redis.get(global_key)
        global_count = int(val) if val else 0
        global_exceeded = global_count >= settings.global_daily_limit

    if global_exceeded:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "daily_limit_exceeded",
                "message": "Daily relay limit reached. Come back tomorrow 🎬",
                "limit": settings.global_daily_limit,
            },
        )

    # 层2：IP 每日限额
    ip_key = f"ip_relay_count:{today}:{ip}"
    if consume:
        ip_count = redis.incr(ip_key)
        if ip_count == 1:
            redis.expire(ip_key, 90000)
        ip_exceeded = ip_count > settings.ip_daily_limit
    else:
        val = redis.get(ip_key)
        ip_count = int(val) if val else 0
        ip_exceeded = ip_count >= settings.ip_daily_limit

    if ip_exceeded:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "ip_limit_exceeded",
                "message": f"You've used all {settings.ip_daily_limit} relays today. See you tomorrow 😄",
                "limit": settings.ip_daily_limit,
            },
        )

    # 层3：IP 频率限制
    freq_key = f"ip_freq:{ip}"
    freq_ttl = settings.freq_limit_seconds
    if consume:
        if not redis.set(freq_key, "1", nx=True, ex=freq_ttl):
            retry_after = redis.ttl(freq_key)
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": f"Too fast! Please wait {retry_after}s and try again 🙏",
                    "retry_after": retry_after,
                },
            )
    else:
        # 只读探测：检查 key 是否存在
        if redis.exists(freq_key):
            retry_after = redis.ttl(freq_key)
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": f"Too fast! Please wait {retry_after}s and try again 🙏",
                    "retry_after": retry_after,
                },
            )
