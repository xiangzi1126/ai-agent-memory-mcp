"""通用 OpenAI 兼容 embedding 封装(硅基流动 / 火山方舟 / OpenAI 均可)。

独立于 Chroma 的 EmbeddingFunction 类型系统:直接用 openai client 调用
OpenAI 兼容的 /embeddings 端点,vector 层预算向量后传给 Chroma,
避免 chromadb 版本间 EmbeddingFunction API 变动带来的兼容问题。
默认硅基流动 BAAI/bge-large-zh-v1.5(1024 维),可在 .aamm/config.yml 切换。
"""
from __future__ import annotations

from openai import OpenAI


class Embedder:
    """调用 OpenAI 兼容 embedding API 的轻量封装。"""

    def __init__(self, api_key: str, model: str, base_url: str, batch_size: int = 64):
        if not api_key:
            raise RuntimeError(
                "缺少 embedding API key。请在项目根 .env 配置对应 key"
                "(默认 VOLCENGINE_API_KEY),或改 .aamm/config.yml 的 api_key_env。"
            )
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._batch_size = batch_size

    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量生成向量。"""
        out: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            chunk = texts[i : i + self._batch_size]
            resp = self._client.embeddings.create(model=self._model, input=chunk)
            # 按 index 排序确保顺序与输入一致
            data = sorted(resp.data, key=lambda d: d.index)
            out.extend(d.embedding for d in data)
        return out

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]

    @property
    def model(self) -> str:
        return self._model
