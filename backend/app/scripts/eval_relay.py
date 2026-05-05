"""跑多个 seed 验证接龙质量,汇总成表格。

用法:
  docker compose exec backend python -m app.scripts.eval_relay
"""
import time
from collections import Counter
from app.database import SessionLocal
from app.services.relay_engine import RelayEngine


SEEDS = [
    "I love you",
    "You shall not pass",
    "Why so serious?",
    "To be or not to be",
    "Run, Forrest, run",
]

ROUNDS_PER_SEED = 5


def run_one(engine: RelayEngine, seed: str) -> dict:
    """跑一次接龙,返回汇总信息"""
    start = time.time()

    seed_quote = engine.find_seed_quote(seed)
    if seed_quote is None:
        return {"seed": seed, "error": "找不到匹配的起始台词"}

    current = seed_quote
    used_ids = [seed_quote.id]
    used_movies = [seed_quote.movie_title]
    chain = [{
        "round": 0,
        "text": seed_quote.text,
        "movie": seed_quote.movie_title,
        "mode": "seed",
        "reason": "-",
    }]
    fallback_count = 0

    for r in range(1, ROUNDS_PER_SEED + 1):
        result = engine.step(current, used_ids, used_movies)
        if result is None:
            chain.append({
                "round": r, "text": "[no candidates]", "movie": "-",
                "mode": "error", "reason": "",
            })
            break

        if result["mode"] == "fallback":
            fallback_count += 1

        next_q = result["quote"]
        chain.append({
            "round": r,
            "text": next_q.text,
            "movie": next_q.movie_title,
            "mode": result["mode"],
            "reason": result["reason"],
        })
        current = next_q
        used_ids.append(next_q.id)
        used_movies.append(next_q.movie_title)

    elapsed = time.time() - start
    return {
        "seed": seed,
        "chain": chain,
        "elapsed": elapsed,
        "fallback_count": fallback_count,
        "modes": Counter(c["mode"] for c in chain if c["mode"] not in ("seed", "error")),
        "movies": Counter(c["movie"] for c in chain),
    }


def print_chain(result: dict):
    """打印一次接龙的详细链路"""
    print(f"\n{'=' * 70}")
    print(f"SEED: {result['seed']}")
    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return
    print(f"耗时: {result['elapsed']:.1f}s | Fallback: {result['fallback_count']}/{ROUNDS_PER_SEED}")
    print(f"{'-' * 70}")
    for c in result["chain"]:
        print(f"  [Round {c['round']}] [{c['mode']:12s}] 《{c['movie']}》")
        print(f"      \"{c['text']}\"")
        if c["mode"] not in ("seed", "error", "fallback"):
            print(f"      理由: {c['reason']}")


def print_summary(results: list[dict]):
    """汇总统计"""
    print(f"\n\n{'=' * 70}")
    print("汇总统计")
    print(f"{'=' * 70}")

    valid = [r for r in results if "error" not in r]
    print(f"成功 seed: {len(valid)}/{len(results)}")

    if not valid:
        return

    # 4 模式分布
    all_modes = Counter()
    for r in valid:
        all_modes.update(r["modes"])
    total_steps = sum(all_modes.values())
    print(f"\n模式分布(总 {total_steps} 步):")
    for mode, count in all_modes.most_common():
        pct = count * 100 / total_steps if total_steps else 0
        print(f"  {mode:15s}: {count:3d} ({pct:5.1f}%)")

    # Fallback 率
    total_fallback = sum(r["fallback_count"] for r in valid)
    fb_rate = total_fallback * 100 / total_steps if total_steps else 0
    print(f"\nLLM 失败率(fallback): {total_fallback}/{total_steps} ({fb_rate:.1f}%)")

    # 平均延迟
    avg_time = sum(r["elapsed"] for r in valid) / len(valid)
    print(f"平均延迟: {avg_time:.1f}s 总 ({avg_time/ROUNDS_PER_SEED:.1f}s/round)")

    # 电影多样性
    all_movies = Counter()
    for r in valid:
        all_movies.update(r["movies"])
    print(f"\n出现频次最高的电影 top 10:")
    for movie, count in all_movies.most_common(10):
        print(f"  {count:3d}x {movie}")


def main():
    db = SessionLocal()
    engine = RelayEngine(db)

    print(f"开始评估 {len(SEEDS)} 个 seed,每个 {ROUNDS_PER_SEED} 轮接龙\n")

    results = []
    for seed in SEEDS:
        print(f"\n>>> 跑: {seed!r}")
        result = run_one(engine, seed)
        results.append(result)
        print_chain(result)

    print_summary(results)
    db.close()


if __name__ == "__main__":
    main()
