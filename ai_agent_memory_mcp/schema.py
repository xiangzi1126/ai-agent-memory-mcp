"""记忆数据模型与分类定义。"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Category(str, Enum):
    """记忆四大分类。"""

    USER = "user"          # 用户偏好:技术背景 / 开发习惯 / 回答偏好
    PROJECT = "project"    # 项目知识:架构 / 选型 / 目录 / 设计决策
    PROCESS = "process"    # 工作过程:已解决问题 / Bug 原因 / 排查方法 / 经验
    AGENT = "agent"        # Agent 协作:谁做过什么 / 接手须知


class Scope(str, Enum):
    USER = "user"
    PROJECT = "project"
    SESSION = "session"


def _slugify(text: str, max_len: int = 50) -> str:
    """标题转 slug(保留中文),用于生成可读 id。"""
    text = text.strip().lower()
    text = re.sub(r"[^\w一-鿿]+", "-", text, flags=re.UNICODE)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len] or "memory"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Memory(BaseModel):
    """单条记忆。SQLite 为结构化主源,Chroma 存向量,Markdown 存镜像。"""

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    category: Category
    scope: Scope = Scope.PROJECT
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    source_agent: str = "unknown"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)

    @classmethod
    def create(
        cls,
        *,
        title: str,
        content: str,
        category: Category | str,
        scope: Scope | str = Scope.PROJECT,
        tags: list[str] | None = None,
        source_agent: str = "unknown",
        metadata: dict[str, Any] | None = None,
        id: str | None = None,
    ) -> "Memory":
        ts = now_iso()
        return cls(
            id=id or f"{_slugify(title)}-{uuid4().hex[:6]}",
            category=Category(category),
            scope=Scope(scope),
            title=title,
            content=content,
            tags=tags or [],
            source_agent=source_agent,
            metadata=metadata or {},
            created_at=ts,
            updated_at=ts,
        )

    def touch(self) -> "Memory":
        self.updated_at = now_iso()
        return self

    def to_chroma_metadata(self) -> dict[str, str]:
        """Chroma metadata 只接受标量;tags 序列化为逗号串。"""
        return {
            "category": self.category.value,
            "scope": self.scope.value,
            "title": self.title,
            "tags": ",".join(self.tags),
            "source_agent": self.source_agent,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def embed_text(self) -> str:
        """用于 embedding 的拼接文本(标题+标签+正文),让标题/标签信息进入向量。"""
        parts = [self.title]
        if self.tags:
            parts.append(" ".join(self.tags))
        parts.append(self.content)
        return "\n".join(parts)
