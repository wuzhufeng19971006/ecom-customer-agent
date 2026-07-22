"""Image Analyzer：编排 vision + ocr，产出最终的多模态上下文。

流程：
    图片
     ├── VisionService  → VisionContext（结构化语义）
     ├── OCRService     → OCRResult（全量文本）
     └── filter_ocr_text → 过滤后的相关文本

最终输出 MultimodalContext，供 ConversationManager / QueryRewrite 使用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.llm.base import ImagePart
from app.multimodal.ocr_service import OCRResult, filter_ocr_text, get_ocr
from app.multimodal.vision_service import VisionContext, VisionService

log = get_logger(__name__)


@dataclass
class MultimodalContext:
    """单次图片分析的综合结果。"""

    vision: VisionContext | None = None
    ocr_full: list[str] = field(default_factory=list)  # OCR 全量文本（未过滤）
    ocr_filtered: list[str] = field(default_factory=list)  # 过滤后保留的相关文本
    ocr_raw: OCRResult | None = None

    def to_prompt_block(self) -> str:
        """供 RAG / LLM 引用的紧凑文本块。"""
        parts: list[str] = []
        if self.vision:
            parts.append(self.vision.to_prompt_block())
        if self.ocr_filtered:
            parts.append("[OCR_Filtered]\n" + "\n".join(self.ocr_filtered))
        return "\n".join(parts) if parts else ""


class ImageAnalyzer:
    def __init__(
        self,
        *,
        vision: VisionService | None = None,
        ocr: Any = None,
    ) -> None:
        self.vision = vision or VisionService()
        # ocr 默认走 get_ocr()，但避免在模块导入时初始化（依赖 MiMo client）
        self._ocr = ocr

    async def analyze(self, images: list[ImagePart]) -> MultimodalContext:
        if not images:
            return MultimodalContext()

        # 并行执行 vision + ocr（独立任务）
        import asyncio

        ocr_svc = self._ocr or get_ocr()
        vision_task = asyncio.create_task(self.vision.analyze(images))
        ocr_task = asyncio.create_task(ocr_svc.extract(images))

        vision_ctx, ocr_result = await asyncio.gather(
            vision_task, ocr_task, return_exceptions=False
        )

        # OCR 过滤：依赖 vision_context 做相关性判断
        filtered = filter_ocr_text(ocr_result, vision_ctx)

        log.info(
            "image_analyzer.done",
            page_type=vision_ctx.page_type,
            confidence=vision_ctx.confidence,
            ocr_full=len(ocr_result.full_text),
            ocr_filtered=len(filtered),
        )

        return MultimodalContext(
            vision=vision_ctx,
            ocr_full=ocr_result.full_text,
            ocr_filtered=filtered,
            ocr_raw=ocr_result,
        )
