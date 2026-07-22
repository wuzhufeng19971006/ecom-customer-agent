"""Vision 服务：调用 MiMo-V2.5 输出结构化 vision_context。

严格按 spec 输出 JSON：
{
  "page_type": "order_detail",
  "focus_area": "payment_amount",
  "detected_text": ["优惠金额", ...],
  "user_annotation": "arrow",
  "possible_intent": ["优惠未显示", ...],
  "confidence": 0.78
}
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from common.logger.logger import get_logger
from runtime.llm.llm_provider import ImagePart
from runtime.llm.providers.mimo import get_vlm

log = get_logger(__name__)


VISION_PROMPT = """你是一个电商客服场景的图片分析助手。请仔细分析用户上传的图片，输出严格的 JSON 格式分析结果。

输出 JSON 字段说明：
- page_type: 图片所属页面类型，如 "order_detail" / "product_page" / "logistics" / "chat" / "refund_page" / "other"
- focus_area: 图片中用户最可能关注的核心区域（用短语描述，如 "payment_amount" / "delivery_address" / "sku_attribute"）
- detected_text: 图片中所有可见的文本片段列表（按视觉位置从上到下，保留原文，不要改写）
- user_annotation: 用户在图片上的标注类型，如 "arrow" / "circle" / "highlight" / "none"；如果没有标注则填 "none"
- possible_intent: 基于图片和标注推断用户可能的提问意图列表（1-3 条）
- confidence: 你对本次分析的置信度，0-1 之间小数

要求：
1. 必须输出合法 JSON，不要任何 markdown 代码块或解释文字
2. detected_text 保留原文，不要做语义合并或改写
3. possible_intent 用短语，不要长句
4. confidence 要诚实反映不确定性，模糊图片给低分
"""


@dataclass
class VisionContext:
    page_type: str = "other"
    focus_area: str = ""
    detected_text: list[str] = field(default_factory=list)
    user_annotation: str = "none"
    possible_intent: list[str] = field(default_factory=list)
    confidence: float = 0.0
    raw: dict[str, Any] | None = None

    def to_prompt_block(self) -> str:
        """供 RAG / LLM 引用的紧凑文本块。"""
        return (
            f"[VisionContext]\n"
            f"page_type={self.page_type}\n"
            f"focus_area={self.focus_area}\n"
            f"user_annotation={self.user_annotation}\n"
            f"possible_intent={','.join(self.possible_intent)}\n"
            f"confidence={self.confidence:.2f}"
        )


class VisionService:
    def __init__(self) -> None:
        self.vlm = get_vlm()

    async def analyze(self, images: list[ImagePart]) -> VisionContext:
        if not images:
            return VisionContext()

        try:
            resp = await self.vlm.analyze(
                prompt=VISION_PROMPT,
                images=images,
                temperature=0.1,
                max_tokens=1024,
                response_format_json=True,
            )
        except Exception as e:  # noqa: BLE001
            log.error("vision.analyze_failed", error=str(e))
            return VisionContext(confidence=0.0)

        return self._parse(resp.content)

    def _parse(self, content: str) -> VisionContext:
        # 容错：模型偶尔会包 markdown 代码块
        text = content.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip("` \n")

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            log.error("vision.parse_failed", error=str(e), content=content[:200])
            return VisionContext(confidence=0.0)

        return VisionContext(
            page_type=str(data.get("page_type", "other")),
            focus_area=str(data.get("focus_area", "")),
            detected_text=list(data.get("detected_text", [])),
            user_annotation=str(data.get("user_annotation", "none")),
            possible_intent=list(data.get("possible_intent", [])),
            confidence=float(data.get("confidence", 0.0)),
            raw=data,
        )
