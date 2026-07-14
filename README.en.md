# AI Memory MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Server-purple.svg)](https://modelcontextprotocol.io/)

[中文](README.md) | [日本語](README.ja.md)

Agent-agnostic persistent memory exposed as an MCP Server. Local-first - memories travel with your project in `.ai-memory/` and are shared across any MCP client (Claude Code / Qoder / Cursor).

## Architecture
- **SQLite**: structured source of truth (CRUD + FTS5 keyword search)
- **Chroma (embedded)**: vector retrieval (persisted to `.ai-memory/chroma/`)
- **Embedding**: any OpenAI-compatible service (Volcengine / SiliconFlow / OpenAI / others); defaults to Volcengine `doubao-embedding-vision` — see Config below
- **Markdown mirror**: each memory is also written to `.ai-memory/memories/<category>/<id>.md`, human-readable and editable

The three layers are joined by `id`. Memories live in **each project's `.ai-memory/` directory** and travel with the project; different agents on the same project share one memory store, with a `source_agent` stamp distinguishing writers.

## Memory categories
| category | use |
|---|---|
| `user` | user preferences (tech background / dev habits / answer style) |
| `project` | project knowledge (architecture / stack / layout / design decisions) |
| `process` | work process (solved issues / bugs / debugging / lessons) |
| `agent` | agent collaboration (what was done / handoff notes) |

## Install
```powershell
cd <clone dir>\ai_memory_mcp
python -m pip install -r requirements.txt
```

> Or install directly from PyPI (no clone needed): `pip install ai-agent-memory-mcp`.

## Configure Embedding (any OpenAI-compatible service)

The embedding layer is a generic OpenAI-compatible client — **Volcengine / SiliconFlow / OpenAI / any compatible service works**. On first run a default config is generated at `.ai-memory/config.yml`; edit as needed.

### Fields (`embedding` section of `.ai-memory/config.yml`)
| field | meaning |
|---|---|
| `provider` | label (informational only) |
| `model` | embedding model name |
| `base_url` | OpenAI-compatible endpoint |
| `api_key_env` | which env var holds the key |
| `dim` | vector dim (must match the model) |

Put the key in the project root `.env`, then edit the `embedding` section of `config.yml`.

### Examples

**Volcengine doubao-embedding-vision** (default; Agent/Coding Plan keys must use the Plan endpoint `/api/plan/v3` — standard `/api/v3` returns 401)
```yaml
embedding:
  provider: volcengine
  model: doubao-embedding-vision
  base_url: https://ark.cn-beijing.volces.com/api/plan/v3
  api_key_env: VOLCENGINE_API_KEY
  dim: 2048
```
`.env`: `VOLCENGINE_API_KEY=...`

**SiliconFlow bge-large-zh** (Chinese-text optimized)
```yaml
embedding:
  provider: siliconflow
  model: BAAI/bge-large-zh-v1.5
  base_url: https://api.siliconflow.cn/v1
  api_key_env: SILICONFLOW_API_KEY
  dim: 1024
```
`.env`: `SILICONFLOW_API_KEY=...`

**OpenAI**
```yaml
embedding:
  provider: openai
  model: text-embedding-3-small
  base_url: https://api.openai.com/v1
  api_key_env: OPENAI_API_KEY
  dim: 1536
```
`.env`: `OPENAI_API_KEY=...`

**Any other OpenAI-compatible service**: just fill in `base_url` / `model` / `api_key_env` / `dim`.

> After switching embedding model, old vectors may mismatch in dimension; clear `.ai-memory/chroma/` and re-`remember`, or run `python tests/rebuild_vectors.py`.

## Retrieval
`recall` uses three-way fused retrieval to maximize hit rate:
- **Vector** (weight 0.6): Chroma cosine; embeddings are computed from `title + tags + content`, so title/tag signal enters the vector
- **Keyword** (weight 0.25): SQLite FTS5 trigram
- **Title/tag match** (weight 0.15): +0.15 if the query appears in the title, +0.075 if in a tag

Candidates are expanded to `top_k*3`, then fused down to `top_k`.

## Wire into Claude Code (user scope; shared code, per-project data)
```powershell
claude mcp add ai-memory -s user -e PYTHONPATH=<clone dir>\ai_memory_mcp -- python -m ai_memory --agent claude-code --project-from-cwd
```
Replace `<clone dir>` with your actual clone path. Qoder / Cursor are the same — just change `--agent`.

> If installed from PyPI (`pip install ai-agent-memory-mcp`), drop `PYTHONPATH`: `claude mcp add ai-memory -s user -- python -m ai_memory --agent claude-code --project-from-cwd`

## MCP tools
- `remember(title, content, category, tags?, scope?)` — store (three-way sync, auto-embed)
- `recall(query, category?, top_k=5)` — fused retrieval (vector + keyword + title match)
- `get_memory(id)` — get one
- `search_memories(category?, tag?, agent?)` — structured filter
- `update_memory(id, ...)` — update (re-embed + refresh md)
- `forget(id)` — delete (three-way sync)
- `list_memories(category?)` — list
- `who_am_i()` — current agent + project context

## Management CLI (later phase)
```powershell
python -m ai_memory.cli init|export|sync|check
```
