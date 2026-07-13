"""AI Memory MCP Server - 跨 Agent 的持久化记忆层。

通过 MCP stdio 协议向 Claude Code / Qoder / Cursor 等客户端提供统一的
记忆存取能力。记忆存于各项目的 .ai-memory/ 目录,与具体 Agent 解耦。
"""
__version__ = "0.1.0"
