"""测试 RRF（Reciprocal Rank Fusion）合并算法的正确性。

RRF 是 line-relay hybrid retrieval 的核心算法,把 3 路召回（语义/关键词/随机）
的结果合并成一个排序。
"""
from app.services.relay_rerank import rrf_merge


class FakeQuote:
    """测试用的假 Quote 对象,不依赖数据库。

    rrf_merge 内部只用 .id 字段做去重和排序,所以不用真的 import Quote 模型 +
    启动数据库。这样测试在毫秒级跑完。
    """
    def __init__(self, id: int):
        self.id = id


def test_rrf_quote_in_multiple_paths_ranks_higher():
    """多路同时召回的 quote 应该排在前面。

    RRF 公式: score = sum(1 / (k + rank)) for each path
    出现在 2 路 (rank=2 + rank=1) 的分数 > 只出现 1 路 (rank=1) 的分数
    """
    # 准备: 3 路召回,id=2 在 semantic (rank 2) 和 keyword (rank 1) 都出现
    recall = {
        "semantic": [FakeQuote(1), FakeQuote(2), FakeQuote(3)],
        "keyword": [FakeQuote(2), FakeQuote(4)],
        "random": [FakeQuote(5)],
    }

    # 执行
    result = rrf_merge(recall, top_n=5)

    # 验证: id=2 应该排第一(在 2 路出现,总分最高)
    assert result[0].id == 2


def test_rrf_returns_at_most_top_n():
    """top_n 限制必须有效,即使输入更多也只返回前 N 条。"""
    recall = {
        "path1": [FakeQuote(i) for i in range(1, 11)],  # 10 条
    }

    result = rrf_merge(recall, top_n=3)

    assert len(result) == 3


def test_rrf_handles_empty_recall():
    """空召回不应该崩,应该返回空列表。"""
    result = rrf_merge({}, top_n=10)
    assert result == []


def test_rrf_deduplicates_quotes():
    """同一个 quote 在多路出现,结果里只能有一份(不能重复)。"""
    recall = {
        "semantic": [FakeQuote(1), FakeQuote(2)],
        "keyword": [FakeQuote(1), FakeQuote(2)],  # 完全一样的两条
    }

    result = rrf_merge(recall, top_n=10)

    # 应该只有 2 条,不是 4 条
    assert len(result) == 2
    ids = [q.id for q in result]
    assert sorted(ids) == [1, 2]
