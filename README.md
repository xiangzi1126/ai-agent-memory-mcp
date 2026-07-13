# AI Memory MCP Server

独立于具体 Agent 的持久化记忆层,以 MCP Server 形式提供。可被 Claude Code / Qoder / Cursor 等任何 MCP 客户端复用。

## 架构
- **SQLite**:结构化主源(CRUD + FTS5 关键词检索)
- **Chroma 嵌入式**:向量检索(持久化到 `.ai-memory/chroma/`)
- **火山 doubao-embedding**:OpenAI 兼容 `/api/v3/embeddings`,复用 `VOLCENGINE_API_KEY`
- **Markdown 镜像**:每条记忆同步写 `.ai-memory/memories/<category>/<id>.md`,人工可读可编辑

三层用 `id` 关联。记忆存于**各项目的 `.ai-memory/` 目录**,跟项目走;不同 Agent 连同一项目时共享同一记忆库,`source_agent` 戳区分写入者。

## 记忆分类
| category | 用途 |
|---|---|
| `user` | 用户偏好(技术背景/开发习惯/回答偏好) |
| `project` | 项目知识(架构/选型/目录/设计决策) |
| `process` | 工作过程(已解决/Bug/排查/经验) |
| `agent` | Agent 协作(谁做过什么/接手须知) |

## 安装
```powershell
cd D:\agent\study\ai_memory_mcp
python -m pip install -r requirements.txt
```

## 配置
项目根 `.env` 中配置火山方舟 key(同 llmwiki_knowledge_base):
```
VOLCENGINE_API_KEY=<你的方舟 API Key>
```
默认 embedding:火山方舟 `doubao-embedding-vision`(2048 维,Agent Plan 可用,纯文本亦可)。**关键:须走 Plan 端点 `/api/plan/v3`**(标准 `/api/v3` 会 401,因 Agent Plan key 只授权 Plan 端点)。若想切硅基流动 `bge-large-zh`(文本专精,1024 维)或 OpenAI,改 `.ai-memory/config.yml` 的 model/base_url/api_key_env/dim。

## 接入 Claude Code(user scope,所有项目共用代码、各自项目数据)
```powershell
claude mcp add ai-memory -s user -e PYTHONPATH=D:\agent\study\ai_memory_mcp -- python -m ai_memory --agent claude-code --project-from-cwd
```
Qoder / Cursor 同理,改 `--agent` 即可。

## MCP 工具
- `remember(title, content, category, tags?, scope?)` - 存记忆(三处同步,自动 embed)
- `recall(query, category?, top_k=5)` - 混合检索(向量 + 关键词加权)
- `get_memory(id)` - 取单条
- `search_memories(category?, tag?, agent?)` - 结构化过滤
- `update_memory(id, ...)` - 更新(重算 embed + 刷新 md)
- `forget(id)` - 删除(三处同步)
- `list_memories(category?)` - 列出
- `who_am_i()` - 当前 agent + 项目上下文

## 管理 CLI(后续阶段)
```powershell
python -m ai_memory.cli init|export|sync|check
```
