"""工作日记:agent 总结每次交互,人读时间线。

与 store.py 的语义记忆分工:这里记「这次交互做了什么」(人读,时间线),
AI 平时不读;仅 search_journal 按需查。写入由 journal_entry 工具触发
(agent 完成一次请求后主动调)。数据独立于 memory.db,存 logs/journal.db
+ logs/journal.md(追加式时间线)。
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from .schema import now_iso

_SCHEMA = """
CREATE TABLE IF NOT EXISTS journals (
    id              TEXT PRIMARY KEY,
    session_id      TEXT,                 -- 可空(MCP 取不到 session,agent 可选传)
    ts              TEXT NOT NULL,        -- 调用时间(时间线排序)
    agent           TEXT NOT NULL,        -- claude-code / qoder / cursor
    user            TEXT,                 -- 问的人(从 profile)
    question        TEXT NOT NULL,
    answer_summary  TEXT NOT NULL,
    key_points      TEXT NOT NULL DEFAULT '[]',  -- JSON 数组
    open_question   TEXT                  -- 可空:留给用户的问题/待定项
);
CREATE INDEX IF NOT EXISTS idx_journal_ts ON journals(ts);
CREATE INDEX IF NOT EXISTS idx_journal_agent ON journals(agent);
CREATE VIRTUAL TABLE IF NOT EXISTS journals_fts USING fts5(
    id, question, answer_summary, key_points, tokenize='trigram'
);
"""

PREVIEW_LEN = 400


@dataclass
class JournalEntry:
    """单条工作日记。id 由调用方(uuid)生成,ts/agent/user 由 server 补。"""

    id: str
    agent: str
    question: str
    answer_summary: str
    ts: str = ""
    key_points: list[str] = field(default_factory=list)
    open_question: str | None = None
    session_id: str | None = None
    user: str | None = None


class JournalStore:
    def __init__(self, log_dir: Path):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.log_dir / "journal.db"
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def _md_path_for(self, ts: str) -> Path:
        """按日期定位 MD 文件:logs/YYYY-MM-DD.md(ts 前 10 位为日期)。"""
        date = (ts or now_iso())[:10]
        return self.log_dir / f"{date}.md"

    def add(self, e: JournalEntry) -> None:
        """写 SQLite + FTS,并按日期追加 MD 到 logs/YYYY-MM-DD.md。"""
        if not e.ts:
            e.ts = now_iso()
        kp = json.dumps(e.key_points, ensure_ascii=False)
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO journals "
                "(id, session_id, ts, agent, user, question, answer_summary, key_points, open_question) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (e.id, e.session_id, e.ts, e.agent, e.user,
                 e.question, e.answer_summary, kp, e.open_question),
            )
            c.execute("DELETE FROM journals_fts WHERE id = ?", (e.id,))
            c.execute(
                "INSERT INTO journals_fts(id, question, answer_summary, key_points) "
                "VALUES (?, ?, ?, ?)",
                (e.id, e.question, e.answer_summary, kp),
            )
        try:
            md_path = self._md_path_for(e.ts)
            if not md_path.exists():
                md_path.write_text(f"# {e.ts[:10]} 工作日记\n\n", encoding="utf-8")
            with open(md_path, "a", encoding="utf-8") as f:
                f.write(self._format_md(e))
        except Exception:
            pass  # MD 是副产物,写失败不阻塞(SQLite 已是主源)

    @staticmethod
    def _format_md(e: JournalEntry) -> str:
        """单条日记的 MD 片段(按确认的样品格式)。"""
        head = f"## {e.ts} · {e.agent}"
        if e.user:
            head += f"（{e.user}）"
        lines = [head, "", f"**Q:** {e.question}", "", e.answer_summary]
        if e.key_points:
            lines += ["", "**关键点:**"] + [f"- {p}" for p in e.key_points]
        if e.open_question:
            lines += ["", f"**待定:** {e.open_question}"]
        return "\n".join(lines) + "\n\n"

    def search(
        self,
        query: str,
        date_from: str | None = None,
        date_to: str | None = None,
        agent: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """FTS5 MATCH + snippet;query 含 FTS 特殊字符时退回 LIKE。"""
        q = (query or "").strip()
        if not q:
            return []
        with self._conn() as c:
            rows = self._fts_search(c, q, date_from, date_to, agent, limit)
            if not rows:  # FTS 报错(None)或无命中(含 trigram 短 query 漏匹配) -> LIKE 兜底
                rows = self._like_search(c, q, date_from, date_to, agent, limit)
        return [self._row_to_hit(r) for r in rows]

    @staticmethod
    def _fts_search(c, q, date_from, date_to, agent, limit):
        extra, args = "", [q]
        if date_from:
            extra += " AND j.ts >= ?"; args.append(date_from)
        if date_to:
            extra += " AND j.ts <= ?"; args.append(date_to)
        if agent:
            extra += " AND j.agent = ?"; args.append(agent)
        args.append(limit)
        sql = (
            "SELECT j.id, j.ts, j.agent, j.user, j.question, "
            "snippet(journals_fts, 2, '[', ']', '...', 32) AS snippet, "
            "substr(j.answer_summary, 1, ?) AS preview, j.open_question "
            "FROM journals_fts f JOIN journals j ON j.id = f.id "
            "WHERE journals_fts MATCH ?" + extra + " ORDER BY rank LIMIT ?"
        )
        try:
            return c.execute(sql, [PREVIEW_LEN, *args]).fetchall()
        except sqlite3.OperationalError:
            return None  # FTS 语法错误 -> 调用方退回 LIKE

    @staticmethod
    def _like_search(c, q, date_from, date_to, agent, limit):
        clauses = ["question LIKE ? OR answer_summary LIKE ? OR key_points LIKE ?"]
        args = [f"%{q}%", f"%{q}%", f"%{q}%"]
        if date_from:
            clauses.append("ts >= ?"); args.append(date_from)
        if date_to:
            clauses.append("ts <= ?"); args.append(date_to)
        if agent:
            clauses.append("agent = ?"); args.append(agent)
        args.append(limit)
        where = "(" + clauses[0] + ")" + "".join(" AND " + cl for cl in clauses[1:])
        sql = (
            "SELECT id, ts, agent, user, question, NULL AS snippet, "
            "substr(answer_summary, 1, ?) AS preview, open_question "
            "FROM journals WHERE " + where + " ORDER BY ts DESC LIMIT ?"
        )
        return c.execute(sql, [PREVIEW_LEN, *args]).fetchall()

    @staticmethod
    def _row_to_hit(r) -> dict:
        return {
            "id": r["id"],
            "ts": r["ts"],
            "agent": r["agent"],
            "user": r["user"],
            "question": r["question"],
            "snippet": r["snippet"],
            "preview": r["preview"],
            "open_question": r["open_question"],
        }

    def list(self, agent: str | None = None, limit: int = 50) -> list[dict]:
        with self._conn() as c:
            if agent:
                rows = c.execute(
                    "SELECT * FROM journals WHERE agent = ? ORDER BY ts DESC LIMIT ?",
                    (agent, limit),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM journals ORDER BY ts DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    def stats(self) -> dict:
        with self._conn() as c:
            total = c.execute("SELECT COUNT(*) AS n FROM journals").fetchone()["n"]
            by_agent = {
                r["agent"]: r["n"]
                for r in c.execute(
                    "SELECT agent, COUNT(*) AS n FROM journals GROUP BY agent"
                ).fetchall()
            }
            rng = c.execute("SELECT MIN(ts) AS lo, MAX(ts) AS hi FROM journals").fetchone()
        return {
            "entries": total,
            "by_agent": by_agent,
            "earliest": rng["lo"],
            "latest": rng["hi"],
        }
