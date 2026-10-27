"""SSE 接龙接口响应时间测试。

对 GET /api/relay/stream 顺序发请求,记录:
  - 请求发出 -> 收到 seed 事件
  - 请求发出 -> 收到第 1 个 round 事件(第一轮接龙结果)
  - 请求发出 -> 收到 done 事件(整条接龙完成)
每个请求用不同的 X-Forwarded-For,避免被 30s 频率限流挡住(限流单独在 rate_limit_bench 测)。

用法 (在 backend 容器里,先按 REPORT.md 启动 bench server):
  python -m tests.benchmark.sse_latency --label mock --runs 30
  python -m tests.benchmark.sse_latency --label real --runs 5
"""
import argparse
import json
import math
import statistics
import time
from pathlib import Path

import httpx

HERE = Path(__file__).parent
RESULTS = HERE / "results"


def load_seeds() -> list[str]:
    queries = json.loads((HERE / "queries.json").read_text(encoding="utf-8"))
    return [q["query"] for q in queries if q["type"] in ("user", "short")]


def p95(values: list[float]) -> float:
    """nearest-rank P95"""
    s = sorted(values)
    return s[math.ceil(0.95 * len(s)) - 1]


def run_one(client: httpx.Client, base_url: str, seed: str, rounds: int, ip: str) -> dict:
    r = {"seed": seed, "status": None, "t_seed": None, "t_first_round": None, "t_done": None,
         "rounds": 0, "modes": [], "error": None}
    t0 = time.perf_counter()
    try:
        with client.stream("GET", f"{base_url}/api/relay/stream",
                           params={"seed": seed, "rounds": rounds},
                           headers={"X-Forwarded-For": ip}) as resp:
            r["status"] = resp.status_code
            if resp.status_code != 200:
                r["error"] = f"http {resp.status_code}"
                return r
            event = None
            for line in resp.iter_lines():
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    now = time.perf_counter() - t0
                    data = json.loads(line[5:])
                    if event == "seed":
                        r["t_seed"] = now
                    elif event == "round":
                        r["rounds"] += 1
                        r["modes"].append(data.get("mode"))
                        r["mock_llm"] = data.get("reason") == "mock"  # MockLLM 的 reason 固定是 "mock"
                        if r["t_first_round"] is None:
                            r["t_first_round"] = now
                    elif event == "done":
                        r["t_done"] = now
                        break
                    elif event == "error":
                        r["error"] = data.get("message")
                        break
    except Exception as e:  # 超时 / 连接断开都算失败
        r["error"] = f"{type(e).__name__}: {e}"
    return r


def summarize(results: list[dict], rounds: int) -> dict:
    ok = [r for r in results if r["error"] is None and r["t_done"] is not None and r["rounds"] == rounds]
    out = {"runs": len(results), "success": len(ok), "success_rate": round(len(ok) / len(results), 3)}
    for key in ("t_seed", "t_first_round", "t_done"):
        vals = [r[key] for r in ok]
        if vals:
            out[key] = {"mean_s": round(statistics.mean(vals), 3), "p50_s": round(statistics.median(vals), 3),
                        "p95_s": round(p95(vals), 3), "max_s": round(max(vals), 3)}
    all_modes = [m for r in ok for m in r["modes"]]
    out["llm_fallback_rate"] = round(all_modes.count("fallback") / len(all_modes), 3) if all_modes else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8100")
    ap.add_argument("--label", required=True, help="mock 或 real,只用于结果文件名")
    ap.add_argument("--runs", type=int, default=30)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--timeout", type=float, default=120)
    args = ap.parse_args()

    seeds = load_seeds()
    results = []
    with httpx.Client(timeout=args.timeout) as client:
        for i in range(args.runs):
            seed = seeds[i % len(seeds)]
            r = run_one(client, args.base_url, seed, args.rounds, ip=f"10.77.{i // 250}.{i % 250 + 1}")
            results.append(r)
            first = f"{r['t_first_round']:.2f}s" if r["t_first_round"] else "-"
            done = f"{r['t_done']:.2f}s" if r["t_done"] else "-"
            print(f"[{i + 1:>3}] first_round={first:>7} done={done:>7} rounds={r['rounds']} "
                  f"err={r['error']}  {seed[:40]}")

    summary = summarize(results, args.rounds)
    mock_seen = any(r.get("mock_llm") for r in results)
    summary.update({"label": args.label, "rounds_per_run": args.rounds, "mock_llm_detected": mock_seen})
    if args.label == "real" and mock_seen:
        print("WARNING: label=real 但服务端返回的是 MockLLM 结果,检查 8100 端口上跑的是哪个 server")
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"sse_{args.label}.json"
    out.write_text(json.dumps({"summary": summary, "runs": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
