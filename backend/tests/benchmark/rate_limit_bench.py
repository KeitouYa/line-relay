"""Redis 限流并发测试。

同时发 20 / 50 个请求到 /api/relay/stream,检查:
  - 成功(200)和被限流(429)的数量是否符合配置
  - Redis 里的计数是否准确

两个场景:
  same_ip      全部请求来自同一个 IP -> 频率限流只放行 1 个
  distinct_ip  每个请求 IP 不同     -> 全局每日限额只放行 global_limit 个

只连 bench server 专用的 Redis DB(默认 15),每个场景前会 FLUSHDB 这个 DB,
不碰业务用的 DB 0。

用法 (在 backend 容器里,先按 REPORT.md 启动限流用的 bench server):
  python -m tests.benchmark.rate_limit_bench --global-limit 10 --ip-limit 3 --freq-seconds 30
"""
import argparse
import asyncio
import json
from collections import Counter
from datetime import date
from pathlib import Path

import httpx
from redis import Redis

HERE = Path(__file__).parent
RESULTS = HERE / "results"


async def one_request(client: httpx.AsyncClient, url: str, ip: str, start: asyncio.Event) -> tuple[int, str]:
    await start.wait()  # 所有请求就绪后同时放出
    async with client.stream("GET", url, params={"seed": "I love you", "rounds": 2},
                             headers={"X-Forwarded-For": ip}) as resp:
        if resp.status_code == 429:
            body = json.loads(await resp.aread())
            return 429, body["detail"]["error"]
        return resp.status_code, ""  # 200 时拿到状态码就断开,不跑完整接龙


async def burst(base_url: str, n: int, same_ip: bool) -> list[tuple[int, str]]:
    url = f"{base_url}/api/relay/stream"
    start = asyncio.Event()
    limits = httpx.Limits(max_connections=n, max_keepalive_connections=0)
    async with httpx.AsyncClient(timeout=60, limits=limits) as client:
        tasks = [asyncio.create_task(one_request(client, url, "10.88.0.1" if same_ip else f"10.88.1.{i + 1}", start))
                 for i in range(n)]
        await asyncio.sleep(0.2)
        start.set()
        return await asyncio.gather(*tasks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8100")
    ap.add_argument("--redis-url", default="redis://redis:6379/15")
    ap.add_argument("--global-limit", type=int, required=True, help="必须和 bench server 的 GLOBAL_DAILY_LIMIT 一致")
    ap.add_argument("--ip-limit", type=int, required=True, help="必须和 bench server 的 IP_DAILY_LIMIT 一致")
    ap.add_argument("--freq-seconds", type=int, required=True, help="必须和 bench server 的 FREQ_LIMIT_SECONDS 一致")
    args = ap.parse_args()

    if args.redis_url.rstrip("/").endswith("/0") or args.redis_url.count("/") < 3:
        raise SystemExit("拒绝使用 Redis DB 0(业务数据),请指定专用 DB,例如 redis://redis:6379/15")
    redis = Redis.from_url(args.redis_url, decode_responses=True)
    today = date.today().isoformat()

    report = []
    for n in (20, 50):
        for same_ip in (True, False):
            redis.flushdb()
            results = asyncio.run(burst(args.base_url, n, same_ip))
            status = Counter(s for s, _ in results)
            reasons = Counter(r for s, r in results if s == 429)

            if same_ip:
                expected_ok = min(1, args.ip_limit, args.global_limit)
                ip_keys = [f"ip_relay_count:{today}:10.88.0.1"]
            else:
                expected_ok = min(n, args.global_limit, n * args.ip_limit)
                ip_keys = [f"ip_relay_count:{today}:10.88.1.{i + 1}" for i in range(n)]

            global_count = int(redis.get(f"global_relay_count:{today}") or 0)
            ip_count_sum = sum(int(redis.get(k) or 0) for k in ip_keys)

            row = {
                "requests": n,
                "scenario": "same_ip" if same_ip else "distinct_ip",
                "ok_200": status.get(200, 0),
                "rejected_429": status.get(429, 0),
                "other_status": {k: v for k, v in status.items() if k not in (200, 429)},
                "expected_200": expected_ok,
                "expected_429": n - expected_ok,
                "limit_correct": status.get(200, 0) == expected_ok and status.get(429, 0) == n - expected_ok,
                "reject_reasons": dict(reasons),
                "redis_global_count": global_count,
                "redis_ip_count_sum": ip_count_sum,
                # 如果只统计真正放行的请求,计数应该等于 ok_200
                "counter_equals_successes": global_count == status.get(200, 0),
            }
            report.append(row)
            print(json.dumps(row, ensure_ascii=False))

    redis.flushdb()
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / "rate_limit.json"
    out.write_text(json.dumps({"config": vars(args), "results": report}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
