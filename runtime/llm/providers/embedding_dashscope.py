"""阿里云 MaaS / DashScope Embedding 实现（原生协议）。

用户配置的是阿里云 MaaS 私有部署端点（非 OpenAI 兼容），
走 DashScope 原生协议：
- POST {base}/services/embeddings/text-embedding/text-embedding
- Body: {"model": "...", "input": {"texts": [...]}, "parameters": {"text_type": "query"}}
- Response: {"output": {"embeddings": [{"text_index": 0, "embedding": [...]}]}}

注：text_type 取值 query / document，写入知识库时用 document，查询时用 query。
"""

from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from common.config.config import settings
from common.logger.logger import get_logger
from runtime.llm.llm_provider import EmbeddingProvider

log = get_logger(__name__)


class DashScopeEmbedding(EmbeddingProvider):
    def __init__(
        self,
        *,
        api_base: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_base = (api_base or settings.dashscope_api_base).rstrip("/")
        self.api_key = api_key or settings.dashscope_api_key
        self.model = model or settings.dashscope_embedding_model
        if not self.api_key:
            log.warning("embedding.no_api_key", hint="set DASHSCOPE_API_KEY in .env")
        self._endpoint = f"{self.api_base}/services/embeddings/text-embedding/text-embedding"
        self._client = httpx.AsyncClient(
            base_url=self.api_base,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def embed(
        self, texts: list[str], *, text_type: str = "document"
    ) -> list[list[float]]:
        """向量化。

        text_type:
          - "document" 写入知识库时使用
          - "query" 查询时使用
        阿里云 MaaS 单次最多 25 条，分批处理。
        """
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        batch_size = 25
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            resp = await self._client.post(
                "/services/embeddings/text-embedding/text-embedding",
                json={
                    "model": self.model,
                    "input": {"texts": batch},
                    "parameters": {"text_type": text_type},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data["output"]["embeddings"]
            # 按 text_index 排序确保顺序与输入一致
            embeddings.sort(key=lambda x: x["text_index"])
            all_embeddings.extend([item["embedding"] for item in embeddings])
        return all_embeddings

    async def close(self) -> None:
        await self._client.aclose()


_embedding: DashScopeEmbedding | None = None


def get_embedding() -> DashScopeEmbedding:
    global _embedding
    if _embedding is None:
        _embedding = DashScopeEmbedding()
    return _embedding
