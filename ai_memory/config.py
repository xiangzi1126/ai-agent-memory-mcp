"""配置:定位项目 .ai-memory 目录、加载 config.yml、读 embedding API key。"""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

CONFIG_FILENAME = "config.yml"
DB_FILENAME = "memory.db"
CHROMA_DIRNAME = "chroma"
MEMORIES_DIRNAME = "memories"
LOG_DIRNAME = "logs"

# 默认 embedding:火山方舟 doubao-embedding-vision(2048 维,多模态,纯文本亦可)。
# Agent/Coding Plan 的 key 须走 Plan 端点 /api/plan/v3(标准 /api/v3 会 401)。
# 若想切硅基流动 bge-large-zh(文本专精)或 OpenAI,改 .ai-memory/config.yml。
DEFAULT_EMBEDDING_MODEL = "doubao-embedding-vision"
DEFAULT_EMBEDDING_DIM = 2048
DEFAULT_EMBEDDING_BASE_URL = "https://ark.cn-beijing.volces.com/api/plan/v3"
DEFAULT_API_KEY_ENV = "VOLCENGINE_API_KEY"

CATEGORIES = ("user", "project", "process", "agent")


class MemoryConfig:
    """单个项目的记忆配置与路径。"""

    def __init__(self, project_root: Path, agent: str = "unknown"):
        self.project_root = Path(project_root).resolve()
        self.agent = agent
        self.data_dir = self.project_root / ".ai-memory"
        self.db_path = self.data_dir / DB_FILENAME
        self.chroma_dir = self.data_dir / CHROMA_DIRNAME
        self.memories_dir = self.data_dir / MEMORIES_DIRNAME
        self.log_dir = self.data_dir / LOG_DIRNAME
        self.config_path = self.data_dir / CONFIG_FILENAME

        self._ensure_dirs()
        load_dotenv(self.project_root / ".env")
        self.settings = self._load_config()

    def _ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        for cat in CATEGORIES:
            (self.memories_dir / cat).mkdir(parents=True, exist_ok=True)

    def _default_settings(self) -> dict:
        return {
            "embedding": {
                "provider": "volcengine",
                "model": DEFAULT_EMBEDDING_MODEL,
                "dim": DEFAULT_EMBEDDING_DIM,
                "base_url": DEFAULT_EMBEDDING_BASE_URL,
                "api_key_env": DEFAULT_API_KEY_ENV,
            }
        }

    def _load_config(self) -> dict:
        default = self._default_settings()
        if self.config_path.exists():
            user = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
            if isinstance(user.get("embedding"), dict):
                default["embedding"].update(user["embedding"])
        else:
            self._write_default(default)
        return default

    def _write_default(self, cfg: dict) -> None:
        try:
            self.config_path.write_text(
                yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
        except Exception:
            pass  # 配置写失败不阻塞运行

    @property
    def embedding(self) -> dict:
        return self.settings["embedding"]

    @property
    def embedding_api_key(self) -> str:
        env_name = self.embedding.get("api_key_env", DEFAULT_API_KEY_ENV)
        return os.getenv(env_name, "")

    @property
    def embedding_model(self) -> str:
        return self.embedding.get("model", DEFAULT_EMBEDDING_MODEL)

    @property
    def embedding_dim(self) -> int:
        return int(self.embedding.get("dim", DEFAULT_EMBEDDING_DIM))

    @property
    def embedding_base_url(self) -> str:
        return self.embedding.get("base_url", DEFAULT_EMBEDDING_BASE_URL)


def find_project_root(start: Path | None = None) -> Path:
    """向上查找含 .ai-memory 或 .git 的目录;找不到则用 cwd。"""
    p = (start or Path.cwd()).resolve()
    for parent in [p, *p.parents]:
        if (parent / ".ai-memory").exists() or (parent / ".git").exists():
            return parent
    return Path.cwd()
