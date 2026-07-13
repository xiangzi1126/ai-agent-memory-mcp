"""管理 CLI:初始化 / 状态 / 导出 / 同步 / 一致性检查。

用法:
  python -m ai_memory.cli init      初始化当前项目 .ai-memory
  python -m ai_memory.cli status    记忆库状态(各分类/向量/Markdown 数量)
  python -m ai_memory.cli export [--dir DIR]   导出所有记忆为 Markdown
  python -m ai_memory.cli sync      从 Markdown 重建 SQLite + Chroma
  python -m ai_memory.cli check     一致性检查(db / md / chroma)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import MemoryConfig, find_project_root
from .markdown import scan_markdown, write_markdown
from .store import Store


def _cfg() -> MemoryConfig:
    return MemoryConfig(find_project_root(), agent="cli")


def cmd_init(args) -> None:
    cfg = _cfg()
    print(f"initialized: {cfg.data_dir}")


def cmd_status(args) -> None:
    cfg = _cfg()
    store = Store(cfg.db_path)
    print(f"data dir : {cfg.data_dir}")
    print(f"project  : {cfg.project_root}")
    print(f"agent    : {cfg.agent}")
    print(f"embedding: {cfg.embedding_model} (dim {cfg.embedding_dim})")
    print("memories by category:")
    for cat in ("user", "project", "process", "agent"):
        print(f"  {cat:8}: {len(store.list(category=cat))}")
    # Chroma 向量数(直接读 collection,不需 API key)
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(cfg.chroma_dir))
        col = client.get_or_create_collection("memories")
        print(f"vectors  : {col.count()}")
    except Exception as e:
        print(f"vectors  : (unavailable: {e})")
    print(f"markdown : {len(scan_markdown(cfg.memories_dir))}")


def cmd_export(args) -> None:
    cfg = _cfg()
    store = Store(cfg.db_path)
    out = Path(args.dir) if args.dir else cfg.memories_dir
    mems = store.list()
    print(f"exporting {len(mems)} memories to {out}")
    for m in mems:
        write_markdown(out, m)
    print("done")


def cmd_sync(args) -> None:
    """从 Markdown 重建 SQLite + Chroma(md 为源,人工编辑 md 后回灌)。"""
    cfg = _cfg()
    store = Store(cfg.db_path)
    mems = scan_markdown(cfg.memories_dir)
    print(f"syncing {len(mems)} memories from markdown -> sqlite")
    for m in mems:
        store.upsert(m)
    # 向量重建(需 API key)
    try:
        from .embedding import Embedder
        from .vector import VectorStore
        emb = Embedder(cfg.embedding_api_key, cfg.embedding_model, cfg.embedding_base_url)
        vs = VectorStore(cfg.chroma_dir, emb)
        for m in mems:
            vs.upsert(m)
        print(f"vectors rebuilt: {len(mems)}")
    except Exception as e:
        print(f"vectors rebuild skipped: {e}")
    print("done")


def cmd_check(args) -> None:
    """一致性检查:db / markdown / chroma 的 id 集合差异。"""
    cfg = _cfg()
    store = Store(cfg.db_path)
    db_ids = set(store.all_ids())
    md_ids = {m.id for m in scan_markdown(cfg.memories_dir)}
    chroma_ids: set[str] = set()
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(cfg.chroma_dir))
        col = client.get_or_create_collection("memories")
        chroma_ids = set(col.get(include=[]).get("ids", []))
    except Exception:
        pass
    print(f"db:{len(db_ids)}  md:{len(md_ids)}  chroma:{len(chroma_ids)}")
    only_db = db_ids - md_ids - chroma_ids
    only_md = md_ids - db_ids
    only_chroma = chroma_ids - db_ids
    if only_db:
        print(f"  only in db    : {only_db}")
    if only_md:
        print(f"  only in md    : {only_md}")
    if only_chroma:
        print(f"  only in chroma: {only_chroma}")
    if not (only_db or only_md or only_chroma):
        print("  all consistent ✓")


def main() -> None:
    parser = argparse.ArgumentParser(prog="ai_memory.cli", description="AI Memory 管理 CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="初始化当前项目 .ai-memory")
    sub.add_parser("status", help="记忆库状态")
    p_export = sub.add_parser("export", help="导出所有记忆为 Markdown")
    p_export.add_argument("--dir", default=None, help="导出目录(默认 memories/ 镜像目录)")
    sub.add_parser("sync", help="从 Markdown 重建 SQLite + Chroma")
    sub.add_parser("check", help="一致性检查 db/md/chroma")
    args = parser.parse_args()
    {
        "init": cmd_init,
        "status": cmd_status,
        "export": cmd_export,
        "sync": cmd_sync,
        "check": cmd_check,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
