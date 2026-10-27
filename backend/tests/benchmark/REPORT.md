# LineRelay Benchmark Report

First run: 2026-10-21. Every number comes from a real run on a local machine. Raw data is in `results/`.

## 1. Test Environment

| Item | Value |
|---|---|
| Machine | Local laptop, AMD Ryzen 7 5800H, Docker Desktop (16 cores / 7.7 GB RAM inside containers) |
| Setup | `docker compose`: backend (Python 3.11, FastAPI), Postgres 16 + pgvector, Redis 7 |
| Data | 34,908 quotes from 20 films, all with 1536-dim embeddings |
| LLM | DeepSeek `deepseek-v4-flash` (real runs) / MockLLM (mock runs) |
| Embedding | OpenAI `text-embedding-3-small` (real calls in both the retrieval and SSE tests) |
| Network | Calls OpenAI / DeepSeek directly from the machine; no Cloudflare and no production deployment |

Note: these are **local, single-machine** results, not production data.

## 2. Test Files

```
backend/tests/benchmark/
  bench_app.py          Test app entry: reuses app.main:app and swaps the LLM / embedding for mocks via env vars
  retrieval_eval.py     Test 1: hybrid vs pgvector-only retrieval
  sse_latency.py        Test 2: SSE response time
  rate_limit_bench.py   Test 3: Redis rate limiting under concurrency
  queries.json          The fixed set of 66 queries
  results/              All raw results
```

The benchmarks do not change any app code; mocks only apply inside the test process. The file names don't start with `test_`, so CI's `pytest` does not collect them (the existing 10 tests still pass).

## 3. Test 1: Hybrid Search Retrieval Quality

### Method

- **Query set (66 fixed queries)**: built by `retrieval_eval build` and saved in `queries.json`.
  - `user`, 6 queries: the 5 seeds in `eval_relay.py`, plus `I love you!` from the hybrid seed-selection fix
  - `short`, 30 queries: quotes from the database with 3–6 words, like a short seed a user would type
  - `long`, 30 queries: quotes from the database with 10–40 words, like the full previous line used as the query during a relay
  - Sampling uses `ORDER BY md5(id)`, so the same data always gives the same queries.
- **Both methods use the same conditions**: both call the existing `QuoteSearchService` with the same filters (`language=en`, `min_length=15`, and the query's own quote excluded).
  - pgvector-only: `semantic_search`, top 5
  - Hybrid: `keyword_search` top 10 + `semantic_search` top 10, merged with `rrf_merge`, top 5. This is exactly the logic in `RelayEngine.find_seed_quote`.
- **Manual labeling**: the results of both methods are merged, de-duplicated and shuffled into `results/labels.csv` (368 rows). The labeler can't see which method found each result (blind labeling).
- **Metric**: Precision@5 = relevant results in the top 5 / 5, averaged over all queries.

### Results that need no labeling (real data)

| Query type | Count | Keyword path returned 0 | Avg top-5 overlap | Top 1 differs | Top 5 identical |
|---|---|---|---|---|---|
| user | 6 | 1 | 3.17 / 5 | 5 | 1 |
| short | 30 | 18 | 4.10 / 5 | 10 | 18 |
| long | 30 | 29 | 5.00 / 5 | 0 | 30 |
| all | 66 | 48 | 4.42 / 5 | 15 | 49 |

Average latency: pgvector-only 289 ms, hybrid 293 ms (both include one OpenAI embedding call).

### Precision@5

**Not measured yet; it needs manual labels.** This report does not make up an accuracy number or an improvement percentage.

How to label: open `results/labels.csv` and fill the `relevant` column:

- `1`: the quote clearly matches the query in topic, meaning or a key word (a user who typed the query would feel the result "fits")
- `0`: not related, or it only shares stopwords like "you" or "the"

Then run `python -m tests.benchmark.retrieval_eval score`. It prints a P@5 table per group and writes `results/retrieval_scores.json`.

## 4. Test 2: SSE Response Time

### Method

- Endpoint: `GET /api/relay/stream?seed=...&rounds=5`, one request at a time (concurrency 1).
- Seeds come from the `user` and `short` queries in `queries.json`.
- Three times are recorded, measured from when the client sends the request: the `seed` event, the first `round` event, and the `done` event.
- A run succeeds when it gets HTTP 200, 5 `round` events and `done`, with no `error` event.
- Every request uses a different `X-Forwarded-For`, so the 30 s cooldown doesn't block it. The test server uses its own Redis DB 15.
- **Mock**: MockLLM returns the first 3 candidate ids. This measures the time spent outside the LLM, with no LLM cost.
- **Real**: real DeepSeek flash calls, only 10 runs (50 LLM calls) to keep the cost down.

### Results (real data)

| Mode | Runs | Success rate | First round mean / P50 / P95 | Full relay mean / P50 / P95 | LLM fallback |
|---|---|---|---|---|---|
| Mock LLM | 30 | 100% (30/30) | 0.41 / 0.38 / 0.62 s | 1.22 / 1.20 / 1.53 s | 0% |
| Real DeepSeek | 10 | 100% (10/10) | 2.14 / 2.07 / 2.70 s | 9.58 / 9.53 / 10.23 s | 0% (0 of 50 rounds) |

- The `seed` event arrives after about 0.21–0.24 s on average.
- Using the means, the LLM takes about 87% of the full relay time in real mode ((9.58 − 1.22) / 9.58).
- Real mode has only 10 samples, so its P95 is the same as the maximum. Treat it as a rough reference.

### Regression run (2026-10-22, after the rate-limit fix)

Same method as above: same script, same test-server config, same seed order. The only change is 30 real DeepSeek runs instead of 10. The old 10-run result is saved in `results/sse_real_10runs.json`.

| Real DeepSeek | Runs | Success rate | First round mean / P50 / P95 | Full 5 rounds mean / P50 / P95 | Fallback |
|---|---|---|---|---|---|
| Old (before the fix) | 10 | 100% (10/10) | 2.14 / 2.07 / 2.70 s | 9.58 / 9.53 / 10.23 s | 0 of 50 rounds |
| New (after the fix) | 30 | 100% (30/30) | 2.21 / 2.11 / 2.87 s | 9.89 / 9.56 / 12.56 s | 0 of 150 rounds |

- Modes across the 150 rounds: twist 60, keyword-trigger 58, break 27, follow-up 5. No fallbacks and no unrecognized modes.
- The means changed by about 3% (first round +0.07 s, full relay +0.31 s). The full-relay P95 went from 10.23 s to 12.56 s mostly because 30 samples caught 3 slow runs of 12–13.5 s; with only 10 samples, the old P95 was simply the maximum.
- The first 10 runs (same seeds as the old test) averaged 2.50 s to the first round and 10.59 s in total; the last 20 averaged 2.07 s and 9.54 s. A gap this big inside one run suggests the DeepSeek API's response time itself varies (this is a guess).
- The only code change was the rate-limit check, which runs once at the start of each request. Timed on its own: 0.21 ms per call for the new Lua check vs 0.63 ms for the old separate commands. So the code change did not cause the latency difference.
- The retrieval code did not change. All 30 relays found a seed and finished 5 rounds, so retrieval works normally.
- The 20/50 concurrency rate-limit test was rerun on the latest code and matched section 5's after-fix results exactly: allowed 1 / 10 / 1 / 10, Redis global counter 1 / 10 / 1 / 10, and the counter equals the allowed requests in all 4 cases.

## 5. Test 3: Redis Rate Limiting Under Concurrency

### Method

- Test-server config: `GLOBAL_DAILY_LIMIT=10`, `IP_DAILY_LIMIT=3`, `FREQ_LIMIT_SECONDS=30`, and **4 uvicorn workers** (separate processes, so they really hit Redis at the same time). The LLM and embedding are mocked, so there is no API cost.
- Only Redis DB 15 is cleared before each scenario.
- `asyncio` prepares N requests and releases them at the same moment. The requests go straight to `/api/relay/stream` without the `X-Relay-Probe` header, the way a script or `curl` would, skipping the frontend probe.
- Two scenarios:
  - `same_ip`: all from one IP; expect exactly 1 allowed
  - `distinct_ip`: every request from a different IP; expect exactly 10 allowed (the global limit)

### Results (real data)

| Requests | Scenario | 200 | 429 | Expected 200 / 429 | Limit correct | Redis global counter |
|---|---|---|---|---|---|---|
| 20 | same_ip | 1 | 19 | 1 / 19 | yes | 20 |
| 20 | distinct_ip | 10 | 10 | 10 / 10 | yes | 20 |
| 50 | same_ip | 1 | 49 | 1 / 49 | yes | 50 |
| 50 | distinct_ip | 10 | 40 | 10 / 40 | yes | 50 |

- In all 4 scenarios the allowed and rejected counts match the config. Every extra request got 429; there were no 500s or other status codes.
- With 4 workers hitting Redis at once, nothing extra got through, because `INCR` and `SET NX` are atomic.
- **The Redis counters don't match the allowed requests**; see issue 1 below. The table above is from before the fix; the raw file is `results/rate_limit_before.json`.

### Rerun after the fix (2026-10-22)

After issue 1 was fixed (see section 6), the same script was rerun with the same config and 4 workers. The raw file is `results/rate_limit.json`.

| Requests | Scenario | 200 | 429 | Limit correct | Redis global counter (before → after) | Counter = allowed |
|---|---|---|---|---|---|---|
| 20 | same_ip | 1 | 19 | yes | 20 → 1 | yes |
| 20 | distinct_ip | 10 | 10 | yes | 20 → 10 | yes |
| 50 | same_ip | 1 | 49 | yes | 50 → 1 | yes |
| 50 | distinct_ip | 10 | 40 | yes | 50 → 10 | yes |

- The allowed and rejected counts are exactly the same as before the fix; only the counters changed.
- For the same IP, the rejection reasons changed from "global quota used 10 / IP quota used 7 / cooldown 2" to "cooldown" for all 19 (all 49 when N=50), so users see the right "Too fast!" message.
- Emulating the frontend flow (probe → real request → probe again within 30 s → direct request from a script): the counter becomes 1; the second probe returns 429 "Too fast! Please wait 30s"; the direct request also gets 429, and the counter stays at 1.
- The existing 10 `pytest` tests still pass.

## 6. Issues Found (issue 1 fixed; the others are recorded only)

1. **[Fixed 2026-10-22] Rejected requests used up quota (when the probe is skipped).** `check_rate_limits` ran `INCR` first and checked the limit after, with no rollback. So a request that got 429 still added 1 to the global and per-IP counters.
   - **The normal page flow was mostly fine (from reading the code, not measured separately).** `useRelaySSE` sends a read-only probe first and stops on 429 without sending the real request. So when a user clicks one time after another, the counts are right.
   - **But the server doesn't require the probe.** Any request without the `X-Relay-Probe` header is counted. This test, like a script or `curl`, called `/api/relay/stream` directly. Measured: one IP sent 20 requests at once, 1 was allowed, but the global counter reached 20, and 10 of the rejections already said `daily_limit_exceeded`. With the default config (global 100/day), about 100 direct requests from one IP would use up the global quota for every user for the rest of the day.
   - **The page flow had a small gap too.** When two tabs click at almost the same time, both probes pass. The second real request gets 429, but its counts were already added.
   - **The fix.** In `rate_limit.py`, the three checks and the counting for a real request now run in one Redis Lua script: check first, and count only if all three pass. Redis runs a script without any other command in the middle, so nothing extra gets through under concurrency. The probe is still read-only, and the 429 JSON format and messages are unchanged, so the frontend did not change. Results after the fix are in section 5.
   - **Why not `GET` then `INCR` in Python.** Measured on Redis DB 15, 5 runs each: with 50 different IPs at once and a limit of 10, separate commands let 49–50 through, while Lua let exactly 10 through every time; with 20 requests at once from one IP, separate commands let 17–20 through, while Lua let exactly 1 through every time.
   - **Also removed.** slowapi was installed, but no endpoint used it. Its source shows that the default fixed-window strategy also increments before checking, and that it checks multiple limits one by one without rolling back, so it could not fix this. Removed `limiter.py`, its setup in `main.py`, and the dependency in `requirements.txt`.
2. **The keyword path barely works for long queries.** `keyword_search` uses `plainto_tsquery`, which requires every word in the query to appear (AND). It returned 0 results for 29 of the 30 long queries and 18 of the 30 short ones. Each relay step uses the full previous line as the query, so in `step()` hybrid is mostly pgvector + random. This is a design limit, not a crash bug.
3. **(From reading the code, not measured)** The SSE generator is `async`, but the database, embedding and LLM calls inside it are blocking, so they block the event loop. When one worker serves several SSE streams at once, they likely queue up. These tests sent requests one at a time and did not cover that case.

## 7. How to Reproduce

```bash
docker compose up -d --build backend

# Test 1 (about 66 embedding calls)
docker compose exec backend python -m tests.benchmark.retrieval_eval build   # already done, can skip
docker compose exec backend python -m tests.benchmark.retrieval_eval run     # add --force if labels.csv already exists
# After labeling results/labels.csv:
docker compose exec backend python -m tests.benchmark.retrieval_eval score

# Test 2: mock (drop BENCH_MOCK_LLM=1 for the real LLM, then use --label real --runs 30)
docker compose exec -d -e REDIS_URL=redis://redis:6379/15 -e BENCH_MOCK_LLM=1 \
  -e GLOBAL_DAILY_LIMIT=100000 -e IP_DAILY_LIMIT=100000 -e FREQ_LIMIT_SECONDS=1 \
  backend uvicorn tests.benchmark.bench_app:app --host 0.0.0.0 --port 8100
docker compose exec backend python -m tests.benchmark.sse_latency --label mock --runs 30

# Test 3 (stop the 8100 server above first)
docker compose exec -d -e REDIS_URL=redis://redis:6379/15 -e BENCH_MOCK_LLM=1 -e BENCH_MOCK_EMBEDDING=1 \
  -e GLOBAL_DAILY_LIMIT=10 -e IP_DAILY_LIMIT=3 -e FREQ_LIMIT_SECONDS=30 \
  backend uvicorn tests.benchmark.bench_app:app --host 0.0.0.0 --port 8100 --workers 4
docker compose exec backend python -m tests.benchmark.rate_limit_bench --global-limit 10 --ip-limit 3 --freq-seconds 30

# Stop the test server afterwards
docker compose restart backend
```

Note: always stop the old 8100 server before switching between mock and real mode. Otherwise the new server fails to bind the port, and requests still go to the old one. `sse_latency` checks for this: if `--label real` receives MockLLM results, it prints a warning and writes `mock_llm_detected: true` in the results.
