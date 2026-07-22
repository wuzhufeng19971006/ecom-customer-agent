"""事件驱动：EventType + Event + EventBus。

按 spec 定义事件：
    TEXT_MESSAGE     用户文本消息
    IMAGE_UPLOAD    用户上传图片
    OCR_COMPLETE    OCR 完成
    VISION_COMPLETE Vision 完成
    TIMEOUT         超时（用于触发 BEST_EFFORT）

EventBus 用 asyncio 实现，进程内异步分发，不引入外部中间件。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Awaitable

from common.logger.logger import get_logger

log = get_logger(__name__)


class EventType(str, Enum):
    TEXT_MESSAGE = "text"
    IMAGE_UPLOAD = "image"
    OCR_COMPLETE = "ocr_complete"
    VISION_COMPLETE = "vision_complete"
    TIMEOUT = "timeout"
    ANSWER_READY = "answer_ready"


@dataclass
class Event:
    type: EventType
    session_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# 事件回调签名
EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    """进程内异步事件总线。"""

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._queue: asyncio.Queue[Event] | None = None
        self._consumer_task: asyncio.Task | None = None

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    async def publish(self, event: Event) -> None:
        if self._queue is None:
            # 没启动消费者时直接同步分发
            await self._dispatch(event)
            return
        await self._queue.put(event)

    async def start(self) -> None:
        if self._consumer_task is not None:
            return
        self._queue = asyncio.Queue()
        self._consumer_task = asyncio.create_task(self._consume())

    async def stop(self) -> None:
        if self._consumer_task is None:
            return
        self._consumer_task.cancel()
        try:
            await self._consumer_task
        except asyncio.CancelledError:
            pass
        self._consumer_task = None
        self._queue = None

    async def _consume(self) -> None:
        assert self._queue is not None
        while True:
            event = await self._queue.get()
            try:
                await self._dispatch(event)
            except Exception as e:  # noqa: BLE001
                log.error("eventbus.dispatch_failed", event_type=event.type, error=str(e))

    async def _dispatch(self, event: Event) -> None:
        for handler in self._handlers.get(event.type, []):
            try:
                await handler(event)
            except Exception as e:  # noqa: BLE001
                log.error(
                    "eventbus.handler_failed",
                    event_type=event.type,
                    handler=handler.__name__,
                    error=str(e),
                )


# 全局事件总线单例
_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
