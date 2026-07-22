"""长期记忆存储（预留接口）。

电商客服场景通常不跨会话记忆用户信息（隐私敏感）。
后续若需要（如记住用户偏好、历史咨询摘要），再填充实现。

注意：跨会话记忆需配合 security/masker 做脱敏后存储。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class MemoryItem:
    """单条记忆。"""
    user_id: str
    content: str
    memory_type: str = "general"  # "preference" | "history" | "preference"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    meta: dict[str, Any] = field(default_factory=dict)


class MemoryStore:
    """长期记忆存储（预留接口）。

    TODO: 后续可对接 PostgreSQL / Redis / 向量库做语义检索
    """

    async def save(self, item: MemoryItem) -> str:
        """保存记忆。"""
        raise NotImplementedError("Memory store not implemented yet")

    async def recall(self, user_id: str, *, query: str = "", limit: int = 5) -> list[MemoryItem]:
        """检索记忆。"""
        raise NotImplementedError("Memory store not implemented yet")

    async def forget(self, user_id: str, memory_id: str | None = None) -> int:
        """删除记忆（GDPR right to be forgotten）。"""
        raise NotImplementedError("Memory store not implemented yet")
