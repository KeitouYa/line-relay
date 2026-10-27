"""Hybrid Search (keyword + pgvector + RRF) vs pgvector-only 的 Top-5 检索对比。

两种方法用同一个 QuoteSearchService、同样的过滤条件(language=en, min_length=15,
排除查询本身那条台词)。Hybrid 的做法和 RelayEngine.find_seed_quote 完全一致:
keyword top10 + semantic top10 -> rrf_merge -> top5。

用法 (在 backend 容器里):
  python -m tests.benchmark.retrieval_eval build   # 从数据库固定抽样,生成 queries.json(只需一次)
  python -m tests.benchmark.retrieval_eval run     # 跑两种检索,导出 labels.csv 给人工标注
  python -m tests.benchmark.retrieval_eval score   # 读取标注好的 labels.csv,计算 Precision@5
"""
import csv
import json
import random
import statistics
import sys
import time
from pathlib import Path

from sqlalchemy import text as sa_text

from app.database import SessionLocal
from app.scripts.eval_relay import SEEDS
from app.services.quote_search import QuoteSearchService
from app.services.relay_rerank import rrf_merge

HERE = Path(__file__).parent
RESULTS = HERE / "results"
QUERIES_FILE = HERE / "queries.json"
RESULTS_FILE = RESULTS / "retrieval_results.json"
LABELS_FILE = RESULTS / "labels.csv"
SCORES_FILE = RESULTS / "retrieval_scores.json"

TOP_K = 5
PER_PATH_LIMIT = 10  # 和 find_seed_quote 一致
N_SHORT = 30
N_LONG = 30


def build_queries():
    """固定抽样:按 md5(id) 排序,同一份数据每次抽到的都一样。"""
    db = SessionLocal()
    sql = """
        SELECT id, text, movie_title FROM quotes
        WHERE language = 'en' AND embedding IS NOT NULL
          AND array_length(regexp_split_to_array(trim(text), '\\s+'), 1) BETWEEN :lo AND :hi
        ORDER BY md5(id::text) LIMIT :n
    """
    short = db.execute(sa_text(sql), {"lo": 3, "hi": 6, "n": N_SHORT}).fetchall()
    long = db.execute(sa_text(sql), {"lo": 10, "hi": 40, "n": N_LONG}).fetchall()
    db.close()

    queries = []
    # user: 用户手打的经典台词(复用 eval_relay 的 SEEDS + improvements 文档里的例子)
    for s in SEEDS + ["I love you!"]:
        queries.append({"type": "user", "query": s, "source_id": None, "source_movie": None})
    # short: 库里的短台词(3-6 个词),模拟用户输入的短 seed
    # long: 库里的长台词(10+ 个词),模拟接龙中用上一句全文做查询
    for kind, rows in (("short", short), ("long", long)):
        for r in rows:
            queries.append({"type": kind, "query": r.text, "source_id": r.id, "source_movie": r.movie_title})

    for i, q in enumerate(queries, start=1):
        q["query_id"] = i

    QUERIES_FILE.write_text(json.dumps(queries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(queries)} queries -> {QUERIES_FILE}")


def run_eval(force: bool = False):
    if LABELS_FILE.exists() and not force:
        sys.exit(f"{LABELS_FILE} 已存在(可能已标注),不覆盖。确实要重跑请加 --force")

    queries = json.loads(QUERIES_FILE.read_text(encoding="utf-8"))
    db = SessionLocal()
    service = QuoteSearchService(db)
    RESULTS.mkdir(exist_ok=True)

    records = []
    for q in queries:
        exclude = [q["source_id"]] if q["source_id"] else None

        t0 = time.perf_counter()
        semantic = [quote for quote, _ in service.semantic_search(q["query"], limit=PER_PATH_LIMIT, exclude_ids=exclude)]
        t_sem = time.perf_counter() - t0
        keyword = service.keyword_search(q["query"], limit=PER_PATH_LIMIT, exclude_ids=exclude)
        t_hybrid = time.perf_counter() - t0

        vector_top = semantic[:TOP_K]  # 和 semantic_search(limit=5) 结果相同,省一次 embedding 调用
        hybrid_top = rrf_merge({"keyword": keyword, "semantic": semantic}, top_n=TOP_K)

        quotes = {x.id: x for x in vector_top + hybrid_top}
        records.append({
            **q,
            "vector_ids": [x.id for x in vector_top],
            "hybrid_ids": [x.id for x in hybrid_top],
            "keyword_hits": len(keyword),
            "vector_ms": round(t_sem * 1000, 1),
            "hybrid_ms": round(t_hybrid * 1000, 1),
            "quotes": {str(i): {"text": x.text, "movie": x.movie_title} for i, x in quotes.items()},
        })
        print(f"[{q['query_id']:>3}] kw={len(keyword):>2}  {q['query'][:60]}")

    db.close()
    RESULTS_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    # 盲标:两种方法结果合并去重、打乱顺序,标注人看不到来自哪个方法
    rng = random.Random(42)
    with LABELS_FILE.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["query_id", "query_type", "query", "quote_id", "movie_title", "quote_text", "relevant"])
        for r in records:
            ids = list(r["quotes"].keys())
            rng.shuffle(ids)
            for qid in ids:
                item = r["quotes"][qid]
                w.writerow([r["query_id"], r["type"], r["query"], qid, item["movie"], item["text"], ""])

    print_unlabeled_stats(records)
    print(f"\nwrote {RESULTS_FILE}\nwrote {LABELS_FILE}  <- 请在 relevant 列填 1(相关) 或 0(不相关)")


def print_unlabeled_stats(records):
    """不需要标注就能得到的客观数字"""
    n = len(records)
    overlap = [len(set(r["vector_ids"]) & set(r["hybrid_ids"])) for r in records]
    top1_diff = sum(1 for r in records if r["vector_ids"][:1] != r["hybrid_ids"][:1])
    kw_empty = sum(1 for r in records if r["keyword_hits"] == 0)
    print(f"\nqueries: {n}")
    print(f"avg top-5 overlap (vector vs hybrid): {statistics.mean(overlap):.2f} / {TOP_K}")
    print(f"top-1 differs: {top1_diff}/{n}")
    print(f"keyword path returned 0 hits: {kw_empty}/{n}")
    print(f"avg latency  vector-only: {statistics.mean(r['vector_ms'] for r in records):.0f} ms  "
          f"hybrid: {statistics.mean(r['hybrid_ms'] for r in records):.0f} ms")


def score():
    records = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
    labels = {}
    unlabeled = 0
    with LABELS_FILE.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            v = row["relevant"].strip()
            if v not in ("0", "1"):
                unlabeled += 1
                continue
            labels[(int(row["query_id"]), row["quote_id"])] = int(v)
    if unlabeled:
        sys.exit(f"还有 {unlabeled} 行没标注(relevant 需要是 0 或 1),先标完再算分")

    def p_at_k(r, key):
        return sum(labels[(r["query_id"], str(i))] for i in r[key]) / TOP_K

    rows = []
    for r in records:
        rows.append({"query_id": r["query_id"], "type": r["type"],
                     "vector": p_at_k(r, "vector_ids"), "hybrid": p_at_k(r, "hybrid_ids")})

    summary = {}
    for group in ["all", "user", "short", "long"]:
        g = [x for x in rows if group == "all" or x["type"] == group]
        if not g:
            continue
        summary[group] = {
            "n": len(g),
            "vector_p5": round(statistics.mean(x["vector"] for x in g), 3),
            "hybrid_p5": round(statistics.mean(x["hybrid"] for x in g), 3),
            "hybrid_better": sum(1 for x in g if x["hybrid"] > x["vector"]),
            "tie": sum(1 for x in g if x["hybrid"] == x["vector"]),
            "vector_better": sum(1 for x in g if x["hybrid"] < x["vector"]),
        }

    SCORES_FILE.write_text(json.dumps({"summary": summary, "per_query": rows}, indent=2), encoding="utf-8")
    print("| group | n | vector P@5 | hybrid P@5 | hybrid better / tie / worse |")
    print("|---|---|---|---|---|")
    for k, s in summary.items():
        print(f"| {k} | {s['n']} | {s['vector_p5']:.3f} | {s['hybrid_p5']:.3f} | "
              f"{s['hybrid_better']} / {s['tie']} / {s['vector_better']} |")
    print(f"\nwrote {SCORES_FILE}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "build":
        build_queries()
    elif cmd == "run":
        run_eval(force="--force" in sys.argv)
    elif cmd == "score":
        score()
    else:
        print(__doc__)
