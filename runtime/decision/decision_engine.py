"""决策引擎：判断何时回答、何时等待。

按 spec 逻辑：
    if has_text and has_image:        -> ANSWER
    if image_confidence > 0.85:        -> ANSWER
    if timeout:                        -> BEST_EFFORT
    else:                              -> WAIT
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from common.config.config import settings
from runtime.conversation.state import ConversationState


class Decision(str, Enum):
    ANSWER = "ANSWER"               # 立即回答
    WAIT = "WAIT"                   # 继续等待用户输入
    BEST_EFFORT = "BEST_EFFORT"     # 超时兜底，尽力回答


@dataclass
class DecisionContext:
    has_text: bool
    has_image: bool
    image_confidence: float
    elapsed_since_last_event_sec: float


class DecisionEngine:
    def __init__(
        self,
        *,
        confidence_threshold: float | None = None,
        timeout_sec: int | None = None,
    ) -> None:
        self.confidence_threshold = confidence_threshold or settings.vision_confidence_threshold
        self.timeout_sec = timeout_sec or settings.conversation_timeout_sec

    def decide(self, state: ConversationState, *, now_ts: float | None = None) -> Decision:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc) if now_ts is None else datetime.fromtimestamp(now_ts, tz=timezone.utc)
        elapsed = (now - state.last_event_at).total_seconds()

        has_text = state.has_text()
        has_image = state.has_image()
        confidence = state.extracted_context.confidence

        # 1. 同时有文本和图片：立即回答
        if has_text and has_image:
            return Decision.ANSWER

        # 2. 图片置信度足够高：直接回答
        if has_image and confidence > self.confidence_threshold:
            return Decision.ANSWER

        # 3. 超时：尽力回答
        if elapsed > self.timeout_sec and (has_text or has_image):
            return Decision.BEST_EFFORT

        # 4. 纯文本场景：直接回答（保持向后兼容）
        if has_text and not has_image:
            return Decision.ANSWER

        # 5. 其他情况：等待
        return Decision.WAIT
