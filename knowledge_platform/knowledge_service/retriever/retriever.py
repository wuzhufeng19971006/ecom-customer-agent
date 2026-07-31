"""ChromaDB 向量库封装。

三个集合：
- kb_faq      店铺常见问题
- kb_product  商品知识（标题/卖点/SKU 属性）
- kb_policy   售后与平台规则
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from common.config.config import settings
from common.logger.logger import get_logger
from runtime.llm.providers.embedding_dashscope import get_embedding

log = get_logger(__name__)

COLLECTIONS = ("kb_faq", "kb_product", "kb_policy")


@dataclass
class RetrievalHit:
    collection: str
    id: str
    text: str
    score: float
    metadata: dict[str, Any]


class ChromaStore:
    """对 ChromaDB 的轻封装：写 / 查 / 删除。"""

    def __init__(self, persist_dir: str | None = None) -> None:
        self.path = persist_dir or str(settings.chroma_path)
        self._client = chromadb.PersistentClient(
            path=self.path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._embedding_fn = get_embedding()
        self._collections = {
            name: self._client.get_or_create_collection(
                name=name, metadata={"hnsw:space": "cosine"}
            )
            for name in COLLECTIONS
        }

    async def add(
        self,
        collection: str,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        if collection not in self._collections:
            raise ValueError(f"unknown collection: {collection}")
        embeddings = await self._embedding_fn.embed(documents, text_type="document")
        # ChromaDB >=1.5 拒绝空 dict metadata（"Expected metadata to be a non-empty dict"），
        # 空 dict 统一转 None（Chroma 合法值，表示无元数据）
        if metadatas is not None:
            metadatas = [m if m else None for m in metadatas]
        self._collections[collection].add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    async def query(
        self,
        collection: str,
        query_text: str,
        *,
        top_k: int = 20,
        where: dict[str, Any] | None = None,
    ) -> list[RetrievalHit]:
        if collection not in self._collections:
            raise ValueError(f"unknown collection: {collection}")
        query_emb = await self._embedding_fn.embed([query_text], text_type="query")
        result = self._collections[collection].query(
            query_embeddings=query_emb,
            n_results=top_k,
            where=where,
        )
        hits: list[RetrievalHit] = []
        for i, doc_id in enumerate(result["ids"][0]):
            hits.append(
                RetrievalHit(
                    collection=collection,
                    id=doc_id,
                    text=result["documents"][0][i],
                    score=1.0 - result["distances"][0][i],  # Chroma 返回距离
                    metadata=result["metadatas"][0][i] or {},
                )
            )
        return hits

    def count(self, collection: str) -> int:
        return self._collections[collection].count()


_store: ChromaStore | None = None


def get_store() -> ChromaStore:
    global _store
    if _store is None:
        _store = ChromaStore()
    return _store
