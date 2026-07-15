"""Store 层测试(SQLite + FTS5,不依赖 chroma/API key)。

可直接 `python tests/test_store.py` 运行,也兼容 pytest。
"""
import shutil
import tempfile
from pathlib import Path

from ai_agent_memory_mcp.schema import Memory
from ai_agent_memory_mcp.store import Store


def _store():
    d = tempfile.mkdtemp()
    return Store(Path(d) / "t.db"), d


def test_upsert_get():
    s, d = _store()
    try:
        m = Memory.create(
            title="FAISS 原理", content="FAISS 是向量检索库",
            category="project", source_agent="claude-code",
        )
        s.upsert(m)
        got = s.get(m.id)
        assert got is not None
        assert got.title == "FAISS 原理"
        assert got.source_agent == "claude-code"
        assert got.tags == []
    finally:
        shutil.rmtree(d)


def test_list_and_filter():
    s, d = _store()
    try:
        s.upsert(Memory.create(title="a", content="aa", category="user", source_agent="cc"))
        s.upsert(Memory.create(title="b", content="bb", category="project", source_agent="qoder", tags=["db"]))
        assert len(s.list()) == 2
        assert len(s.list(category="user")) == 1
        assert len(s.search(agent="qoder")) == 1
        assert len(s.search(tag="db")) == 1
    finally:
        shutil.rmtree(d)


def test_fts_search():
    s, d = _store()
    try:
        s.upsert(Memory.create(title="向量检索", content="FAISS 与 Chroma 对比", category="project", source_agent="cc"))
        s.upsert(Memory.create(title="无关", content="今天天气不错", category="user", source_agent="cc"))
        res = s.fts_search("FAISS")
        assert len(res) >= 1
        assert res[0][0]  # id 非空
    finally:
        shutil.rmtree(d)


def test_delete():
    s, d = _store()
    try:
        m = Memory.create(title="x", content="y", category="process")
        s.upsert(m)
        assert s.delete(m.id) is True
        assert s.get(m.id) is None
        assert s.delete("nope") is False
    finally:
        shutil.rmtree(d)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok: {name}")
    print("all store tests passed")
