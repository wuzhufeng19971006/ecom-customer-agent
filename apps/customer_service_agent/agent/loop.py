"""Agent 主循环（Webhook 路径入口）。

已重构为 AnswerEngine 的薄包装：
- AgentLoop 保留为 webhooks.py 的调用入口，保持接口兼容
- 核心逻辑（脱敏/RAG/LLM/工具循环/恢复脱敏）委托给 AnswerEngine.answer_agent()
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.customer_service_agent.adapters.base import PlatformAdapter
from apps.customer_service_agent.agent.answer_engine import AnswerResult, get_answer_engine
from apps.customer_service_agent.agent.session import Session
from common.logger.logger import get_logger
from knowledge_platform.knowledge_service.service import RAGPipeline
from runtime.llm.llm_provider import LLMProvider

log = get_logger(__name__)


@dataclass
class AgentResult:
    """Webhook 路径的返回结构，保持与旧接口兼容。"""

    reply: str
    handoff: bool = False
    tool_calls_made: list[str] = None  # type: ignore[assignment]
    masked_answer: str = ""
    """脱敏版回复（含占位符），供 webhook 落库，DB 不存明文。"""


class AgentLoop:
    """Agent 主循环。

    委托 AnswerEngine 执行核心逻辑，自身仅负责构造和结果转换。
    """

    def __init__(
        self,
        *,
        llm: LLMProvider,
        adapter: PlatformAdapter,
        rag: RAGPipeline,
        max_steps: int = 4,
    ) -> None:
        self.engine = get_answer_engine(
            llm=llm,
            rag=rag,
            adapter=adapter,
            max_steps=max_steps,
        )

    async def handle(self, session: Session, user_text: str) -> AgentResult:
        """处理用户消息，返回回复结果。"""
        result: AnswerResult = await self.engine.answer_agent(session, user_text)

        return AgentResult(
            reply=result.answer,
            handoff=result.handoff,
            tool_calls_made=result.tool_calls_made,
            masked_answer=result.masked_answer or result.answer,
        )
