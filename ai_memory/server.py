"""MCP server:注册 8 个记忆工具(FastMCP)。

工具:remember / recall / get_memory / search_memories / update_memory /
forget / list_memories / who_am_i。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import MemoryConfig, find_project_root
from .links import resolve_links
from .markdown import delete_markdown, write_markdown
from .schema import Category, Memory, Scope
from .search import hybrid_search
from .store import Store

mcp = FastMCP(
    "ai-memory",
    instructions=(
        "Persistent memory layer across sessions and agents (Claude Code / Qoder / Cursor). "
        "Call remember() when the user says '记住/记下/沉淀/保存' a decision or fact; "
        "call recall() when the user asks '之前/上次/有没有记录/回忆/召回/历史决策/踩过的坑/接手须知'. "
        "Memory categories: user (preferences) / project (knowledge) / process (work) / agent (handoff). "
        "Memories may reference each other via [[title]] links; recall/get_memory return a 'links' field. "
        "Call who_am_i() at session start to learn the current agent and memory overview."
    ),
)

_service: "MemoryService | None" = None


class MemoryService:
    """组合 store / vector / markdown,提供高层记忆操作。"""

    def __init__(self, config: MemoryConfig):
        self.config = config
        self.store = Store(config.db_path)
        self._vector = None  # 懒加载(需 API key + chromadb)

    @property
    def vector(self):
        if self._vector is None:
            from .embedding import Embedder
            from .vector import VectorStore

            embedder = Embedder(
                api_key=self.config.embedding_api_key,
                model=self.config.embedding_model,
                base_url=self.config.embedding_base_url,
            )
            self._vector = VectorStore(self.config.chroma_dir, embedder)
        return self._vector

    def remember(self, title, content, category, tags=None, scope="project") -> Memory:
        mem = Memory.create(
            title=title,
            content=content,
            category=category,
            scope=scope,
            tags=tags or [],
            source_agent=self.config.agent,
        )
        self.store.upsert(mem)
        try:
            self.vector.upsert(mem)
        except Exception as e:
            # 向量失败不阻塞结构化存储,记录错误供排查
            mem.metadata["vector_error"] = str(e)
            self.store.upsert(mem)
        write_markdown(self.config.memories_dir, mem)
        return mem

    def recall(self, query, category=None, top_k=5) -> list[Memory]:
        ids = hybrid_search(
            query, self.store, self.vector, category=category, top_k=top_k
        )
        return [m for m in (self.store.get(i) for i in ids) if m]

    def update(self, mem_id, title=None, content=None, tags=None, category=None, scope=None):
        mem = self.store.get(mem_id)
        if not mem:
            return None
        content_changed = False
        if title is not None:
            mem.title = title
        if content is not None:
            mem.content = content
            content_changed = True
        if tags is not None:
            mem.tags = tags
        if category is not None:
            mem.category = Category(category)
        if scope is not None:
            mem.scope = Scope(scope)
        mem.touch()
        self.store.upsert(mem)
        if content_changed:
            try:
                self.vector.upsert(mem)
            except Exception:
                pass
        write_markdown(self.config.memories_dir, mem)
        return mem

    def forget(self, mem_id) -> bool:
        ok = self.store.delete(mem_id)
        if ok:
            try:
                self.vector.delete(mem_id)
            except Exception:
                pass
            delete_markdown(self.config.memories_dir, mem_id)
        return ok


def init_service(project_root: Path, agent: str) -> None:
    global _service
    cfg = MemoryConfig(Path(project_root), agent=agent)
    _service = MemoryService(cfg)


def _svc() -> MemoryService:
    if _service is None:
        init_service(find_project_root(), "unknown")
    return _service


def _brief(mem: Memory) -> dict[str, Any]:
    return {
        "id": mem.id,
        "category": mem.category.value,
        "scope": mem.scope.value,
        "title": mem.title,
        "source_agent": mem.source_agent,
        "tags": mem.tags,
        "updated_at": mem.updated_at,
    }


@mcp.tool()
def remember(
    title: str,
    content: str,
    category: str,
    tags: list[str] | None = None,
    scope: str = "project",
) -> dict:
    """存储一条持久化记忆(SQLite+Chroma+Markdown 三处同步,自动 embed)。

    当用户说"记住 / 记下 / 沉淀 / 保存"某条信息时调用。content 中可用
    [[其他记忆标题]] 引用已有记忆,recall 时会解析为关联记忆。
    category:user(用户偏好)/ project(项目知识)/ process(工作过程)/ agent(Agent 协作)。
    scope:user / project / session。
    """
    mem = _svc().remember(title, content, category, tags, scope)
    return {
        "status": "remembered",
        "id": mem.id,
        "category": mem.category.value,
        "title": mem.title,
        "source_agent": mem.source_agent,
    }


@mcp.tool()
def recall(query: str, category: str | None = None, top_k: int = 5) -> list[dict]:
    """语义 + 关键词 + 标题三路融合检索,返回最相关记忆(含正文 + [[link]] 关联)。

    当用户问"之前 / 上次 / 有没有记录 / 回忆 / 召回 / 历史决策 / 踩过的坑"时调用。
    每条记忆若 content 含 [[其他记忆标题]],返回时附 links 字段(关联记忆 id/title/category)。
    """
    svc = _svc()
    mems = svc.recall(query, category=category, top_k=top_k)
    result = []
    for m in mems:
        d = m.model_dump(mode="json")
        d["links"] = resolve_links(m.content, svc.store)
        result.append(d)
    return result


@mcp.tool()
def get_memory(id: str) -> dict:
    """按 id 取单条记忆的完整内容(含 [[link]] 关联)。已知具体 id 时调用。"""
    svc = _svc()
    mem = svc.store.get(id)
    if not mem:
        return {"error": "not found", "id": id}
    d = mem.model_dump(mode="json")
    d["links"] = resolve_links(mem.content, svc.store)
    return d


@mcp.tool()
def search_memories(
    category: str | None = None,
    tag: str | None = None,
    agent: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """按分类 / 标签 / 来源 Agent 结构化过滤(不含正文)。需精确筛选时调用。"""
    mems = _svc().store.search(category=category, tag=tag, agent=agent, limit=limit)
    return [_brief(m) for m in mems]


@mcp.tool()
def update_memory(
    id: str,
    title: str | None = None,
    content: str | None = None,
    tags: list[str] | None = None,
    category: str | None = None,
    scope: str | None = None,
) -> dict:
    """更新已有记忆;改 content 会重算向量并刷新 Markdown。修改 / 补充已有记忆时调用。"""
    mem = _svc().update(id, title, content, tags, category, scope)
    return mem.model_dump(mode="json") if mem else {"error": "not found", "id": id}


@mcp.tool()
def forget(id: str) -> dict:
    """删除一条记忆(SQLite+Chroma+Markdown 三处同步)。用户要求"删掉 / 忘掉"某条记忆时调用。"""
    ok = _svc().forget(id)
    return {"id": id, "deleted": ok}


@mcp.tool()
def list_memories(category: str | None = None) -> list[dict]:
    """列出记忆(可按分类过滤),按更新时间倒序(不含正文)。浏览 / 概览已有记忆时调用。"""
    mems = _svc().store.list(category=category)
    return [_brief(m) for m in mems]


@mcp.tool()
def who_am_i() -> dict:
    """返回当前 Agent 标识、项目根、数据目录与各分类记忆数量。会话开始时先调用,了解当前 agent 与记忆库概况。"""
    svc = _svc()
    counts = {cat: len(svc.store.list(category=cat)) for cat in ("user", "project", "process", "agent")}
    return {
        "agent": svc.config.agent,
        "project": str(svc.config.project_root),
        "data_dir": str(svc.config.data_dir),
        "counts": counts,
    }
