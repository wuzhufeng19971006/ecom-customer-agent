"""RAG 流水线：召回 → Jina 精排 → 注入 LLM 上下文。"""

from __future__ import annotations

from dataclasses import dataclass

from common.logger.logger import get_logger
from runtime.llm.providers.rerank_jina import get_reranker
from knowledge_platform.knowledge_service.retriever.retriever import ChromaStore, RetrievalHit, get_store

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
        final = [
            candidates[r.index] for r in ranked if 0 <= r.index < len(candidates)
        ]

        # embedding 强命中兜底：召回阶段的第一名若被 reranker 挤出，强制补到最前。
        # 实测 jina-reranker-v2-base-multilingual 对中文口语化问法（如
        # "小孩2岁舞台演出能用吗" vs "彩妆会伤害皮肤吗"）语义理解弱，
        # 会把 embedding 正确召回的强相关文档排到末尾导致漏检。
        top_embed_idx = max(
            range(len(candidates)), key=lambda i: candidates[i].score
        )
        if top_embed_idx not in {r.index for r in ranked}:
            log.warning(
                "rag.rerank_dropped_top_embedding",
                query=query[:60],
                doc=candidates[top_embed_idx].text[:50],
            )
            final.insert(0, candidates[top_embed_idx])

        blocks = [
            f"[{h.collection}] {h.text}\n(metadata: {h.metadata})"
            for h in final
        ]
        return RAGContext(
            hits=final,
            prompt_block="\n---\n".join(blocks) if blocks else "",
        )
