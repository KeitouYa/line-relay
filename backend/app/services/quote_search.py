from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from app.models.quote import Quote, QuoteResponse
from app.services.opensubtitles import OpenSubtitlesClient
from app.services.embedding import get_embedding
from redis import Redis
from app.config import settings
import json

class QuoteSearchService:
    def __init__(self, db: Session):
        self.db = db
        self.opensubtitles = OpenSubtitlesClient()
        self.redis = Redis.from_url(settings.redis_url)

    def search_local(self, query: str, language: str = "en", limit: int = 20) -> list[Quote]:
        """从本地数据库搜索台词（全文匹配）"""
        query = query.replace("%", "\\%").replace("_", "\\_")
        return (
            self.db.query(Quote)
            .filter(
                Quote.language == language,
                Quote.text.ilike(f"%{query}%"),
            )
            .limit(limit)
            .all()
        )

    async def search_opensubtitles(self, query: str, language: str = "en") -> list[dict]:
        """从OpenSubtitles搜索（带Redis缓存）"""
        cache_key = f"os_search:{language}:{query}"
        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        results = await self.opensubtitles.search_subtitles(query, language)
        if results:
            self.redis.setex(cache_key, 86400, json.dumps(results))  # 缓存24小时
        return results

    def search(self, query: str, language: str = "en", limit: int = 20) -> list[Quote]:
        """主搜索入口：优先本地数据库，结果不足时补充OpenSubtitles"""
        local_results = self.search_local(query, language, limit)
        return local_results

    def semantic_search(
        self,
        query: str,
        language: str = "en",
        limit: int = 20,
        exclude_ids: list[int] = None,
        min_length: int = 15,
    ) -> list[tuple[Quote, float]]:
        """RAG语义搜索:返回 (Quote, cosine_distance) 元组列表

        Args:
            min_length: 台词最短字符数,过滤掉 "I will." 这种没语义信息量的短台词
        """
        query_embedding = get_embedding(query)
        distance_expr = Quote.embedding.cosine_distance(query_embedding)

        q = (
            self.db.query(Quote, distance_expr.label("distance"))
            .filter(
                Quote.language == language,
                Quote.embedding.isnot(None),
                func.length(Quote.text) >= min_length,
            )
            .order_by(distance_expr)
        )

        if exclude_ids:
            q = q.filter(Quote.id.notin_(exclude_ids))

        return q.limit(limit).all()

    def keyword_search(
        self,
        query: str,
        language: str = "en",
        limit: int = 20,
        exclude_ids: list[int] = None,
        min_length: int = 15,
    ) -> list[Quote]:
        """全文检索召回:用 PostgreSQL tsvector 关键词命中"""
        from sqlalchemy import text as sa_text, func

        # 用 plainto_tsquery 把用户输入转成查询(自动处理停用词)
        ts_query = func.plainto_tsquery('english', query)
        ts_vector = func.to_tsvector('english', Quote.text)

        q = (
            self.db.query(Quote)
            .filter(
                Quote.language == language,
                func.length(Quote.text) >= min_length,
                ts_vector.op('@@')(ts_query),
            )
            .order_by(func.ts_rank(ts_vector, ts_query).desc())
        )

        if exclude_ids:
            q = q.filter(Quote.id.notin_(exclude_ids))

        return q.limit(limit).all()

    def random_sample(
        self,
        language: str = "en",
        limit: int = 20,
        exclude_ids: list[int] = None,
        min_length: int = 15,
    ) -> list[Quote]:
        """随机抽样召回:覆盖跨场景断裂模式"""
        from sqlalchemy import func

        q = (
            self.db.query(Quote)
            .filter(
                Quote.language == language,
                func.length(Quote.text) >= min_length,
            )
            .order_by(func.random())  # PostgreSQL 原生 RANDOM()
        )

        if exclude_ids:
            q = q.filter(Quote.id.notin_(exclude_ids))

        return q.limit(limit).all()
