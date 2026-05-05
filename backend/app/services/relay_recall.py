from concurrent.futures import ThreadPoolExecutor
from app.models.quote import Quote
from app.services.quote_search import QuoteSearchService


def parallel_recall(
    service: QuoteSearchService,
    query: str,
    exclude_ids: list[int] = None,
    per_path_limit: int = 20,
) -> dict[str, list[Quote]]:
    """3 路并行召回,返回每路的结果"""

    def semantic_path():
        rows = service.semantic_search(query, exclude_ids=exclude_ids, limit=per_path_limit)
        return [quote for quote, _distance in rows]

    def keyword_path():
        return service.keyword_search(query, exclude_ids=exclude_ids, limit=per_path_limit)

    def random_path():
        return service.random_sample(exclude_ids=exclude_ids, limit=per_path_limit)

    with ThreadPoolExecutor(max_workers=3) as executor:
        future_semantic = executor.submit(semantic_path)
        future_keyword = executor.submit(keyword_path)
        future_random = executor.submit(random_path)

        return {
            "semantic": future_semantic.result(),
            "keyword": future_keyword.result(),
            "random": future_random.result(),
        }