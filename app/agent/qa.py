"""答疑服务：基于知识库的 RAG 问答。

策略（用户选「严格引用知识库原文，少改写」）：
1. 仅从 kb_faq 检索（一期答疑主场景）
2. Jina 精排取 Top-N
3. Prompt 强约束 LLM：只允许基于检索片段回答，无匹配时明确告知
4. 返回 {answer, sources, matched} 便于前端展示与审计
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.llm.base import LLMProvider, Message
from app.llm.deepseek import get_llm
from app.retrieval.chroma_store import RetrievalHit
from app.retrieval.rag import RAGPipeline

log = get_logger(__name__)

SYSTEM_PROMPT = """你是店铺客服助手，专门解答顾客咨询。
你必须严格遵守以下规则：
1. 只能基于下方【知识库片段】回答问题，禁止使用任何不在片段中的信息。
2. 严禁改写、加工、扩展片段内容；可以调整语气但事实必须一致。
3. 如果片段中没有相关内容，必须直接回复："抱歉，这个问题我暂时无法回答，已为您转人工。" 不得编造。
4. 回答简洁、专业、礼貌，使用中文，不超过片段本身长度。
5. 不暴露知识库 metadata、片段编号等内部信息。
"""

USER_TEMPLATE = """【知识库片段】
{context}

【顾客问题】
{question}
"""


@dataclass
class QAResponse:
    answer: str
    matched: bool
    sources: list[RetrievalHit]


class QAService:
    def __init__(
        self,
        *,
        rag: RAGPipeline | None = None,
        llm: LLMProvider | None = None,
        top_k: int = 10,
        top_n: int = 3,
    ) -> None:
        self.rag = rag or RAGPipeline()
        self.llm = llm or get_llm()
        self.top_k = top_k
        self.top_n = top_n

    async def answer(self, question: str) -> QAResponse:
        question = question.strip()
        if not question:
            return QAResponse(answer="请描述您的问题。", matched=False, sources=[])

        # 仅查 FAQ 集合
        ctx = await self.rag.retrieve(
            question,
            collections=["kb_faq"],
            top_k=self.top_k,
            top_n=self.top_n,
        )

        if not ctx.hits:
            # 知识库为空 / 召回失败
            return QAResponse(
                answer="抱歉，这个问题我暂时无法回答，已为您转人工。",
                matched=False,
                sources=[],
            )

        context_block = "\n---\n".join(
            f"[{i+1}] {h.text}" for i, h in enumerate(ctx.hits)
        )
        user_msg = USER_TEMPLATE.format(context=context_block, question=question)

        messages = [
            Message(role="system", content=SYSTEM_PROMPT),
            Message(role="user", content=user_msg),
        ]

        try:
            resp = await self.llm.chat(messages, temperature=0.1, max_tokens=512)
        except Exception as e:  # noqa: BLE001
            log.error("qa.llm_failed", error=str(e))
            return QAResponse(
                answer="抱歉，服务暂时不可用，请稍后重试或联系人工客服。",
                matched=False,
                sources=ctx.hits,
            )

        answer = resp.content.strip()
        # 检测 LLM 是否给出了"无法回答"的信号
        matched = "无法回答" not in answer and "转人工" not in answer

        return QAResponse(
            answer=answer,
            matched=matched,
            sources=ctx.hits,
        )
