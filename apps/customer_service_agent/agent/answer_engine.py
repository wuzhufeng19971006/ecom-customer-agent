"""统一回答引擎：两条路径（Webhook / HTTP）共享的核心逻辑。

职责：
1. 脱敏（Masker）— 敏感信息不进入 LLM 和 embedding
2. RAG 召回 — 知识库检索
3. LLM 调用 — 带/不带工具
4. JSON 结构化解析 — matched 判定
5. 恢复脱敏 — 回复中还原占位符

三种调用模式：
- answer_qa: 简单问答（无状态、无工具），供 QAService 使用
- answer_agent: Agent 模式（有状态、有工具循环），供 AgentLoop 使用
- answer_multimodal: 多模态（先 query rewrite 再问答），供 ConversationManager 使用
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from apps.customer_service_agent.adapters.base import PlatformAdapter
from apps.customer_service_agent.agent.session import Session
from apps.customer_service_agent.agent.tools import ALL_TOOLS, create_tool_executor
from common.logger.logger import get_logger
from knowledge_platform.knowledge_service.retriever.retriever import RetrievalHit
from knowledge_platform.knowledge_service.service import RAGPipeline
from runtime.conversation.context_builder import ContextBuilder
from runtime.llm.llm_provider import LLMProvider, Message
from security.data_mask.masker import Masker
from tool_center.manager.tool_executor import ToolExecutor

log = get_logger(__name__)

# ===== 共享常量 =====

QA_SYSTEM_PROMPT = """你是店铺客服助手，专门解答顾客咨询。
你必须严格遵守以下规则：
1. 只能基于下方【知识库片段】回答问题，禁止使用任何不在片段中的信息。
2. 顾客的问题可能用不同的措辞表达，只要与知识库片段的语义相关，就应当回答。例如"下单后多久到"与"发货时间"、"正品吗"与"是不是正品"是同一个问题。
3. 回答时基于片段内容，可以调整语气使其更自然，但事实必须与片段一致，不得编造。
4. 只有当知识库片段确实与问题完全无关时，才回复："抱歉，这个问题我暂时无法回答，已为您转人工。" 并将 matched 设为 false。
5. 回答简洁、专业、礼貌，使用中文。
6. 不暴露知识库 metadata、片段编号等内部信息。

你必须以 JSON 格式回复，格式如下：
{"answer": "你的回答内容", "matched": true或false}

- matched 为 true 表示知识库片段与问题相关，已给出有效回答。
- matched 为 false 表示知识库片段与问题无关，无法回答，需转人工。
"""

QA_USER_TEMPLATE = """【知识库片段】
{context}

【顾客问题】
{question}

请以 JSON 格式回复：{{"answer": "...", "matched": true/false}}"""

AGENT_SYSTEM_PROMPT = """你是 {platform} 平台的店铺客服助手。
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


# ===== 统一返回结构 =====


@dataclass
class AnswerResult:
    """统一回答结果，覆盖三种模式的输出。"""

    answer: str
    matched: bool = True
    handoff: bool = False
    sources: list[RetrievalHit] = field(default_factory=list)
    tool_calls_made: list[str] = field(default_factory=list)
    masked_answer: str = ""
    """脱敏后的回复（含占位符），用于 DB 持久化。

    与 answer 的区别：answer 已 restore（含真实敏感信息），用于发送给用户；
    masked_answer 保留占位符，用于落库，确保 DB 不存明文。
    无敏感信息时 masked_answer 与 answer 相同。
    """


class AnswerEngine:
    """统一回答引擎。

    被 AgentLoop（Webhook）、QAService（HTTP 文本）、ConversationManager（HTTP 多模态）
    三条路径共享，保证脱敏/RAG/LLM/解析行为一致。
    """

    def __init__(
        self,
        *,
        llm: LLMProvider,
        rag: RAGPipeline,
        adapter: PlatformAdapter | None = None,
        top_k: int = 10,
        top_n: int = 3,
        max_steps: int = 4,
    ) -> None:
        self.llm = llm
        self.rag = rag
        self.adapter = adapter
        self.top_k = top_k
        self.top_n = top_n
        self.max_steps = max_steps
        # 工具执行器：adapter 为 None 时不支持工具调用
        self.tool_executor: ToolExecutor | None = (
            create_tool_executor(adapter) if adapter else None
        )
        # query rewrite（多模态用）
        self._context_builder: ContextBuilder | None = None

    # ===== 共享工具方法 =====

    @staticmethod
    def mask(text: str) -> tuple[str, Masker]:
        """脱敏文本，返回 (masked_text, masker)。

        masker 用于后续 restore 调用。
        每次调用创建新 Masker，避免映射表跨请求污染。
        """
        masker = Masker()
        masked = masker.mask_text(text).masked
        return masked, masker

    @staticmethod
    def restore(masker: Masker, text: str) -> str:
        """恢复脱敏文本。"""
        return masker.restore(text)

    @staticmethod
    def parse_json_response(raw: str) -> tuple[str, bool]:
        """解析 LLM 的 JSON 结构化回复。

        预期格式：{"answer": "...", "matched": true/false}
        解析失败时回退到字符串启发式，保证健壮性。
        """
        raw = raw.strip()
        try:
            data = json.loads(raw)
            answer = str(data.get("answer", "")).strip()
            matched = bool(data.get("matched", False))
            if answer:
                return answer, matched
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            log.warning("answer_engine.json_parse_failed", error=str(e), raw=raw[:200])

        # 回退：从纯文本中提取答案，用旧启发式判断 matched
        answer = raw
        matched = "无法回答" not in answer and "转人工" not in answer
        return answer, matched

    @staticmethod
    def check_human_keywords(text: str) -> bool:
        """检查是否命中转人工关键词。"""
        return any(k in text for k in HUMAN_KEYWORDS)

    async def _retrieve(
        self,
        query: str,
        collections: list[str] | None = None,
    ) -> list[RetrievalHit]:
        """RAG 召回，返回命中片段列表。"""
        try:
            ctx = await self.rag.retrieve(
                query,
                collections=collections,
                top_k=self.top_k,
                top_n=self.top_n,
            )
            return ctx.hits
        except Exception as e:  # noqa: BLE001
            log.warning("answer_engine.rag_failed", error=str(e))
            return []

    @staticmethod
    def _build_context_block(hits: list[RetrievalHit]) -> str:
        """将检索片段拼接为 context 文本块。"""
        return "\n---\n".join(f"[{i+1}] {h.text}" for i, h in enumerate(hits))

    # ===== 模式一：简单 QA（无状态、无工具）=====

    async def answer_qa(
        self,
        question: str,
        *,
        collections: list[str] | None = None,
    ) -> AnswerResult:
        """简单问答模式。

        流程：脱敏 → RAG(仅 kb_faq) → LLM(JSON) → 解析 → 恢复脱敏
        无状态、无工具、无会话上下文。

        供 QAService 和 ConversationManager（纯文本场景）调用。
        """
        question = question.strip()
        if not question:
            return AnswerResult(answer="请描述您的问题。", matched=False)

        # 1. 脱敏
        masked_question, masker = self.mask(question)

        # 2. RAG 召回
        hits = await self._retrieve(masked_question, collections or ["kb_faq"])
        if not hits:
            return AnswerResult(
                answer="抱歉，这个问题我暂时无法回答，已为您转人工。",
                matched=False,
            )

        # 3. 构建 prompt
        context_block = self._build_context_block(hits)
        user_msg = QA_USER_TEMPLATE.format(
            context=context_block,
            question=masked_question,
        )
        messages = [
            Message(role="system", content=QA_SYSTEM_PROMPT),
            Message(role="user", content=user_msg),
        ]

        # 4. LLM 调用（JSON 结构化输出）
        try:
            resp = await self.llm.chat(
                messages,
                temperature=0.1,
                max_tokens=512,
                response_format={"type": "json_object"},
            )
        except Exception as e:  # noqa: BLE001
            log.error("answer_engine.qa_llm_failed", error=str(e))
            return AnswerResult(
                answer="抱歉，服务暂时不可用，请稍后重试或联系人工客服。",
                matched=False,
                sources=hits,
            )

        # 5. 解析 + 恢复脱敏（masked_answer 保留占位符版本用于落库）
        answer, matched = self.parse_json_response(resp.content)
        masked_answer = answer
        answer = self.restore(masker, answer)

        return AnswerResult(
            answer=answer,
            matched=matched,
            sources=hits,
            masked_answer=masked_answer,
        )

    # ===== 模式二：Agent（有状态、有工具循环）=====

    async def answer_agent(
        self,
        session: Session,
        user_text: str,
    ) -> AnswerResult:
        """Agent 模式。

        流程：脱敏 → 关键词检查 → RAG → LLM(工具循环) → 恢复脱敏
        有状态（session）、有工具、有多轮上下文。

        供 AgentLoop（Webhook 路径）调用。
        """
        # 1. 脱敏
        masked_text, masker = self.mask(user_text)

        # 2. 兜底关键词
        if self.check_human_keywords(user_text):
            msg = "已为您转接人工客服，请稍候。"
            return AnswerResult(answer=msg, masked_answer=msg, handoff=True)

        # 3. RAG 召回（全集合）
        hits = await self._retrieve(masked_text)
        context_block = self._build_context_block(hits) if hits else "（无）"

        system_prompt = AGENT_SYSTEM_PROMPT.format(
            platform=session.platform,
            context=context_block,
        )

        # session 中保存脱敏后的文本
        session.append(Message(role="user", content=masked_text))

        # 4. LLM + 工具循环
        tool_calls_made: list[str] = []
        for step in range(self.max_steps):
            resp = await self.llm.chat(
                messages=session.to_llm_messages(system_prompt),
                tools=ALL_TOOLS,
            )

            if not resp.tool_calls:
                session.append(Message(role="assistant", content=resp.content))
                reply = self.restore(masker, resp.content)
                return AnswerResult(
                    answer=reply,
                    matched=False,
                    handoff=False,
                    sources=hits,
                    tool_calls_made=tool_calls_made,
                    masked_answer=resp.content,
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
                # 工具参数 restore
                args = {
                    k: self.restore(masker, v) if isinstance(v, str) else v
                    for k, v in args.items()
                }
                log.info("tool.call", name=fn["name"], args=args)
                if fn["name"] == "handoff_human":
                    handoff = True

                # 通过 ToolExecutor 执行
                if self.tool_executor:
                    exec_result = await self.tool_executor.execute(fn["name"], args)
                    if exec_result.success:
                        result = exec_result.output
                    else:
                        result = f"工具执行失败: {exec_result.error}"
                        log.warning(
                            "tool.exec_failed",
                            name=fn["name"],
                            error=exec_result.error,
                        )
                else:
                    result = "工具执行器未初始化"

                tool_calls_made.append(fn["name"])
                # 工具返回结果脱敏后再存入 session，避免真实 PII 进入后续 LLM 上下文
                masked_result = masker.mask_text(result).masked
                session.append(
                    Message(
                        role="tool",
                        content=masked_result,
                        tool_call_id=call["id"],
                        name=fn["name"],
                    )
                )

            if handoff:
                msg = "已为您转接人工客服，请稍候。"
                return AnswerResult(
                    answer=msg,
                    masked_answer=msg,
                    handoff=True,
                    sources=hits,
                    tool_calls_made=tool_calls_made,
                )

        # 达到 max_steps 仍未结束
        msg = "很抱歉，未能完全解决您的问题，正在为您转接人工客服。"
        return AnswerResult(
            answer=msg,
            masked_answer=msg,
            handoff=True,
            sources=hits,
            tool_calls_made=tool_calls_made,
        )

    # ===== 模式三：多模态（query rewrite + QA）=====

    async def answer_multimodal(
        self,
        question: str,
        *,
        vision_summary: str = "",
        ocr_filtered: list[str] | None = None,
        possible_intents: list[str] | None = None,
    ) -> AnswerResult:
        """多模态问答模式。

        流程：query rewrite（融合 vision/ocr） → answer_qa
        供 ConversationManager 调用。
        """
        if self._context_builder is None:
            self._context_builder = ContextBuilder(llm=self.llm)

        # 如果没有视觉上下文，直接走普通 QA
        if not vision_summary and not ocr_filtered:
            return await self.answer_qa(question)

        # query rewrite
        try:
            rewritten = await self._context_builder.rewrite(
                user_text=question,
                vision_summary=vision_summary,
                ocr_filtered=ocr_filtered,
                possible_intents=possible_intents,
            )
            log.info(
                "answer_engine.query_rewritten",
                original=question[:80],
                rewritten=rewritten[:80],
            )
        except Exception as e:  # noqa: BLE001
            log.warning("answer_engine.rewrite_failed", error=str(e))
            rewritten = question

        return await self.answer_qa(rewritten)


# ===== 工厂函数 =====


def get_answer_engine(
    *,
    llm: LLMProvider | None = None,
    rag: RAGPipeline | None = None,
    adapter: PlatformAdapter | None = None,
    max_steps: int = 4,
    top_k: int = 10,
    top_n: int = 3,
) -> AnswerEngine:
    """创建 AnswerEngine 实例。

    每次调用都创建新实例，确保注入参数（llm/rag/adapter/max_steps 等）始终生效。
    调用方自行持有返回的实例引用以复用。

    之前使用全局单例导致第二次调用起所有参数被忽略，
    淘宝 webhook 的 adapter 永远不会生效、测试无法注入 mock。
    """
    from runtime.llm.providers.deepseek import get_llm as _get_llm

    return AnswerEngine(
        llm=llm or _get_llm(),
        rag=rag or RAGPipeline(),
        adapter=adapter,
        max_steps=max_steps,
        top_k=top_k,
        top_n=top_n,
    )
