"""混合检索:向量相似度 + FTS5 关键词 + 标题/标签匹配,三路加权融合。

embedding 内容为 title+tags+content 拼接(见 Memory.embed_text),标题/标签
信息进入向量;再用三路融合 + 候选扩大提升命中率。
"""
from __future__ import annotations

from .store import Store
from .vector import VectorStore

VECTOR_WEIGHT = 0.6
KEYWORD_WEIGHT = 0.25
TITLE_WEIGHT = 0.15


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
    """三路融合:向量 + 关键词 + 标题/标签匹配,返回按分数排序的 id 列表。"""
    scores: dict[str, float] = {}
    candidates: set[str] = set()
    q_lower = query.lower().strip()
    candidate_k = max(top_k * 3, 15)

    # 1. 向量分支:distance 越小越相似 -> 归一化后反转
    try:
        vec_results = vector.query(query, category=category, top_k=candidate_k)
    except Exception:
        vec_results = []
    if vec_results:
        ids, dists = zip(*vec_results)
        norm = _min_max(list(dists))
        for mid, d in zip(ids, norm):
            scores[mid] = scores.get(mid, 0.0) + VECTOR_WEIGHT * (1.0 - d)
            candidates.add(mid)

    # 2. 关键词分支:BM25 rank 越小越相关 -> 归一化后反转
    fts_results = store.fts_search(query, limit=candidate_k)
    if fts_results:
        ids, ranks = zip(*fts_results)
        norm = _min_max(list(ranks))
        for mid, r in zip(ids, norm):
            scores[mid] = scores.get(mid, 0.0) + KEYWORD_WEIGHT * (1.0 - r)
            candidates.add(mid)

    # 3. 标题/标签子串匹配 bonus:查询词出现在标题或标签时加分
    if q_lower:
        for mid in candidates:
            mem = store.get(mid)
            if not mem:
                continue
            if q_lower in mem.title.lower():
                scores[mid] = scores.get(mid, 0.0) + TITLE_WEIGHT
            elif any(q_lower in t.lower() for t in mem.tags):
                scores[mid] = scores.get(mid, 0.0) + TITLE_WEIGHT * 0.5

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [mid for mid, _ in ranked]
