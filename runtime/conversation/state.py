"""会话状态：ConversationState + 状态机枚举。

按 spec 定义：
    COLLECTING    等待用户继续输入
    READY         输入完整，可以回答
    PROCESSING    正在生成回答
    ANSWERED      已回答完成
    WAITING_USER  等待用户继续
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ConversationStatus(str, Enum):
    COLLECTING = "COLLECTING"
    READY = "READY"
    PROCESSING = "PROCESSING"
    ANSWERED = "ANSWERED"
    WAITING_USER = "WAITING_USER"


@dataclass
class MessageItem:
    """会话中累积的一条消息（文本或图片）。"""

    role: str  # "user" | "assistant"
    text: str = ""
    image_data: bytes | None = None
    image_mime: str = "image/jpeg"
    arrived_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ExtractedContext:
    """从图片分析中提取的上下文。"""

    vision_summary: str = ""
    ocr_filtered: list[str] = field(default_factory=list)
    possible_intent: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class ConversationState:
    session_id: str
    platform: str = "taobao"
    buyer_id: str = ""
    shop_id: str = ""
    messages: list[MessageItem] = field(default_factory=list)
    images: list[MessageItem] = field(default_factory=list)  # 仅图片消息
    extracted_context: ExtractedContext = field(default_factory=ExtractedContext)
    status: ConversationStatus = ConversationStatus.COLLECTING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_event_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    meta: dict[str, Any] = field(default_factory=dict)

    def has_text(self) -> bool:
        return any(m.text for m in self.messages)

    def has_image(self) -> bool:
        return len(self.images) > 0

    def latest_text(self) -> str:
        """合并所有用户文本消息（用于多轮合并回答场景）。"""
        return " ".join(m.text for m in self.messages if m.text).strip()

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
        self.last_event_at = self.updated_at

    def merge_context(self, ctx: ExtractedContext) -> None:
        """合并新提取的上下文（图片+图片场景）。"""
        if ctx.vision_summary:
            self.extracted_context.vision_summary = ctx.vision_summary
        self.extracted_context.ocr_filtered.extend(ctx.ocr_filtered)
        self.extracted_context.possible_intent.extend(ctx.possible_intent)
        # 取最大置信度
        self.extracted_context.confidence = max(
            self.extracted_context.confidence, ctx.confidence
        )
