"""Benchmark 专用 app 入口。

直接复用 app.main:app,只在这个测试进程里按环境变量把 LLM / embedding 换成 mock,
业务代码不改。用法见 REPORT.md:
  uvicorn tests.benchmark.bench_app:app --port 8100

环境变量:
  BENCH_MOCK_LLM=1          LLM 换成 MockLLM(不调 DeepSeek,零费用)
  BENCH_MOCK_LLM_DELAY=0.0  MockLLM 每次调用的模拟耗时(秒)
  BENCH_MOCK_EMBEDDING=1    embedding 换成确定性假向量(不调 OpenAI,只用于限流测试)
"""
import hashlib
import json
import os
import random
import re
import time

import app.services.quote_search as quote_search
import app.services.relay_engine as relay_engine
from app.services.llm.base import LLMProvider
from app.services.embedding import EMBEDDING_DIM


class MockLLM(LLMProvider):
    """按 relay_judge 的 JSON 格式返回候选列表里的前 3 个 id"""

    def chat(self, system: str, user: str, max_tokens: int = 1000, temperature: float = 0.7) -> str:
        delay = float(os.getenv("BENCH_MOCK_LLM_DELAY", "0"))
        if delay > 0:
            time.sleep(delay)
        # 候选行格式: [123] 《Movie》: "text"
        ids = [int(x) for x in re.findall(r"^\[(\d+)\]", user, re.M)][:3]
        return json.dumps([{"id": i, "mode": "keyword-trigger", "reason": "mock"} for i in ids])

    @property
    def name(self) -> str:
        return "mock"


def fake_embedding(text: str) -> list[float]:
    """同一文本永远得到同一个向量,不发网络请求"""
    rnd = random.Random(hashlib.md5(text.encode()).hexdigest())
    return [rnd.uniform(-1, 1) for _ in range(EMBEDDING_DIM)]


if os.getenv("BENCH_MOCK_LLM") == "1":
    relay_engine.get_llm_provider = lambda: MockLLM()

if os.getenv("BENCH_MOCK_EMBEDDING") == "1":
    quote_search.get_embedding = fake_embedding

from app.main import app  # noqa: E402,F401
