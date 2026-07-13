"""Markdown 镜像读写:每条记忆同步为 frontmatter + 正文,人工可读可编辑。"""
from __future__ import annotations

import yaml
from pathlib import Path

from .config import CATEGORIES
from .schema import Category, Memory


def _md_path(memories_dir: Path, mem: Memory) -> Path:
    return memories_dir / mem.category.value / f"{mem.id}.md"


def write_markdown(memories_dir: Path, mem: Memory) -> Path:
    p = _md_path(memories_dir, mem)
    p.parent.mkdir(parents=True, exist_ok=True)
    front = {
        "id": mem.id,
        "category": mem.category.value,
        "scope": mem.scope.value,
        "title": mem.title,
        "tags": mem.tags,
        "source_agent": mem.source_agent,
        "metadata": mem.metadata,
        "created_at": mem.created_at,
        "updated_at": mem.updated_at,
    }
    fm = yaml.safe_dump(front, allow_unicode=True, sort_keys=False).strip()
    p.write_text(f"---\n{fm}\n---\n\n{mem.content}\n", encoding="utf-8")
    return p


def delete_markdown(memories_dir: Path, mem_id: str) -> None:
    for cat in CATEGORIES:
        p = memories_dir / cat / f"{mem_id}.md"
        if p.exists():
            p.unlink()
            return


def read_markdown(path: Path) -> Memory | None:
    """从 md 文件解析回 Memory(用于 sync 重建)。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    front = yaml.safe_load(parts[1]) or {}
    content = parts[2].strip()
    return Memory(
        id=front["id"],
        category=Category(front["category"]),
        scope=front.get("scope", "project"),
        title=front["title"],
        content=content,
        tags=front.get("tags", []),
        source_agent=front.get("source_agent", "unknown"),
        metadata=front.get("metadata", {}),
        created_at=front.get("created_at", ""),
        updated_at=front.get("updated_at", ""),
    )


def scan_markdown(memories_dir: Path) -> list[Memory]:
    """扫描 memories/ 下所有 md,返回 Memory 列表(sync 用)。"""
    mems: list[Memory] = []
    for cat in CATEGORIES:
        d = memories_dir / cat
        if not d.exists():
            continue
        for p in sorted(d.glob("*.md")):
            m = read_markdown(p)
            if m:
                mems.append(m)
    return mems
