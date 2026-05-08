import json
import random
from sqlalchemy.orm import Session
from app.models.quote import Quote
from app.services.quote_search import QuoteSearchService
from app.services.relay_recall import parallel_recall
from app.services.relay_rerank import rrf_merge
from app.services.llm import get_llm_provider
from app.prompts.relay_judge import RELAY_JUDGE_SYSTEM, build_user_prompt, VALID_MODES


class RelayEngine:
    def __init__(self, db: Session):
        self.db = db
        self.search = QuoteSearchService(db)
        self.llm = get_llm_provider()

    def find_seed_quote(self, seed_text: str) -> Quote | None:
        """用户输入起始台词,用 hybrid retrieval 在库里找最匹配的一条作为 seed.

        Aligns seed selection with the downstream hybrid retrieval used in step().
        Pure embedding fails on short queries (stopwords dominate cosine similarity).
        Combined with keyword path via RRF, surfaces semantically meaningful seeds.

        See: docs/improvements/01-hybrid-seed-selection.md
        """
        keyword_hits = self.search.keyword_search(seed_text, limit=10)
        semantic_hits = [q for q, _ in self.search.semantic_search(seed_text, limit=10)]

        if not keyword_hits and not semantic_hits:
            return None

        merged = rrf_merge({
            "keyword": keyword_hits,
            "semantic": semantic_hits,
        }, top_n=5)

        return merged[0] if merged else None

    def step(
        self,
        current_quote: Quote,
        used_quote_ids: list[int],
        used_movie_titles: list[str],
    ) -> dict:
        """
        接龙单步:从 current_quote 出发,选出下一句。

        返回 dict: {quote, mode, reason, candidates}
        """
        # 1. 3 路召回
        recall = parallel_recall(
            self.search,
            current_quote.text,
            exclude_ids=used_quote_ids,
            per_path_limit=20,
        )

        # 2. RRF 重排
        ranked = rrf_merge(recall, top_n=30)

        # 3. 业务过滤:连续同电影
        filtered = [q for q in ranked if q.movie_title not in used_movie_titles[-1:]]

        if not filtered:
            # fallback: 如果过滤后空了,退回到所有 ranked
            filtered = ranked

        if not filtered:
            return None  # 真的没候选了

        # 4. 限制喂 LLM 的候选数(节省 token)
        candidates = filtered[:20]

        # 5. LLM 仲裁
        user_prompt = build_user_prompt(current_quote, candidates)
        llm_output = self.llm.chat(
            system=RELAY_JUDGE_SYSTEM,
            user=user_prompt,
            max_tokens=500,
            temperature=0.8,
        )

        # 6. 解析 LLM 输出
        # DeepSeek 偶尔会用 ```json ... ``` 包裹,先剥掉
        cleaned = llm_output.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            picks = json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "quote": candidates[0],
                "mode": "fallback",
                "reason": "LLM 输出解析失败,使用 RRF top 1",
                "candidates": [c.id for c in candidates[:5]],
            }

        # 7. 从 3 个 picks 里随机选 1(避免每次都一样)
        if not picks:
            return {
                "quote": candidates[0],
                "mode": "fallback",
                "reason": "LLM 返回空列表",
                "candidates": [c.id for c in candidates[:5]],
            }

        chosen = random.choice(picks[:3])
        chosen_quote = next((c for c in candidates if c.id == chosen["id"]), None)

        if chosen_quote is None:
            # LLM 编了一个不在候选里的 id,fallback
            chosen_quote = candidates[0]

        raw_mode = chosen.get("mode", "")
        # LLM 偶尔会输出 "2-关键词触发" 这种带序号的,做一次包含匹配
        normalized_mode = "unknown"
        for valid in VALID_MODES:
            if valid in raw_mode:
                normalized_mode = valid
                break

        return {
            "quote": chosen_quote,
            "mode": normalized_mode,
            "reason": chosen.get("reason", ""),
            "candidates": [c.id for c in candidates[:5]],
        }
