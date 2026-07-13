"""Chroma 向量存储层。

预算向量(Embedder)后传入 Chroma,不使用 Chroma 的 EmbeddingFunction
类型系统,避免版本兼容问题。collection 用 cosine 距离,持久化到 .ai-memory/chroma/。
"""
from __future__ import annotations

from pathlib import Path

import chromadb

from .embedding import Embedder
from .schema import Memory

COLLECTION = "memories"


class VectorStore:
    def __init__(self, chroma_dir: Path, embedder: Embedder):
        self._client = chromadb.PersistentClient(path=str(chroma_dir))
        self._col = self._client.get_or_create_collection(
            COLLECTION, metadata={"hnsw:space": "cosine"}
        )
        self._embedder = embedder

    def upsert(self, mem: Memory) -> None:
        vec = self._embedder.embed_one(mem.embed_text())
        self._col.upsert(
            ids=[mem.id],
            documents=[mem.content],
            embeddings=[vec],
            metadatas=[mem.to_chroma_metadata()],
        )

    def query(
        self, text: str, category: str | None = None, top_k: int = 5
    ) -> list[tuple[str, float]]:
        """返回 (id, distance);cosine distance 越小越相似。"""
        vec = self._embedder.embed_one(text)
        where = {"category": category} if category else None
        res = self._col.query(
            query_embeddings=[vec], n_results=top_k, where=where
        )
        ids = (res.get("ids") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        return list(zip(ids, dists))

    def delete(self, mem_id: str) -> None:
        try:
            self._col.delete(ids=[mem_id])
        except Exception:
            pass  # id 不存在无碍

    def count(self) -> int:
        try:
            return self._col.count()
        except Exception:
            return 0
