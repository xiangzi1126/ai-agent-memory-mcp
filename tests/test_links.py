"""[[link]] 互链解析测试。"""
import shutil
import tempfile
from pathlib import Path

from ai_agent_memory_mcp.links import extract_links, resolve_links
from ai_agent_memory_mcp.schema import Memory
from ai_agent_memory_mcp.store import Store


def _store():
    d = tempfile.mkdtemp()
    return Store(Path(d) / "t.db"), d


def test_extract_links():
    content = "见 [[FAISS 原理]] 和 [[向量检索]] 详情"
    assert extract_links(content) == ["FAISS 原理", "向量检索"]
    assert extract_links("无链接内容") == []


def test_resolve_links():
    s, d = _store()
    try:
        m1 = Memory.create(title="FAISS 原理", content="FAISS 是向量库", category="project")
        m2 = Memory.create(
            title="向量检索", content="ANN 搜索,相关 [[FAISS 原理]]", category="project"
        )
        s.upsert(m1)
        s.upsert(m2)
        links = resolve_links(m2.content, s)
        assert len(links) == 1
        assert links[0]["title"] == "FAISS 原理"
        assert links[0]["id"] == m1.id
        # 无链接 -> 空
        assert resolve_links(m1.content, s) == []
        # 引用不存在的标题 -> 静默跳过
        m3 = Memory.create(title="x", content="见 [[不存在]]", category="process")
        assert resolve_links(m3.content, s) == []
    finally:
        shutil.rmtree(d)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok: {name}")
    print("all links tests passed")
