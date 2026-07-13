# AI Memory MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Server-purple.svg)](https://modelcontextprotocol.io/)

[English](README.en.md) | [日本語](README.ja.md)

独立于具体 Agent 的持久化记忆层,以 MCP Server 形式提供。可被 Claude Code / Qoder / Cursor 等任何 MCP 客户端复用。

## 架构
- **SQLite**:结构化主源(CRUD + FTS5 关键词检索)
- **Chroma 嵌入式**:向量检索(持久化到 `.ai-memory/chroma/`)
- **Embedding**:任意 OpenAI 兼容服务(火山方舟 / 硅基流动 / OpenAI / 其他),默认火山 `doubao-embedding-vision`;见下文配置
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
cd <clone 目录>\ai_memory_mcp
python -m pip install -r requirements.txt
```

## 配置 Embedding(任意 OpenAI 兼容服务)

ai-memory 的 embedding 层是通用 OpenAI 兼容客户端,**火山方舟 / 硅基流动 / OpenAI / 任何兼容服务都能用**。首次运行会在 `.ai-memory/config.yml` 生成默认配置,按需修改即可。

### 配置字段(`.ai-memory/config.yml` 的 `embedding` 段)
| 字段 | 说明 |
|---|---|
| `provider` | 标识(仅记录用,不影响逻辑) |
| `model` | embedding 模型名 |
| `base_url` | OpenAI 兼容端点 |
| `api_key_env` | 读哪个环境变量拿 key |
| `dim` | 向量维度(须与模型一致) |

在项目根 `.env` 配对应 key,再改 `config.yml` 的 `embedding` 段。

### 示例

**火山方舟 doubao-embedding-vision**(默认;Agent/Coding Plan 须走 Plan 端点 `/api/plan/v3`,标准 `/api/v3` 会 401)
```yaml
embedding:
  provider: volcengine
  model: doubao-embedding-vision
  base_url: https://ark.cn-beijing.volces.com/api/plan/v3
  api_key_env: VOLCENGINE_API_KEY
  dim: 2048
```
`.env`:`VOLCENGINE_API_KEY=...`

**硅基流动 bge-large-zh**(中文文本专精)
```yaml
embedding:
  provider: siliconflow
  model: BAAI/bge-large-zh-v1.5
  base_url: https://api.siliconflow.cn/v1
  api_key_env: SILICONFLOW_API_KEY
  dim: 1024
```
`.env`:`SILICONFLOW_API_KEY=...`

**OpenAI**
```yaml
embedding:
  provider: openai
  model: text-embedding-3-small
  base_url: https://api.openai.com/v1
  api_key_env: OPENAI_API_KEY
  dim: 1536
```
`.env`:`OPENAI_API_KEY=...`

**任何其他 OpenAI 兼容服务**:填对应 `base_url` / `model` / `api_key_env` / `dim` 即可。

> 切换 embedding 模型后,旧向量维度可能不匹配;清空 `.ai-memory/chroma/` 重新 `remember`,或跑 `python tests/rebuild_vectors.py`。

## 检索机制
`recall` 用三路融合检索,提升命中率:
- **向量检索**(权重 0.6):Chroma cosine;embedding 内容为 `title + tags + content` 拼接,标题/标签信息进入向量
- **关键词检索**(权重 0.25):SQLite FTS5 trigram
- **标题/标签匹配**(权重 0.15):查询词出现在标题(+0.15)或标签(+0.075)时加分

候选扩大到 `top_k*3`,三路融合后取 `top_k`。

## 接入 Claude Code(user scope,所有项目共用代码、各自项目数据)
```powershell
claude mcp add ai-memory -s user -e PYTHONPATH=<clone 目录>\ai_memory_mcp -- python -m ai_memory --agent claude-code --project-from-cwd
```
`<clone 目录>` 换成你 clone 的实际路径。Qoder / Cursor 同理,改 `--agent` 即可。

## MCP 工具
- `remember(title, content, category, tags?, scope?)` - 存记忆(三处同步,自动 embed)
- `recall(query, category?, top_k=5)` - 混合检索(向量 + 关键词 + 标题匹配)
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
