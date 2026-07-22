"""OCR 服务：独立提取图片中的全量文本。

抽象接口，便于后续替换为 PaddleOCR / 阿里云 OCR / 腾讯云 OCR。
当前默认实现 `MiMoOCRService` 复用 MiMo-V2.5 的 OCR 能力，
配合 `filter_ocr_text` 做噪声过滤，避免菜单/页脚污染 RAG。
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.llm.base import ImagePart
from app.llm.mimo import get_vlm
from app.multimodal.vision_service import VisionContext

log = get_logger(__name__)


@dataclass
class OCRResult:
    full_text: list[str] = field(default_factory=list)  # 全量原始文本片段
    blocks: list[dict[str, Any]] = field(default_factory=list)  # 带 bbox 的块（如果 OCR 提供）
    raw: dict[str, Any] | None = None


class OCRService(ABC):
    @abstractmethod
    async def extract(self, images: list[ImagePart]) -> OCRResult:
        """对图片做 OCR，返回全量文本（不过滤）。"""


class MiMoOCRService(OCRService):
    """复用 MiMo-V2.5 做 OCR。要求输出严格 JSON。"""

    OCR_PROMPT = """请对图片做 OCR 文本提取，输出严格 JSON：
{
  "text_blocks": [
    {"text": "片段原文", "category": "title|content|menu|footer|navigation|button|other"}
  ]
}

要求：
1. 按视觉位置从上到下、从左到右提取
2. 保留原文，不要改写、不要翻译、不要合并
3. category 必须给出，区分核心内容与导航/菜单/页脚等噪声
4. 只输出 JSON，不要任何 markdown 或解释
"""

    def __init__(self) -> None:
        self.vlm = get_vlm()

    async def extract(self, images: list[ImagePart]) -> OCRResult:
        if not images:
            return OCRResult()

        try:
            resp = await self.vlm.analyze(
                prompt=self.OCR_PROMPT,
                images=images,
                temperature=0.0,
                max_tokens=2048,
                response_format_json=True,
            )
        except Exception as e:  # noqa: BLE001
            log.error("ocr.extract_failed", error=str(e))
            return OCRResult()

        return self._parse(resp.content)

    def _parse(self, content: str) -> OCRResult:
        text = content.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip("` \n")

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            log.error("ocr.parse_failed", error=str(e), content=content[:200])
            return OCRResult()

        blocks = list(data.get("text_blocks", []))
        full_text = [str(b.get("text", "")) for b in blocks if b.get("text")]
        return OCRResult(full_text=full_text, blocks=blocks, raw=data)


# ===== OCR 噪声过滤机制 =====

NOISE_CATEGORIES = {"menu", "footer", "navigation", "button"}
CORE_CATEGORIES = {"title", "content"}


def filter_ocr_text(
    ocr_result: OCRResult,
    vision_context: VisionContext,
) -> list[str]:
    """过滤 OCR 噪声，只保留与 vision_context 相关的文本。

    优先级：
    1. 标注区域附近的文字（user_annotation != none 时优先保留 core 类）
    2. 页面核心字段（title / content 类）
    3. Vision 判断相关的文本（与 focus_area / possible_intent 字面匹配）

    过滤：
    - 菜单、页脚、导航栏、按钮等无业务意义文字
    """
    if not ocr_result.blocks:
        # 没有 block 分类信息时，退化为返回 full_text（最坏情况）
        return ocr_result.full_text

    # 关键词集合：vision 判断的相关文本
    vision_keywords: set[str] = set()
    if vision_context.focus_area:
        vision_keywords.update(_tokenize(vision_context.focus_area))
    for intent in vision_context.possible_intent:
        vision_keywords.update(_tokenize(intent))

    kept: list[str] = []
    for block in ocr_result.blocks:
        cat = str(block.get("category", "other")).lower()
        text = str(block.get("text", "")).strip()
        if not text:
            continue

        # 1. 噪声类直接过滤
        if cat in NOISE_CATEGORIES:
            continue

        # 2. 核心类直接保留
        if cat in CORE_CATEGORIES:
            kept.append(text)
            continue

        # 3. other 类：若与 vision 关键词有重叠则保留，否则丢弃
        tokens = set(_tokenize(text))
        if vision_keywords & tokens:
            kept.append(text)

    return kept


def _tokenize(text: str) -> list[str]:
    """简单中文分词：按非字母数字字符切分，保留长度 >= 2 的片段。"""
    import re

    tokens = re.split(r"[\s,，。.、;；:：!！?？/\\（）()【】\[\]\"'`-]+", text)
    return [t for t in tokens if len(t) >= 2]


_ocr: OCRService | None = None


def get_ocr() -> OCRService:
    global _ocr
    if _ocr is None:
        _ocr = MiMoOCRService()
    return _ocr
