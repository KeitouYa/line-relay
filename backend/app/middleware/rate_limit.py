from datetime import date
from fastapi import Request, HTTPException
from redis import Redis
from app.config import settings

# 三层限流放在一个 Lua 脚本里：先检查，全部通过才计数。
# Redis 执行脚本时不会插入其他命令，所以检查和计数之间没有竞态，
# 被拒绝的请求也不会占用额度。
RATE_LIMIT_LUA = """
-- KEYS[1]=全局计数 KEYS[2]=IP计数 KEYS[3]=冷却key
-- ARGV[1]=全局上限 ARGV[2]=IP上限 ARGV[3]=冷却秒数 ARGV[4]=每日key的TTL
if tonumber(redis.call('GET', KEYS[1]) or '0') >= tonumber(ARGV[1]) then
  return {0, 'daily_limit_exceeded', 0}
end
if tonumber(redis.call('GET', KEYS[2]) or '0') >= tonumber(ARGV[2]) then
  return {0, 'ip_limit_exceeded', 0}
end
if redis.call('EXISTS', KEYS[3]) == 1 then
  return {0, 'rate_limit_exceeded', redis.call('TTL', KEYS[3])}
end
if redis.call('INCR', KEYS[1]) == 1 then redis.call('EXPIRE', KEYS[1], ARGV[4]) end
if redis.call('INCR', KEYS[2]) == 1 then redis.call('EXPIRE', KEYS[2], ARGV[4]) end
redis.call('SET', KEYS[3], '1', 'EX', ARGV[3])
return {1, 'ok', 0}
"""


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


def raise_limit_error(reason: str, retry_after: int = 0) -> None:
    """按拒绝原因抛出 429，文案和格式保持不变（前端读 detail.message）"""
    if reason == "daily_limit_exceeded":
        detail = {
            "error": reason,
            "message": "Daily relay limit reached. Come back tomorrow 🎬",
            "limit": settings.global_daily_limit,
        }
    elif reason == "ip_limit_exceeded":
        detail = {
            "error": reason,
            "message": f"You've used all {settings.ip_daily_limit} relays today. See you tomorrow 😄",
            "limit": settings.ip_daily_limit,
        }
    else:
        detail = {
            "error": "rate_limit_exceeded",
            "message": f"Too fast! Please wait {retry_after}s and try again 🙏",
            "retry_after": retry_after,
        }
    raise HTTPException(status_code=429, detail=detail)


def check_rate_limits(request: Request, consume: bool = True) -> None:
    """
    检查三层限流，任意一层超限就抛 429。

    consume=False：只读探测（fetch probe 用），不消耗配额。
    consume=True： 在一个 Lua 脚本里先检查、全部通过才计数（正式 EventSource 请求用）。
    """
    redis = get_redis()
    today = date.today().isoformat()
    ip = get_client_ip(request)
    global_key = f"global_relay_count:{today}"  # 层1：全局每日限额
    ip_key = f"ip_relay_count:{today}:{ip}"     # 层2：IP 每日限额
    freq_key = f"ip_freq:{ip}"                  # 层3：IP 频率限制

    if consume:
        script = redis.register_script(RATE_LIMIT_LUA)
        allowed, reason, retry_after = script(
            keys=[global_key, ip_key, freq_key],
            args=[settings.global_daily_limit, settings.ip_daily_limit,
                  settings.freq_limit_seconds, 90000],
        )
        if not allowed:
            raise_limit_error(reason, retry_after)
        return

    # 只读探测：只 GET 不写，和原来一样
    val = redis.get(global_key)
    if (int(val) if val else 0) >= settings.global_daily_limit:
        raise_limit_error("daily_limit_exceeded")
    val = redis.get(ip_key)
    if (int(val) if val else 0) >= settings.ip_daily_limit:
        raise_limit_error("ip_limit_exceeded")
    if redis.exists(freq_key):
        raise_limit_error("rate_limit_exceeded", redis.ttl(freq_key))
