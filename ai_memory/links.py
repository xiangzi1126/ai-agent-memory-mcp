"""[[link]] 互链解析:记忆 content 里的 [[标题]] 引用其他记忆,recall 时解析为关联记忆。

例:content 含 "相关决策见 [[AI Memory 选型演变过程]]",recall 返回时 links 字段
会带上那条被引用记忆的 id/title/category,便于顺藤摸瓜。
"""
from __future__ import annotations

import re

from .store import Store

LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def extract_links(content: str) -> list[str]:
    """从 content 提取所有 [[title]] 的 title。"""
    return LINK_RE.findall(content)


def resolve_links(content: str, store: Store) -> list[dict]:
    """解析 content 的 [[title]],返回匹配记忆的 brief 列表(id/title/category)。

    按精确标题匹配;未匹配的链接静默跳过;去重。
    """
    titles = extract_links(content)
    if not titles:
        return []
    seen: set[str] = set()
    linked: list[dict] = []
    for title in titles:
        mem = store.find_by_title(title)
        if mem and mem.id not in seen:
            seen.add(mem.id)
            linked.append({
                "id": mem.id,
                "title": mem.title,
                "category": mem.category.value,
            })
    return linked
