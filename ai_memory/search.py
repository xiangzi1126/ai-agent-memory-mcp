"""混合检索:Chroma 向量相似度 + FTS5 关键词相关度,加权融合(min-max 归一化)。"""
from __future__ import annotations

from .store import Store
from .vector import VectorStore

VECTOR_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3


def _min_max(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    rng = hi - lo or 1.0
    return [(v - lo) / rng for v in values]


def hybrid_search(
    query: str,
    store: Store,
    vector: VectorStore,
    category: str | None = None,
    top_k: int = 5,
) -> list[str]:
    """返回按融合分数排序的 memory id 列表。"""
    scores: dict[str, float] = {}

    # 向量分支:distance 越小越相似 -> 归一化后反转
    try:
        vec_results = vector.query(query, category=category, top_k=max(top_k * 2, 10))
    except Exception:
        vec_results = []
    if vec_results:
        ids, dists = zip(*vec_results)
        norm = _min_max(list(dists))
        for mid, d in zip(ids, norm):
            scores[mid] = scores.get(mid, 0.0) + VECTOR_WEIGHT * (1.0 - d)

    # 关键词分支:BM25 rank 越小越相关 -> 归一化后反转
    fts_results = store.fts_search(query, limit=max(top_k * 2, 10))
    if fts_results:
        ids, ranks = zip(*fts_results)
        norm = _min_max(list(ranks))
        for mid, r in zip(ids, norm):
            scores[mid] = scores.get(mid, 0.0) + KEYWORD_WEIGHT * (1.0 - r)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [mid for mid, _ in ranked]
