from app.models.quote import Quote


def rrf_merge(
    recall_results: dict[str, list[Quote]],
    k: int = 60,
    top_n: int = 30,
) -> list[Quote]:
    """
    Reciprocal Rank Fusion: 合并多路召回结果。

    每条 quote 的 RRF 得分 = sum(1 / (k + rank_i)) for each path it appears in

    k 是平滑参数,默认 60(论文经验值),让 rank 1 和 rank 2 之间差距不会过大
    """
    scores: dict[int, float] = {}  # quote_id -> rrf_score
    quote_map: dict[int, Quote] = {}  # quote_id -> Quote 对象

    for path_name, quotes in recall_results.items():
        for rank, quote in enumerate(quotes, start=1):
            scores[quote.id] = scores.get(quote.id, 0.0) + 1.0 / (k + rank)
            quote_map[quote.id] = quote

    # 按 RRF 分数降序
    sorted_ids = sorted(scores.keys(), key=lambda qid: scores[qid], reverse=True)

    return [quote_map[qid] for qid in sorted_ids[:top_n]]