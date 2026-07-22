"""RAG 流水线：召回 → Jina 精排 → 注入 LLM 上下文。"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.llm.rerank_jina import get_reranker
from app.retrieval.chroma_store import ChromaStore, RetrievalHit, get_store

log = get_logger(__name__)


@dataclass
class RAGContext:
    hits: list[RetrievalHit]
    prompt_block: str


class RAGPipeline:
    def __init__(self, store: ChromaStore | None = None) -> None:
        self.store = store or get_store()

    async def retrieve(
        self,
        query: str,
        *,
        collections: list[str] | None = None,
        top_k: int = 20,
        top_n: int = 4,
    ) -> RAGContext:
        cols = collections or ["kb_faq", "kb_product", "kb_policy"]
        candidates: list[RetrievalHit] = []
        for col in cols:
            candidates.extend(await self.store.query(col, query, top_k=top_k))

        if not candidates:
            return RAGContext(hits=[], prompt_block="")

        # Jina 精排
        reranker = get_reranker()
        ranked = await reranker.rerank(
            query=query,
            documents=[h.text for h in candidates],
            top_n=top_n,
        )
        final = [candidates[r.index] for r in ranked]

        blocks = [
            f"[{h.collection}] {h.text}\n(metadata: {h.metadata})"
            for h in final
        ]
        return RAGContext(
            hits=final,
            prompt_block="\n---\n".join(blocks) if blocks else "",
        )
