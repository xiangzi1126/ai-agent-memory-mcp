"""search 层测试:用 stub vector 测 FTS 分支与融合逻辑(不依赖 chroma/API key)。"""
import shutil
import tempfile
from pathlib import Path

from ai_agent_memory_mcp.schema import Memory
from ai_agent_memory_mcp.store import Store
from ai_agent_memory_mcp.search import hybrid_search


class StubVector:
    """模拟 VectorStore。"""

    def __init__(self, results=None, raise_=False):
        self._results = results or []
        self._raise = raise_

    def query(self, text, category=None, top_k=5):
        if self._raise:
            raise RuntimeError("no api key")
        return self._results


def test_fts_only_when_vector_fails():
    d = tempfile.mkdtemp()
    try:
        s = Store(Path(d) / "t.db")
        s.upsert(Memory.create(title="向量检索", content="FAISS 向量库对比", category="project", source_agent="cc"))
        s.upsert(Memory.create(title="其它", content="无关内容", category="user", source_agent="cc"))
        v = StubVector(raise_=True)
        ids = hybrid_search("FAISS", s, v, top_k=5)
        assert len(ids) >= 1
    finally:
        shutil.rmtree(d)


def test_fusion():
    d = tempfile.mkdtemp()
    try:
        s = Store(Path(d) / "t.db")
        m1 = Memory.create(title="FAISS", content="向量检索库", category="project", source_agent="cc")
        m2 = Memory.create(title="Chroma", content="嵌入式向量库", category="project", source_agent="cc")
        s.upsert(m1)
        s.upsert(m2)
        v = StubVector(results=[(m1.id, 0.1), (m2.id, 0.5)])
        ids = hybrid_search("向量", s, v, top_k=2)
        assert m1.id in ids
    finally:
        shutil.rmtree(d)


def test_fts_special_chars_fallback_to_like():
    """query 含 FTS5 特殊字符(点号等)时退回 LIKE,hybrid_search 不崩且仍命中。

    回归:修复前 'aamm v0.2.0' 里的点号触发 fts5: syntax error near ".",
    异常穿透 recall 工具。向量分支给空结果,迫使命中只能来自关键词分支。
    """
    d = tempfile.mkdtemp()
    try:
        s = Store(Path(d) / "t.db")
        m = Memory.create(
            title="aamm v0.2.0", content="重启验证闭环", category="project", source_agent="cc"
        )
        s.upsert(m)
        v = StubVector(results=[])  # 向量分支无贡献
        ids = hybrid_search("aamm v0.2.0", s, v, top_k=5)
        assert m.id in ids
    finally:
        shutil.rmtree(d)


def test_empty_query_short_circuits():
    """空/空白 query 直接返回 [],不调 vector(避免无意义 embedding 调用)。"""
    d = tempfile.mkdtemp()
    try:
        s = Store(Path(d) / "t.db")
        s.upsert(Memory.create(title="x", content="y", category="project", source_agent="cc"))
        called = []

        class V:
            def query(self, text, category=None, top_k=5):
                called.append(text)
                return []

        assert hybrid_search("   ", s, V(), top_k=3) == []
        assert hybrid_search("", s, V(), top_k=3) == []
        assert called == []  # vector.query 未被调用
    finally:
        shutil.rmtree(d)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok: {name}")
    print("all search tests passed")
