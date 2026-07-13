"""Markdown 镜像读写测试(不依赖 chroma/API key)。"""
import shutil
import tempfile
from pathlib import Path

from ai_memory.schema import Memory
from ai_memory.markdown import write_markdown, delete_markdown, read_markdown, scan_markdown


def _dir():
    d = tempfile.mkdtemp()
    p = Path(d) / "memories"
    for cat in ("user", "project", "process", "agent"):
        (p / cat).mkdir(parents=True)
    return p, d


def test_write_read_roundtrip():
    p, d = _dir()
    try:
        m = Memory.create(
            title="测试记忆", content="正文内容,可含 [[链接]]",
            category="project", source_agent="cc", tags=["t1", "t2"],
        )
        path = write_markdown(p, m)
        assert path.exists()
        m2 = read_markdown(path)
        assert m2 is not None
        assert m2.id == m.id
        assert m2.title == "测试记忆"
        assert m2.content == "正文内容,可含 [[链接]]"
        assert m2.tags == ["t1", "t2"]
        assert m2.source_agent == "cc"
        assert m2.category.value == "project"
    finally:
        shutil.rmtree(d)


def test_scan_and_delete():
    p, d = _dir()
    try:
        m1 = Memory.create(title="a", content="aa", category="user", source_agent="cc")
        m2 = Memory.create(title="b", content="bb", category="process", source_agent="qoder")
        write_markdown(p, m1)
        write_markdown(p, m2)
        mems = scan_markdown(p)
        assert len(mems) == 2
        delete_markdown(p, m1.id)
        assert len(scan_markdown(p)) == 1
    finally:
        shutil.rmtree(d)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok: {name}")
    print("all markdown tests passed")
