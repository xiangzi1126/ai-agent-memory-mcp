"""SQLite 结构化存储 + FTS5 关键词检索。

memories 表为结构化主源;memories_fts 为冗余全文索引(title+content),
二者在 CRUD 时手动同步。trigram 分词器改善中文子串匹配。
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .schema import Category, Memory

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id           TEXT PRIMARY KEY,
    category     TEXT NOT NULL,
    scope        TEXT NOT NULL,
    title        TEXT NOT NULL,
    content      TEXT NOT NULL,
    tags         TEXT NOT NULL DEFAULT '[]',
    source_agent TEXT NOT NULL DEFAULT 'unknown',
    metadata     TEXT NOT NULL DEFAULT '{}',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
CREATE INDEX IF NOT EXISTS idx_memories_agent ON memories(source_agent);
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    id, title, content, tokenize='trigram'
);
"""

_UPSERT = """
INSERT OR REPLACE INTO memories
(id, category, scope, title, content, tags, source_agent, metadata, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


class Store:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
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

    @staticmethod
    def _row_to_memory(row: sqlite3.Row) -> Memory:
        return Memory(
            id=row["id"],
            category=Category(row["category"]),
            scope=row["scope"],
            title=row["title"],
            content=row["content"],
            tags=json.loads(row["tags"]),
            source_agent=row["source_agent"],
            metadata=json.loads(row["metadata"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def upsert(self, mem: Memory) -> None:
        with self._conn() as c:
            c.execute(
                _UPSERT,
                (
                    mem.id,
                    mem.category.value,
                    mem.scope.value,
                    mem.title,
                    mem.content,
                    json.dumps(mem.tags, ensure_ascii=False),
                    mem.source_agent,
                    json.dumps(mem.metadata, ensure_ascii=False),
                    mem.created_at,
                    mem.updated_at,
                ),
            )
            c.execute("DELETE FROM memories_fts WHERE id = ?", (mem.id,))
            c.execute(
                "INSERT INTO memories_fts(id, title, content) VALUES(?, ?, ?)",
                (mem.id, mem.title, mem.content),
            )

    def get(self, mem_id: str) -> Memory | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
            return self._row_to_memory(row) if row else None

    def delete(self, mem_id: str) -> bool:
        with self._conn() as c:
            cur = c.execute("DELETE FROM memories WHERE id = ?", (mem_id,))
            c.execute("DELETE FROM memories_fts WHERE id = ?", (mem_id,))
            return cur.rowcount > 0

    def list(self, category: str | None = None, limit: int = 200) -> list[Memory]:
        with self._conn() as c:
            if category:
                rows = c.execute(
                    "SELECT * FROM memories WHERE category = ? ORDER BY updated_at DESC LIMIT ?",
                    (category, limit),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?", (limit,)
                ).fetchall()
            return [self._row_to_memory(r) for r in rows]

    def search(
        self,
        category: str | None = None,
        tag: str | None = None,
        agent: str | None = None,
        limit: int = 50,
    ) -> list[Memory]:
        clauses: list[str] = []
        args: list = []
        if category:
            clauses.append("category = ?")
            args.append(category)
        if agent:
            clauses.append("source_agent = ?")
            args.append(agent)
        if tag:
            clauses.append("tags LIKE ?")
            args.append(f'%"{tag}"%')
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM memories{where} ORDER BY updated_at DESC LIMIT ?"
        args.append(limit)
        with self._conn() as c:
            rows = c.execute(sql, args).fetchall()
            return [self._row_to_memory(r) for r in rows]

    def fts_search(self, query: str, limit: int = 10) -> list[tuple[str, float]]:
        """关键词检索,返回 (id, rank);rank 越小越相关(BM25)。

        query 含 FTS5 特殊字符(点号/星号/引号/连字符等)触发 MATCH 语法错误时,
        退回 LIKE 子串匹配并返回 (id, 0.0);与 journal.py 的兜底策略一致,
        避免 hybrid_search 因关键词分支异常而整体崩溃。
        """
        q = (query or "").strip()
        if not q:
            return []
        with self._conn() as c:
            try:
                rows = c.execute(
                    "SELECT id, rank FROM memories_fts WHERE memories_fts MATCH ? ORDER BY rank LIMIT ?",
                    (query, limit),
                ).fetchall()
                return [(r["id"], float(r["rank"])) for r in rows]
            except sqlite3.OperationalError:
                # FTS5 语法错误(特殊字符如 . * " - ) -> LIKE 子串兜底
                rows = c.execute(
                    "SELECT id FROM memories "
                    "WHERE title LIKE ? OR content LIKE ? "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (f"%{q}%", f"%{q}%", limit),
                ).fetchall()
                return [(r["id"], 0.0) for r in rows]

    def all_ids(self) -> list[str]:
        with self._conn() as c:
            return [r["id"] for r in c.execute("SELECT id FROM memories").fetchall()]

    def find_by_title(self, title: str) -> Memory | None:
        """按精确标题查找(供 [[link]] 解析)。"""
        with self._conn() as c:
            row = c.execute("SELECT * FROM memories WHERE title = ?", (title,)).fetchone()
            return self._row_to_memory(row) if row else None
