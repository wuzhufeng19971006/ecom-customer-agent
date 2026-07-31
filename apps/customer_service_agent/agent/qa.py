"""答疑服务（HTTP 文本路径入口）。

已重构为 AnswerEngine 的薄包装：
- QAService 保留为 qa.py API 的调用入口，保持接口兼容
- 核心逻辑（脱敏/RAG/LLM/JSON解析/恢复脱敏）委托给 AnswerEngine.answer_qa()
"""

from __future__ import annotations

from dataclasses import dataclass

from common.logger.logger import get_logger
from knowledge_platform.knowledge_service.retriever.retriever import RetrievalHit
from knowledge_platform.knowledge_service.service import RAGPipeline
from runtime.llm.llm_provider import LLMProvider
from runtime.llm.providers.deepseek import get_llm
from apps.customer_service_agent.agent.answer_engine import AnswerResult, get_answer_engine

log = get_logger(__name__)


@dataclass
class QAResponse:
    """HTTP 路径的返回结构，保持与旧接口兼容。"""

    answer: str
    matched: bool
    sources: list[RetrievalHit]


class QAService:
    """答疑服务。

    委托 AnswerEngine 执行核心逻辑，自身仅负责构造和结果转换。
    """

    def __init__(
        self,
        *,
        rag: RAGPipeline | None = None,
        llm: LLMProvider | None = None,
        top_k: int = 10,
        top_n: int = 3,
    ) -> None:
        self.engine = get_answer_engine(
            llm=llm or get_llm(),
            rag=rag or RAGPipeline(),
            top_k=top_k,
            top_n=top_n,
        )

    async def answer(self, question: str) -> QAResponse:
        """回答顾客问题。"""
        result: AnswerResult = await self.engine.answer_qa(question)

        return QAResponse(
            answer=result.answer,
            matched=result.matched,
            sources=result.sources,
        )
