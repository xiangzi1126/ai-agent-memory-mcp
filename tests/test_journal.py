"""JournalStore 测试:add/search/MD 渲染/stats,不依赖 LLM/API key。

可直接 `python tests/test_journal.py` 运行,也兼容 pytest。
"""
import shutil
import tempfile
from pathlib import Path

from ai_agent_memory_mcp.journal import JournalEntry, JournalStore


def _store():
    d = Path(tempfile.mkdtemp())
    return JournalStore(d), d


def test_add_writes_db_fts_and_md():
    s, d = _store()
    try:
        s.add(JournalEntry(
            id="j1", agent="claude-code", ts="2026-07-15T10:00:00+00:00",
            question="怎么改名", answer_summary="统一为 aamm",
            key_points=["三统一", "短前缀"], open_question="推不推",
        ))
        assert s.stats()["entries"] == 1
        md = (d / "2026-07-15.md").read_text(encoding="utf-8")
        assert "怎么改名" in md
        assert "**Q:**" in md
        assert "**关键点:**" in md
        assert "- 三统一" in md
        assert "**待定:**" in md and "推不推" in md
    finally:
        shutil.rmtree(d)


def test_add_writes_dated_md():
    """MD 按日期分文件:跨日落不同文件,同日追加同一文件,日期头只写一次。"""
    s, d = _store()
    try:
        s.add(JournalEntry(id="j1", agent="cc", ts="2026-07-14T10:00:00+00:00",
                           question="day1", answer_summary="a1"))
        s.add(JournalEntry(id="j2", agent="cc", ts="2026-07-15T10:00:00+00:00",
                           question="day2", answer_summary="a2"))
        s.add(JournalEntry(id="j3", agent="cc", ts="2026-07-15T11:00:00+00:00",
                           question="day2b", answer_summary="a3"))
        md14 = (d / "2026-07-14.md").read_text(encoding="utf-8")
        md15 = (d / "2026-07-15.md").read_text(encoding="utf-8")
        assert "day1" in md14 and "day2" not in md14
        # 同日两条都进 15 号文件,day1 不串味
        assert "day2" in md15 and "day2b" in md15 and "day1" not in md15
        assert md15.count("# 2026-07-15 工作日记") == 1  # 日期头只写一次
    finally:
        shutil.rmtree(d)


def test_search_fts_hits_question():
    s, d = _store()
    try:
        s.add(JournalEntry(id="j1", agent="cc", question="排查recall报错",
                           answer_summary="历史列名问题已修", key_points=[]))
        s.add(JournalEntry(id="j2", agent="cc", question="改名为aamm",
                           answer_summary="三统一", key_points=[]))
        hits = s.search("recall")
        assert len(hits) == 1
        assert hits[0]["id"] == "j1"
        assert hits[0]["snippet"] is not None  # FTS snippet
    finally:
        shutil.rmtree(d)


def test_search_like_fallback_on_special_char():
    """query 含 FTS 特殊字符(点号)退回 LIKE,不报错。"""
    s, d = _store()
    try:
        s.add(JournalEntry(id="j1", agent="cc", question="fts5 syntax error near .",
                           answer_summary="降级 LIKE", key_points=[]))
        hits = s.search("near .")  # 点号触发 FTS 错误 -> LIKE
        assert len(hits) == 1
        assert hits[0]["id"] == "j1"
    finally:
        shutil.rmtree(d)


def test_search_empty_query_returns_empty():
    s, d = _store()
    try:
        s.add(JournalEntry(id="j1", agent="cc", question="x", answer_summary="y", key_points=[]))
        assert s.search("") == []
        assert s.search("   ") == []
    finally:
        shutil.rmtree(d)


def test_md_omits_optional_sections_when_empty():
    """无 key_points/open_question 时 MD 不含关键点/待定段。"""
    s, d = _store()
    try:
        s.add(JournalEntry(id="j1", agent="cc", ts="2026-07-15T10:00:00+00:00",
                           question="Q1", answer_summary="A1"))
        md = (d / "2026-07-15.md").read_text(encoding="utf-8")
        assert "Q1" in md and "A1" in md
        assert "关键点" not in md
        assert "待定" not in md
    finally:
        shutil.rmtree(d)


def test_list_and_stats():
    s, d = _store()
    try:
        s.add(JournalEntry(id="j1", agent="claude-code", ts="2026-07-15T10:00:00+00:00",
                           question="q1", answer_summary="a1"))
        s.add(JournalEntry(id="j2", agent="qoder", ts="2026-07-15T11:00:00+00:00",
                           question="q2", answer_summary="a2"))
        all_e = s.list(limit=10)
        assert len(all_e) == 2
        assert all_e[0]["ts"] == "2026-07-15T11:00:00+00:00"  # 倒序
        only_cc = s.list(agent="claude-code")
        assert len(only_cc) == 1 and only_cc[0]["id"] == "j1"
        st = s.stats()
        assert st["entries"] == 2
        assert st["by_agent"] == {"claude-code": 1, "qoder": 1}
    finally:
        shutil.rmtree(d)


def test_add_auto_timestamp_when_missing():
    """ts 为空时 add 自动补 now_iso。"""
    s, d = _store()
    try:
        s.add(JournalEntry(id="j1", agent="cc", question="q", answer_summary="a"))  # ts 默认 ""
        rows = s.list()
        assert rows[0]["ts"]  # 非空
    finally:
        shutil.rmtree(d)


def test_search_short_query_falls_back_to_like():
    """trigram 对 <3 字符 query 漏匹配,FTS 空时退回 LIKE 命中。"""
    s, d = _store()
    try:
        s.add(JournalEntry(id="j1", agent="cc", question="怎么统一目录名",
                           answer_summary="改成aamm", key_points=[]))
        hits = s.search("目录")  # 2 字符,trigram 漏 -> LIKE 兜底
        assert len(hits) == 1
        assert hits[0]["id"] == "j1"
    finally:
        shutil.rmtree(d)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok: {name}")
    print("all journal tests passed")
