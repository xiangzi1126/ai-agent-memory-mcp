# AI Memory MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Server-purple.svg)](https://modelcontextprotocol.io/)

[中文](README.md) | [English](README.en.md)

特定のエージェントに依存しない永続メモリレイヤー(MCP サーバー)。Local-first - 記憶はプロジェクトの `.ai-memory/` に保存され、Claude Code / Qoder / Cursor 間で共有されます。

## アーキテクチャ
- **SQLite**: 構造化主ソース(CRUD + FTS5 キーワード検索)
- **Chroma(組み込み)**: ベクトル検索(`.ai-memory/chroma/` に永続化)
- **Embedding**: 任意の OpenAI 互換サービス(火山方舟 / SiliconFlow / OpenAI / その他)。デフォルトは火山方舟 `doubao-embedding-vision`(下記設定参照)
- **Markdown ミラー**: 各メモリは `.ai-memory/memories/<category>/<id>.md` にも書き出され、人が読める・編集できる

3 層は `id` で紐付く。メモリは**各プロジェクトの `.ai-memory/` ディレクトリ**に置かれ、プロジェクトと共に移動。同じプロジェクトを開くエージェント間でメモリを共有し、`source_agent` スタンプで書き手を区別。

## メモリ分類
| category | 用途 |
|---|---|
| `user` | ユーザー設定(技術背景/開発習慣/回答の好み) |
| `project` | プロジェクト知識(アーキテクチャ/技術選定/構成/設計判断) |
| `process` | 作業過程(解決済み/Bug/調査/経験) |
| `agent` | エージェント連携(何をしたか/引き継ぎ事項) |

## インストール
```powershell
cd <clone ディレクトリ>\ai_memory_mcp
python -m pip install -r requirements.txt
```

## Embedding 設定(任意の OpenAI 互換サービス)

embedding 層は汎用 OpenAI 互換クライアントで、**火山方舟 / SiliconFlow / OpenAI / 任意の互換サービス** に対応。初回実行時に `.ai-memory/config.yml` にデフォルト設定が生成されるので、必要に応じて編集。

### 設定フィールド(`.ai-memory/config.yml` の `embedding` セクション)
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

> embedding モデル切替後、旧ベクトルと次元が合わない場合あり。`.ai-memory/chroma/` を空にして再 `remember`、または `python tests/rebuild_vectors.py` を実行。

## 検索メカニズム
`recall` は三方式融合検索で命中率を向上:
- **ベクトル検索**(重み 0.6): Chroma cosine;embedding は `title + tags + content` を結合し、タイトル/タグ情報をベクトルに含む
- **キーワード検索**(重み 0.25): SQLite FTS5 trigram
- **タイトル/タグ一致**(重み 0.15): クエリがタイトルにあれば +0.15、タグにあれば +0.075

候補を `top_k*3` に拡大し、融合後に `top_k` を取得。

## Claude Code への接続(user scope;コード共有、プロジェクト別データ)
```powershell
claude mcp add ai-memory -s user -e PYTHONPATH=<clone ディレクトリ>\ai_memory_mcp -- python -m ai_memory --agent claude-code --project-from-cwd
```
`<clone ディレクトリ>` は実際の clone パスに置き換え。Qoder / Cursor も同様、`--agent` を変更するだけ。

## MCP ツール
- `remember(title, content, category, tags?, scope?)` — 保存(3 層同期、自動 embedding)
- `recall(query, category?, top_k=5)` — 融合検索(ベクトル + キーワード + タイトル一致)
- `get_memory(id)` — 1 件取得
- `search_memories(category?, tag?, agent?)` — 構造化フィルタ
- `update_memory(id, ...)` — 更新(再 embedding + md 更新)
- `forget(id)` — 削除(3 層同期)
- `list_memories(category?)` — 一覧
- `who_am_i()` — 現在のエージェント + プロジェクト情報

## 管理 CLI(後続フェーズ)
```powershell
python -m ai_memory.cli init|export|sync|check
```
