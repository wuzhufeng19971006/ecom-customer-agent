"""Jina Reranker v2 实现。

POST {base}/rerank
- Authorization: Bearer {JINA_API_KEY}
- Body: { model, query, documents, top_n }
- 响应 results[i] = { index, relevance_score, document:{ text } }
"""

from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger
from app.llm.base import RerankProvider, RerankResult

log = get_logger(__name__)


class JinaReranker(RerankProvider):
    def __init__(
        self,
        *,
        api_base: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_base = (api_base or settings.jina_api_base).rstrip("/")
        self.api_key = api_key or settings.jina_api_key
        self.model = model or settings.jina_reranker_model
        self._client = httpx.AsyncClient(
            base_url=self.api_base,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        top_n: int = 4,
    ) -> list[RerankResult]:
        if not documents:
            return []
        resp = await self._client.post(
            "/rerank",
            json={
                "model": self.model,
                "query": query,
                "documents": documents,
                "top_n": min(top_n, len(documents)),
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            RerankResult(
                index=item["index"],
                score=item["relevance_score"],
                document=item.get("document", {}).get("text", ""),
            )
            for item in data.get("results", [])
        ]

    async def close(self) -> None:
        await self._client.aclose()


_reranker: JinaReranker | None = None


def get_reranker() -> JinaReranker:
    global _reranker
    if _reranker is None:
        _reranker = JinaReranker()
    return _reranker
