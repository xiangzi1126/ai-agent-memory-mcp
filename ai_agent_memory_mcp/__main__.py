"""启动入口:python -m ai_agent_memory_mcp [--agent NAME] [--project PATH | --project-from-cwd]"""
from __future__ import annotations

import argparse
from pathlib import Path

from .config import find_project_root
from .server import init_service, mcp


def main() -> None:
    parser = argparse.ArgumentParser(prog="ai_agent_memory_mcp", description="AI Memory MCP Server")
    parser.add_argument(
        "--agent", default=None,
        help="当前 Agent 标识(claude-code / qoder / cursor),默认 unknown",
    )
    parser.add_argument(
        "--project", default=None,
        help="显式指定项目根目录",
    )
    parser.add_argument(
        "--project-from-cwd", action="store_true",
        help="以当前工作目录作为项目根",
    )
    args = parser.parse_args()

    if args.project:
        project_root = Path(args.project).resolve()
    elif args.project_from_cwd:
        project_root = Path.cwd().resolve()
    else:
        project_root = find_project_root()

    agent = args.agent or "unknown"
    init_service(project_root, agent)
    mcp.run()  # 默认 stdio transport


if __name__ == "__main__":
    main()
