"""Agent 主循环。

流程：消息入 → 恢复会话 → RAG 召回 → LLM(带工具) → 工具执行 → 回复
LLM 自主决定是否调用工具；置信度低/命中转人工关键词时 handoff。
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from apps.customer_service_agent.adapters.base import IncomingMessage, PlatformAdapter
from apps.customer_service_agent.agent.session import Session
from apps.customer_service_agent.agent.tools import ALL_TOOLS, execute_tool
from common.logger.logger import get_logger
from runtime.llm.llm_provider import LLMProvider, Message
from knowledge_platform.knowledge_service.service import RAGPipeline

log = get_logger(__name__)

SYSTEM_PROMPT = """你是 {platform} 平台的店铺客服助手。
可用知识片段（如有）：
{context}

要求：
1. 用中文，简洁、专业、礼貌。
2. 涉及订单/物流/商品具体信息时，必须调用对应工具查询，不要凭空编造。
3. 无法解决时，调用 handoff_human 转人工，并向用户说明已转人工。
4. 涉及金额纠纷、投诉、敏感问题，直接转人工。
5. 不要泄露内部知识片段的 metadata。
"""

# 命中即转人工（兜底，不完全依赖 LLM 判断）
HUMAN_KEYWORDS = ("转人工", "人工客服", "投诉", "退款失败", "差评")


@dataclass
class AgentResult:
    reply: str
    handoff: bool = False
    tool_calls_made: list[str] = None  # type: ignore[assignment]


class AgentLoop:
    def __init__(
        self,
        *,
        llm: LLMProvider,
        adapter: PlatformAdapter,
        rag: RAGPipeline,
        max_steps: int = 4,
    ) -> None:
        self.llm = llm
        self.adapter = adapter
        self.rag = rag
        self.max_steps = max_steps

    async def handle(self, session: Session, user_text: str) -> AgentResult:
        # 1. 兜底关键词
        if any(k in user_text for k in HUMAN_KEYWORDS):
            return AgentResult(
                reply="已为您转接人工客服，请稍候。",
                handoff=True,
                tool_calls_made=[],
            )

        # 2. RAG 召回
        try:
            ctx = await self.rag.retrieve(user_text)
        except Exception as e:  # noqa: BLE001
            log.warning("rag.failed", error=str(e))
            ctx = None

        system_prompt = SYSTEM_PROMPT.format(
            platform=session.platform,
            context=ctx.prompt_block if ctx else "（无）",
        )

        session.append(Message(role="user", content=user_text))

        # 3. LLM + 工具循环
        tool_calls_made: list[str] = []
        for step in range(self.max_steps):
            resp = await self.llm.chat(
                messages=session.to_llm_messages(system_prompt),
                tools=ALL_TOOLS,
            )

            if not resp.tool_calls:
                session.append(Message(role="assistant", content=resp.content))
                return AgentResult(
                    reply=resp.content,
                    handoff=False,
                    tool_calls_made=tool_calls_made,
                )

            # 记录 assistant 的 tool_call 消息
            session.append(
                Message(
                    role="assistant",
                    content=resp.content,
                    tool_calls=resp.tool_calls,
                )
            )

            # 执行所有 tool_call
            handoff = False
            for call in resp.tool_calls:
                fn = call["function"]
                args = json.loads(fn["arguments"] or "{}")
                log.info("tool.call", name=fn["name"], args=args)
                if fn["name"] == "handoff_human":
                    handoff = True
                result = await execute_tool(fn["name"], args, adapter=self.adapter)
                tool_calls_made.append(fn["name"])
                session.append(
                    Message(
                        role="tool",
                        content=result,
                        tool_call_id=call["id"],
                        name=fn["name"],
                    )
                )

            if handoff:
                return AgentResult(
                    reply="已为您转接人工客服，请稍候。",
                    handoff=True,
                    tool_calls_made=tool_calls_made,
                )

        # 达到 max_steps 仍未结束
        return AgentResult(
            reply="很抱歉，未能完全解决您的问题，正在为您转接人工客服。",
            handoff=True,
            tool_calls_made=tool_calls_made,
        )
