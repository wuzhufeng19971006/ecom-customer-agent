"""会话管理：维护对话上下文、从 DB 恢复历史。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from runtime.llm.llm_provider import Message

MAX_HISTORY = 20  # 单会话最多保留 N 轮


class Session:
    def __init__(self, session_id: str, platform: str, buyer_id: str, shop_id: str) -> None:
        self.session_id = session_id
        self.platform = platform
        self.buyer_id = buyer_id
        self.shop_id = shop_id
        self.messages: list[Message] = []
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = self.created_at
        self.meta: dict[str, Any] = {}

    def append(self, msg: Message) -> None:
        self.messages.append(msg)
        if len(self.messages) > MAX_HISTORY * 2:
            self.messages = self.messages[-MAX_HISTORY * 2 :]
        self.updated_at = datetime.now(timezone.utc)

    def to_llm_messages(self, system_prompt: str) -> list[Message]:
        return [Message(role="system", content=system_prompt), *self.messages]
