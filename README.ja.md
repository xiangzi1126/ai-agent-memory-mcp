# AI Memory MCP Server

<!-- mcp-name: io.github.xiangzi1126/ai-agent-memory-mcp -->

> エージェント非依存の永続メモリレイヤー(MCP サーバー)— ローカルファースト:メモリは `.aamm/` に保存され、プロジェクトと共に移動。Claude Code / Qoder / Cursor 間で共有。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Server-purple.svg)](https://modelcontextprotocol.io/)
[![PyPI](https://img.shields.io/pypi/v/ai-agent-memory-mcp.svg)](https://pypi.org/project/ai-agent-memory-mcp/)

[中文](README.zh.md) | [English](README.md)

特定のエージェントに依存しない永続メモリレイヤー(MCP サーバー)。Claude Code / Qoder / Cursor など任意の MCP クライアントで再利用可能。メモリは各プロジェクトの `.aamm/` に保存されプロジェクトと共に移動;同じプロジェクトを開くエージェント間でメモリを共有し、`source_agent` スタンプで書き手を区別。

## アーキテクチャ
- **SQLite**: 構造化主ソース(CRUD + FTS5 キーワード検索)
- **Chroma(組み込み)**: ベクトル検索(`.aamm/chroma/` に永続化)
- **Embedding**: 任意の OpenAI 互換サービス(火山方舟 / SiliconFlow / OpenAI / その他)。デフォルトは火山方舟 `doubao-embedding-vision`
- **Markdown ミラー**: 各メモリは `.aamm/memories/<category>/<id>.md` にも書き出され、人が読める・編集できる

3 層は `id` で紐付く。

## メモリ分類
| category | 用途 |
|---|---|
| `user` | ユーザー設定(技術背景/開発習慣/回答の好み) |
| `project` | プロジェクト知識(アーキテクチャ/技術選定/構成/設計判断) |
| `process` | 作業過程(解決済み/Bug/調査/経験) |
| `agent` | エージェント連携(何をしたか/引き継ぎ事項) |

## インストール

PyPI から:
```powershell
pip install ai-agent-memory-mcp
```

ソースから:
```powershell
cd ai_agent_memory_mcp
pip install .          # または: pip install -e .   (開発用 editable)
```

Python 3.11+ が必要。

## Embedding 設定(任意の OpenAI 互換サービス)

embedding 層は汎用 OpenAI 互換クライアントで、火山方舟 / SiliconFlow / OpenAI / 任意の互換サービスに対応。初回実行時に `.aamm/config.yml` にデフォルト設定が生成されるので、必要に応じて編集。

### 設定フィールド(`.aamm/config.yml` の `embedding` セクション)
| フィールド | 説明 |
|---|---|
| `provider` | 識別子(記録用、動作に影響しない) |
| `model` | embedding モデル名 |
| `base_url` | OpenAI 互換エンドポイント |
| `api_key_env` | キーを読む環境変数名 |
| `dim` | ベクトル次元(モデルと一致必要) |

プロジェクトルートの `.env` にキーを設定し、`config.yml` の `embedding` セクションを編集。

### 例

**火山方舟 doubao-embedding-vision**(デフォルト;Agent/Coding Plan のキーは Plan エンドポイント `/api/plan/v3` を使う必要あり。標準 `/api/v3` は 401)
```yaml
embedding:
  provider: volcengine
  model: doubao-embedding-vision
  base_url: https://ark.cn-beijing.volces.com/api/plan/v3
  api_key_env: VOLCENGINE_API_KEY
  dim: 2048
```
`.env`: `VOLCENGINE_API_KEY=...`

**SiliconFlow bge-large-zh**(中国語テキスト特化)
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

**その他の OpenAI 互換サービス**: `base_url` / `model` / `api_key_env` / `dim` を設定するだけ。

> embedding モデル切替後、旧ベクトルと次元が合わない場合あり。`.aamm/chroma/` を空にして再 `remember`、または `python tests/rebuild_vectors.py` を実行。

## 検索メカニズム
`recall` は三方式融合検索で命中率を向上:
- **ベクトル検索**(重み 0.6): Chroma cosine;embedding は `title + tags + content` を結合し、タイトル/タグ情報をベクトルに含む
- **キーワード検索**(重み 0.25): SQLite FTS5 trigram
- **タイトル/タグ一致**(重み 0.15): クエリがタイトルにあれば +0.15、タグにあれば +0.075

候補を `top_k*3` に拡大し、融合後に `top_k` を取得。クエリが FTS5 特殊文字(`.`、`*`、`"`、`-` など)を含む場合、キーワード分岐は `LIKE` 部分一致にフォールバックし、エラーにならない。

## ワークジャーナル

検索可能なメモリとは別に、aamm は人が読むワークジャーナルを保持する。ユーザーリクエスト完了後、エージェントは `journal_entry()` を呼び出し、聞かれたこと / 行ったこと / 未解決の質問を記録。ジャーナルは人がタイムラインを読むためのもの;`recall` はこれを検索**しない**。過去のやり取りを復元する必要がある場合のみ `search_journal()` をフォールバックで使用。

ジャーナルは `.aamm/logs/` に書き出される:
- `journal.db` — 単一 SQLite ストア(検索ソース、全日付をまたぐ)
- `YYYY-MM-DD.md` — 1 日 1 つの Markdown ファイル、追記型タイムライン

```
.aamm/logs/
├── journal.db        # 検索ソース(全日付)
├── 2026-07-14.md     # 日次タイムライン
└── 2026-07-15.md
```

## MCP ツール

メモリ(8):
- `remember(title, content, category, tags?, scope?)` - 保存(3 層同期、自動 embedding)
- `recall(query, category?, top_k=5)` - 融合検索(ベクトル + キーワード + タイトル一致)
- `get_memory(id)` - 1 件取得
- `search_memories(category?, tag?, agent?)` - 構造化フィルタ
- `update_memory(id, ...)` - 更新(再 embedding + md 更新)
- `forget(id)` - 削除(3 層同期)
- `list_memories(category?)` - 一覧
- `who_am_i()` - 現在のエージェント + プロジェクト情報

ジャーナル(3):
- `journal_entry(question, answer_summary, key_points?, open_question?, session_id?)` - タイムラインエントリを記録
- `search_journal(query, date_from?, date_to?, agent?, limit=10)` - ジャーナルのフォールバック検索
- `setup_profile(user_name)` - ユーザー名を設定(ジャーナルに表示)

## 管理 CLI
```powershell
python -m ai_agent_memory_mcp.cli init                  # 現在のプロジェクトに .aamm を初期化
python -m ai_agent_memory_mcp.cli status                # ストア概要(分類/ベクトル/md/ジャーナル)
python -m ai_agent_memory_mcp.cli export [--dir DIR]    # 全メモリを Markdown にエクスポート
python -m ai_agent_memory_mcp.cli sync                  # Markdown から SQLite + Chroma を再構築
python -m ai_agent_memory_mcp.cli check                 # 整合性チェック(db / md / chroma)
python -m ai_agent_memory_mcp.cli journal [--limit N]   # 最近のジャーナルを表示
```

## Claude Code への接続(user scope;コード共有、プロジェクト別データ)

PyPI から(`PYTHONPATH` 不要):
```powershell
claude mcp add aamm -s user -- python -m ai_agent_memory_mcp --agent claude-code --project-from-cwd
```

ソース clone の場合、`-e PYTHONPATH=<clone ディレクトリ>\ai_agent_memory_mcp` を追加:
```powershell
claude mcp add aamm -s user -e PYTHONPATH=<clone ディレクトリ>\ai_agent_memory_mcp -- python -m ai_agent_memory_mcp --agent claude-code --project-from-cwd
```

Qoder / Cursor も同様、`--agent` を変更するだけ。

## データレイアウト
```
.aamm/
├── memory.db                    # SQLite: 構造化メモリ + FTS5
├── chroma/                      # Chroma ベクトルストア
├── memories/<category>/<id>.md  # Markdown ミラー(編集可能)
├── logs/
│   ├── journal.db               # ワークジャーナル(検索ソース)
│   └── YYYY-MM-DD.md            # 日次ジャーナルタイムライン
├── config.yml                   # embedding 設定
└── profile.json                 # ユーザー名
```

## ライセンス
MIT
