# AI Memory MCP Server

<!-- mcp-name: io.github.xiangzi1126/ai-agent-memory-mcp -->

> Agent-agnostic persistent memory as an MCP Server — local-first: memories travel with your project in `.aamm/`, shared across Claude Code / Qoder / Cursor.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Server-purple.svg)](https://modelcontextprotocol.io/)
[![PyPI](https://img.shields.io/pypi/v/ai-agent-memory-mcp.svg)](https://pypi.org/project/ai-agent-memory-mcp/)

[中文](README.zh.md) | [日本語](README.ja.md)

An agent-agnostic persistent memory layer exposed as an MCP Server. Any MCP client — Claude Code, Qoder, Cursor — can reuse it. Memories live in each project's `.aamm/` directory and travel with the project; different agents working the same project share one memory store, with a `source_agent` stamp distinguishing writers.

## Architecture
- **SQLite** — structured source of truth (CRUD + FTS5 keyword search)
- **Chroma (embedded)** — vector retrieval, persisted to `.aamm/chroma/`
- **Embedding** — any OpenAI-compatible service (Volcengine / SiliconFlow / OpenAI / others); defaults to Volcengine `doubao-embedding-vision`
- **Markdown mirror** — each memory is also written to `.aamm/memories/<category>/<id>.md`, human-readable and editable

The three layers are joined by `id`.

## Memory categories
| category | use |
|---|---|
| `user` | user preferences (tech background / dev habits / answer style) |
| `project` | project knowledge (architecture / stack / layout / design decisions) |
| `process` | work process (solved issues / bugs / debugging / lessons) |
| `agent` | agent collaboration (what was done / handoff notes) |

## Install

From PyPI:
```powershell
pip install ai-agent-memory-mcp
```

From source:
```powershell
cd ai_agent_memory_mcp
pip install .          # or: pip install -e .   (editable, for development)
```

Requires Python 3.11+.

## Configure embedding (any OpenAI-compatible service)

The embedding layer is a generic OpenAI-compatible client — Volcengine / SiliconFlow / OpenAI / any compatible service works. On first run a default config is generated at `.aamm/config.yml`; edit as needed.

### Fields (`embedding` section of `.aamm/config.yml`)
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

> After switching embedding model, old vectors may mismatch in dimension; clear `.aamm/chroma/` and re-`remember`, or run `python tests/rebuild_vectors.py`.

## Retrieval
`recall` uses three-way fused retrieval to maximize hit rate:
- **Vector** (weight 0.6): Chroma cosine; embeddings are computed from `title + tags + content`, so title/tag signal enters the vector
- **Keyword** (weight 0.25): SQLite FTS5 trigram
- **Title/tag match** (weight 0.15): +0.15 if the query appears in the title, +0.075 if in a tag

Candidates are expanded to `top_k*3`, then fused down to `top_k`. If the query contains FTS5 special characters (`.`, `*`, `"`, `-`, ...), the keyword branch falls back to `LIKE` substring matching instead of erroring.

## Work journal

Besides searchable memories, aamm keeps a human-readable work journal. After completing a user request, the agent calls `journal_entry()` to log what was asked / what it did / any open question. Journals are for people reading a timeline; `recall` does **not** search them. Use `search_journal()` only as a fallback to recover "what happened in a past interaction".

Journals are written to `.aamm/logs/`:
- `journal.db` — single SQLite store (the search source, spans all dates)
- `YYYY-MM-DD.md` — one Markdown file per day, append-only timeline

```
.aamm/logs/
├── journal.db        # search source (all dates)
├── 2026-07-14.md     # per-day timeline
└── 2026-07-15.md
```

## MCP tools

Memory (8):
- `remember(title, content, category, tags?, scope?)` — store (three-way sync, auto-embed)
- `recall(query, category?, top_k=5)` — fused retrieval (vector + keyword + title match)
- `get_memory(id)` — get one
- `search_memories(category?, tag?, agent?)` — structured filter
- `update_memory(id, ...)` — update (re-embed + refresh md)
- `forget(id)` — delete (three-way sync)
- `list_memories(category?)` — list
- `who_am_i()` — current agent + project context

Journal (3):
- `journal_entry(question, answer_summary, key_points?, open_question?, session_id?)` — log a timeline entry
- `search_journal(query, date_from?, date_to?, agent?, limit=10)` — fallback search over journals
- `setup_profile(user_name)` — set the user name (shown in journals)

## Management CLI
```powershell
python -m ai_agent_memory_mcp.cli init                  # initialize .aamm in the current project
python -m ai_agent_memory_mcp.cli status                # store overview (categories / vectors / md / journal)
python -m ai_agent_memory_mcp.cli export [--dir DIR]    # export all memories to Markdown
python -m ai_agent_memory_mcp.cli sync                  # rebuild SQLite + Chroma from Markdown
python -m ai_agent_memory_mcp.cli check                 # consistency check (db / md / chroma)
python -m ai_agent_memory_mcp.cli journal [--limit N]   # show recent journal entries
```

## Wire into Claude Code (user scope; shared code, per-project data)

From PyPI (no `PYTHONPATH` needed):
```powershell
claude mcp add aamm -s user -- python -m ai_agent_memory_mcp --agent claude-code --project-from-cwd
```

From a source clone, add `-e PYTHONPATH=<clone dir>\ai_agent_memory_mcp`:
```powershell
claude mcp add aamm -s user -e PYTHONPATH=<clone dir>\ai_agent_memory_mcp -- python -m ai_agent_memory_mcp --agent claude-code --project-from-cwd
```

Qoder / Cursor are the same — just change `--agent`.

## Data layout
```
.aamm/
├── memory.db                    # SQLite: structured memories + FTS5
├── chroma/                      # Chroma vector store
├── memories/<category>/<id>.md  # Markdown mirror (editable)
├── logs/
│   ├── journal.db               # work journal (search source)
│   └── YYYY-MM-DD.md            # per-day journal timeline
├── config.yml                   # embedding config
└── profile.json                 # user name
```

## License
MIT
