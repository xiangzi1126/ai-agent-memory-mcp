"""search 层测试:用 stub vector 测 FTS 分支与融合逻辑(不依赖 chroma/API key)。"""
import shutil
import tempfile
from pathlib import Path

from ai_memory.schema import Memory
from ai_memory.store import Store
from ai_memory.search import hybrid_search


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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok: {name}")
    print("all search tests passed")
