"""ContextBuilder：融合多模态 context 重写 RAG 查询。

按 spec 的 RAG Query 重构：
    用户文本 + Vision Context + OCR Context
      ↓
    ContextBuilder
      ↓
    Vector Search

例如：
    输入：
        图片：订单详情截图
        文字："为什么这里没有数据显示"
    生成查询：
        "订单详情页 优惠金额 支付金额 优惠未显示"
"""

from __future__ import annotations

import json
from typing import Any

from common.logger.logger import get_logger
from runtime.llm.llm_provider import LLMProvider, Message
from runtime.llm.providers.deepseek import get_llm

log = get_logger(__name__)


REWRITE_SYSTEM_PROMPT = """你是查询改写助手，专门为电商客服 RAG 系统服务。
你的任务是把用户的自然语言问题结合多模态上下文，改写为一个适合向量检索的查询语句。

改写规则：
1. 融合用户文本、Vision Context、OCR 过滤文本、可能的意图
2. 输出简洁的关键词组合，用空格分隔，不要完整句子
3. 去掉噪声词（"为什么"、"怎么"、"请问" 等），保留业务关键词
4. 如果用户文本为空，仅根据图片上下文生成查询
5. 严格输出 JSON：{"query": "改写后的查询"}

示例：
    用户文本: "为什么这里没有数据显示"
    Vision: page_type=order_detail, focus_area=payment_amount, possible_intent=["优惠未显示"]
    OCR过滤: ["优惠金额", "支付金额", "订单详情"]
    输出: {"query": "订单详情 优惠金额 支付金额 优惠未显示"}
"""


USER_TEMPLATE = """用户文本: {user_text}
Vision Context:
{vision_summary}
OCR 过滤文本:
{ocr_filtered}
可能意图:
{possible_intents}
"""


class ContextBuilder:
    def __init__(self, *, llm: LLMProvider | None = None) -> None:
        self.llm = llm or get_llm()

    async def rewrite(
        self,
        *,
        user_text: str,
        vision_summary: str = "",
        ocr_filtered: list[str] | None = None,
        possible_intents: list[str] | None = None,
    ) -> str:
        ocr_text = "\n".join(ocr_filtered) if ocr_filtered else "（无）"
        intents = "\n".join(f"- {i}" for i in (possible_intents or [])) or "（无）"
        vision = vision_summary or "（无）"

        user_msg = USER_TEMPLATE.format(
            user_text=user_text or "（无）",
            vision_summary=vision,
            ocr_filtered=ocr_text,
            possible_intents=intents,
        )

        messages = [
            Message(role="system", content=REWRITE_SYSTEM_PROMPT),
            Message(role="user", content=user_msg),
        ]

        try:
            resp = await self.llm.chat(
                messages,
                temperature=0.0,
                max_tokens=128,
                response_format={"type": "json_object"},
            )
        except Exception as e:  # noqa: BLE001
            log.error("query_rewrite.failed", error=str(e))
            # 降级：直接用用户文本 + OCR 关键词
            return self._fallback(user_text, ocr_filtered)

        return self._parse(resp.content, user_text, ocr_filtered)

    def _parse(
        self,
        content: str,
        user_text: str,
        ocr_filtered: list[str] | None,
    ) -> str:
        text = content.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip("` \n")
        try:
            data = json.loads(text)
            q = str(data.get("query", "")).strip()
            if q:
                return q
        except json.JSONDecodeError as e:
            log.warning("query_rewrite.parse_failed", error=str(e), content=content[:200])

        return self._fallback(user_text, ocr_filtered)

    def _fallback(self, user_text: str, ocr_filtered: list[str] | None) -> str:
        parts: list[str] = []
        if user_text:
            parts.append(user_text)
        if ocr_filtered:
            parts.extend(ocr_filtered[:5])  # OCR 取前 5 个关键词
        return " ".join(parts) if parts else "客服咨询"
