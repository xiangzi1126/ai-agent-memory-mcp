# AI Memory MCP Server

<!-- mcp-name: io.github.xiangzi1126/ai-agent-memory-mcp -->

> 独立于具体 Agent 的持久化记忆层(MCP Server)——本地优先:记忆跟项目走,存在 `.aamm/`,跨 Claude Code / Qoder / Cursor 共享。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Server-purple.svg)](https://modelcontextprotocol.io/)
[![PyPI](https://img.shields.io/pypi/v/ai-agent-memory-mcp.svg)](https://pypi.org/project/ai-agent-memory-mcp/)

[English](README.md) | [日本語](README.ja.md)

独立于具体 Agent 的持久化记忆层,以 MCP Server 形式提供。任何 MCP 客户端(Claude Code / Qoder / Cursor)都可复用。记忆存于各项目的 `.aamm/` 目录,跟项目走;不同 Agent 连同一项目时共享同一记忆库,用 `source_agent` 戳区分写入者。

## 架构
- **SQLite**:结构化主源(CRUD + FTS5 关键词检索)
- **Chroma 嵌入式**:向量检索(持久化到 `.aamm/chroma/`)
- **Embedding**:任意 OpenAI 兼容服务(火山方舟 / 硅基流动 / OpenAI / 其他),默认火山 `doubao-embedding-vision`
- **Markdown 镜像**:每条记忆同步写 `.aamm/memories/<category>/<id>.md`,人工可读可编辑

三层用 `id` 关联。

## 记忆分类
| category | 用途 |
|---|---|
| `user` | 用户偏好(技术背景/开发习惯/回答偏好) |
| `project` | 项目知识(架构/选型/目录/设计决策) |
| `process` | 工作过程(已解决/Bug/排查/经验) |
| `agent` | Agent 协作(谁做过什么/接手须知) |

## 安装

从 PyPI:
```powershell
pip install ai-agent-memory-mcp
```

从源码:
```powershell
cd ai_agent_memory_mcp
pip install .          # 或:pip install -e .(开发可编辑模式)
```

要求 Python 3.11+。

## 配置 Embedding(任意 OpenAI 兼容服务)

aamm 的 embedding 层是通用 OpenAI 兼容客户端,火山方舟 / 硅基流动 / OpenAI / 任何兼容服务都能用。首次运行会在 `.aamm/config.yml` 生成默认配置,按需修改。

### 配置字段(`.aamm/config.yml` 的 `embedding` 段)
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

> 切换 embedding 模型后,旧向量维度可能不匹配;清空 `.aamm/chroma/` 重新 `remember`,或跑 `python tests/rebuild_vectors.py`。

## 检索机制
`recall` 用三路融合检索,提升命中率:
- **向量检索**(权重 0.6):Chroma cosine;embedding 内容为 `title + tags + content` 拼接,标题/标签信息进入向量
- **关键词检索**(权重 0.25):SQLite FTS5 trigram
- **标题/标签匹配**(权重 0.15):查询词出现在标题(+0.15)或标签(+0.075)时加分

候选扩大到 `top_k*3`,三路融合后取 `top_k`。query 含 FTS5 特殊字符(`.`、`*`、`"`、`-` 等)时,关键词分支退回 `LIKE` 子串匹配,而非报错。

## 工作日记

除可检索的记忆外,aamm 还维护一份人读的工作日记。Agent 完成一次用户请求后,调 `journal_entry()` 记录:问了什么 / 做了什么 / 留的待定项。日记是给人翻看时间线的,`recall` **不**检索它。仅在需要还原「某次交互具体做了什么」时,才用 `search_journal()` 兜底查。

日记写到 `.aamm/logs/`:
- `journal.db` —— 单库 SQLite(检索源,跨所有日期)
- `YYYY-MM-DD.md` —— 按日一个 Markdown 文件,追加式时间线

```
.aamm/logs/
├── journal.db        # 检索源(跨日)
├── 2026-07-14.md     # 按日时间线
└── 2026-07-15.md
```

## MCP 工具

记忆(8):
- `remember(title, content, category, tags?, scope?)` - 存记忆(三处同步,自动 embed)
- `recall(query, category?, top_k=5)` - 混合检索(向量 + 关键词 + 标题匹配)
- `get_memory(id)` - 取单条
- `search_memories(category?, tag?, agent?)` - 结构化过滤
- `update_memory(id, ...)` - 更新(重算 embed + 刷新 md)
- `forget(id)` - 删除(三处同步)
- `list_memories(category?)` - 列出
- `who_am_i()` - 当前 agent + 项目上下文

日记(3):
- `journal_entry(question, answer_summary, key_points?, open_question?, session_id?)` - 记一条时间线
- `search_journal(query, date_from?, date_to?, agent?, limit=10)` - 兜底搜日记
- `setup_profile(user_name)` - 设置用户名(日记里显示)

## 管理 CLI
```powershell
python -m ai_agent_memory_mcp.cli init                  # 初始化当前项目 .aamm
python -m ai_agent_memory_mcp.cli status                # 记忆库状态(分类/向量/Markdown/日记)
python -m ai_agent_memory_mcp.cli export [--dir DIR]    # 导出所有记忆为 Markdown
python -m ai_agent_memory_mcp.cli sync                  # 从 Markdown 重建 SQLite + Chroma
python -m ai_agent_memory_mcp.cli check                 # 一致性检查(db / md / chroma)
python -m ai_agent_memory_mcp.cli journal [--limit N]   # 查看最近工作日记
```

## 接入 Claude Code(user scope;代码共用、项目各自数据)

从 PyPI(无需 `PYTHONPATH`):
```powershell
claude mcp add aamm -s user -- python -m ai_agent_memory_mcp --agent claude-code --project-from-cwd
```

从源码 clone,加 `-e PYTHONPATH=<clone 目录>\ai_agent_memory_mcp`:
```powershell
claude mcp add aamm -s user -e PYTHONPATH=<clone 目录>\ai_agent_memory_mcp -- python -m ai_agent_memory_mcp --agent claude-code --project-from-cwd
```

Qoder / Cursor 同理,改 `--agent` 即可。

## 数据目录结构
```
.aamm/
├── memory.db                    # SQLite:结构化记忆 + FTS5
├── chroma/                      # Chroma 向量库
├── memories/<category>/<id>.md  # Markdown 镜像(可编辑)
├── logs/
│   ├── journal.db               # 工作日记(检索源)
│   └── YYYY-MM-DD.md            # 按日时间线
├── config.yml                   # embedding 配置
└── profile.json                 # 用户名
```

## 许可证
MIT
