"""ConversationManager：编排整体多轮会话流程。

按 spec 的 Agent 调用流程：
    用户
      ↓
    Gateway (HTTP / Webhook)
      ↓
    ConversationManager
      ↓
    判断输入是否完整 (DecisionEngine)
      |
      ├── 图片 → ImageAnalyzer → Context
      ├── 文字 → QueryRewrite
      └── 两者 → RAG → LLM → 回答

特性：
1. 500ms debounce：连续消息合并一次回答
2. 事件驱动：图片上传不立即回答，触发 Vision 任务后等待用户继续输入
3. 多轮上下文：累积 messages / images / extracted_context
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from app.agent.qa import QAService
from app.agent_runtime.conversation.context_builder import ContextBuilder
from app.agent_runtime.decision.decision_engine import Decision, DecisionEngine
from app.agent_runtime.conversation.event import EventBus, Event, EventType, get_event_bus
from app.agent_runtime.conversation.state import (
    ConversationState,
    ConversationStatus,
    ExtractedContext,
    MessageItem,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.llm.base import ImagePart
from app.multimodal.image_analyzer import ImageAnalyzer

log = get_logger(__name__)


class ConversationManager:
    """单进程内会话管理（多实例需自行扩展持久化）。"""

    def __init__(
        self,
        *,
        image_analyzer: ImageAnalyzer | None = None,
        qa_service: QAService | None = None,
        query_rewrite: ContextBuilder | None = None,
        decision_engine: DecisionEngine | None = None,
        event_bus: EventBus | None = None,
        debounce_ms: int | None = None,
    ) -> None:
        self.image_analyzer = image_analyzer or ImageAnalyzer()
        self.qa = qa_service or QAService()
        self.query_rewrite = query_rewrite or ContextBuilder()
        self.decision = decision_engine or DecisionEngine()
        self.bus = event_bus or get_event_bus()
        self.debounce_ms = debounce_ms or settings.conversation_debounce_ms

        self._sessions: dict[str, ConversationState] = {}
        self._debounce_tasks: dict[str, asyncio.Task] = {}

    # ===== 会话生命周期 =====

    def get_or_create_session(
        self,
        session_id: str | None = None,
        *,
        platform: str = "taobao",
        buyer_id: str = "",
        shop_id: str = "",
    ) -> ConversationState:
        sid = session_id or f"sess-{uuid.uuid4().hex[:12]}"
        if sid in self._sessions:
            return self._sessions[sid]
        state = ConversationState(
            session_id=sid,
            platform=platform,
            buyer_id=buyer_id,
            shop_id=shop_id,
        )
        self._sessions[sid] = state
        return state

    def get_session(self, session_id: str) -> ConversationState | None:
        return self._sessions.get(session_id)

    # ===== 消息接入 =====

    async def ingest_text(self, session_id: str, text: str) -> ConversationState:
        state = self.get_or_create_session(session_id)
        state.messages.append(MessageItem(role="user", text=text))
        state.touch()
        await self.bus.publish(
            Event(
                type=EventType.TEXT_MESSAGE,
                session_id=session_id,
                payload={"text": text},
            )
        )
        # 触发 debounce 回调（500ms 内的连续消息合并）
        self._schedule_debounce(session_id)
        return state

    async def ingest_image(
        self,
        session_id: str,
        image_data: bytes,
        *,
        mime_type: str = "image/jpeg",
    ) -> ConversationState:
        state = self.get_or_create_session(session_id)
        img_msg = MessageItem(
            role="user",
            image_data=image_data,
            image_mime=mime_type,
        )
        state.messages.append(img_msg)
        state.images.append(img_msg)
        state.touch()
        state.status = ConversationStatus.PROCESSING  # 图片触发后台分析

        await self.bus.publish(
            Event(
                type=EventType.IMAGE_UPLOAD,
                session_id=session_id,
                payload={"size": len(image_data), "mime": mime_type},
            )
        )

        # 异步触发 vision + ocr，不立即回答
        asyncio.create_task(self._analyze_images(session_id))
        return state

    # ===== 内部：图片分析 =====

    async def _analyze_images(self, session_id: str) -> None:
        state = self._sessions.get(session_id)
        if not state or not state.images:
            return

        image_parts = [
            ImagePart(data=im.image_data, mime_type=im.image_mime)
            for im in state.images
            if im.image_data
        ]
        if not image_parts:
            return

        try:
            ctx = await self.image_analyzer.analyze(image_parts)
        except Exception as e:  # noqa: BLE001
            log.error("conversation.image_analyze_failed", session_id=session_id, error=str(e))
            state.status = ConversationStatus.WAITING_USER
            return

        extracted = ExtractedContext(
            vision_summary=ctx.vision.to_prompt_block() if ctx.vision else "",
            ocr_filtered=ctx.ocr_filtered,
            possible_intent=ctx.vision.possible_intent if ctx.vision else [],
            confidence=ctx.vision.confidence if ctx.vision else 0.0,
        )
        state.merge_context(extracted)

        await self.bus.publish(
            Event(
                type=EventType.VISION_COMPLETE,
                session_id=session_id,
                payload={"confidence": extracted.confidence},
            )
        )

        # 图片分析完成后不立即回答，等待用户继续输入（按 spec）
        # 但若置信度足够高，直接触发回答
        if extracted.confidence > settings.vision_confidence_threshold:
            state.status = ConversationStatus.READY
            self._schedule_debounce(session_id, delay_ms=0)
        else:
            state.status = ConversationStatus.WAITING_USER

    # ===== 内部：debounce 调度 =====

    def _schedule_debounce(self, session_id: str, *, delay_ms: int | None = None) -> None:
        delay = delay_ms if delay_ms is not None else self.debounce_ms

        # 取消已有 debounce
        old = self._debounce_tasks.get(session_id)
        if old and not old.done():
            old.cancel()

        if delay <= 0:
            # 立即触发
            asyncio.create_task(self._on_debounce(session_id))
            return

        async def _waiter() -> None:
            try:
                await asyncio.sleep(delay / 1000.0)
                await self._on_debounce(session_id)
            except asyncio.CancelledError:
                pass

        self._debounce_tasks[session_id] = asyncio.create_task(_waiter())

    async def _on_debounce(self, session_id: str) -> None:
        """debounce 窗口结束，做决策。"""
        state = self._sessions.get(session_id)
        if not state:
            return

        decision = self.decision.decide(state)
        if decision in (Decision.ANSWER, Decision.BEST_EFFORT):
            asyncio.create_task(self._generate_answer(session_id, best_effort=(decision == Decision.BEST_EFFORT)))

    # ===== 内部：生成回答 =====

    async def _generate_answer(self, session_id: str, *, best_effort: bool = False) -> str:
        state = self._sessions.get(session_id)
        if not state:
            return ""

        state.status = ConversationStatus.PROCESSING

        user_text = state.latest_text()
        has_image = state.has_image()

        try:
            if has_image:
                # 多模态：走 query rewrite 融合 context，再走 RAG
                rewritten = await self.query_rewrite.rewrite(
                    user_text=user_text,
                    vision_summary=state.extracted_context.vision_summary,
                    ocr_filtered=state.extracted_context.ocr_filtered,
                    possible_intents=state.extracted_context.possible_intent,
                )
                log.info(
                    "conversation.rewritten_query",
                    session_id=session_id,
                    original=user_text[:80],
                    rewritten=rewritten[:80],
                )
                result = await self.qa.answer(rewritten)
            else:
                # 纯文本：直接走 RAG
                result = await self.qa.answer(user_text)

            if best_effort and not result.matched:
                # 超时兜底：加上引导语
                result.answer = (
                    f"{result.answer}\n\n如需进一步帮助，请提供更多信息或联系人工客服。"
                )

            # 记录到会话
            state.messages.append(MessageItem(role="assistant", text=result.answer))
            state.status = ConversationStatus.ANSWERED
            state.touch()

            await self.bus.publish(
                Event(
                    type=EventType.ANSWER_READY,
                    session_id=session_id,
                    payload={"answer": result.answer, "matched": result.matched},
                )
            )
            return result.answer

        except Exception as e:  # noqa: BLE001
            log.error("conversation.generate_failed", session_id=session_id, error=str(e))
            state.status = ConversationStatus.WAITING_USER
            fallback = "抱歉，处理过程中出现异常，请稍后重试或联系人工客服。"
            state.messages.append(MessageItem(role="assistant", text=fallback))
            return fallback

    # ===== 同步等待接口（便于 HTTP 路由直接返回）=====

    async def handle_text_and_wait(
        self, session_id: str, text: str, *, timeout_sec: float = 30.0
    ) -> str:
        """同步处理一条文本消息，等待回答生成完成。

        适用于 HTTP API 场景：客户端发请求 → 等待回答返回。
        内部仍走 debounce + 决策，但等待 ANSWER_READY 事件。
        """
        state = self.get_or_create_session(session_id)
        future: asyncio.Future[str] = asyncio.get_event_loop().create_future()

        async def _on_answer(event: Event) -> None:
            if not future.done():
                future.set_result(event.payload.get("answer", ""))

        self.bus.subscribe(EventType.ANSWER_READY, _on_answer)
        await self.ingest_text(session_id, text)

        # 立即触发决策（HTTP 场景不等 debounce）
        decision = self.decision.decide(state)
        if decision in (Decision.ANSWER, Decision.BEST_EFFORT):
            asyncio.create_task(
                self._generate_answer(session_id, best_effort=(decision == Decision.BEST_EFFORT))
            )

        try:
            return await asyncio.wait_for(future, timeout=timeout_sec)
        except asyncio.TimeoutError:
            return "处理超时，请稍后重试或联系人工客服。"

    async def handle_image_and_text_and_wait(
        self,
        session_id: str,
        image_data: bytes,
        text: str,
        *,
        mime_type: str = "image/jpeg",
        timeout_sec: float = 60.0,
    ) -> str:
        """同步处理图片+文本，等待回答。"""
        future: asyncio.Future[str] = asyncio.get_event_loop().create_future()

        async def _on_answer(event: Event) -> None:
            if not future.done():
                future.set_result(event.payload.get("answer", ""))

        self.bus.subscribe(EventType.ANSWER_READY, _on_answer)

        # 先 ingest 图片触发后台分析
        await self.ingest_image(session_id, image_data, mime_type=mime_type)

        # 等待 vision + ocr 完成（轮询 state.status）
        deadline = (datetime.now(timezone.utc).timestamp()) + timeout_sec
        while datetime.now(timezone.utc).timestamp() < deadline:
            state = self._sessions.get(session_id)
            if state and state.extracted_context.confidence > 0:
                break
            await asyncio.sleep(0.3)

        # 注入文本，立即触发回答
        await self.ingest_text(session_id, text)
        state = self._sessions.get(session_id)
        if state:
            asyncio.create_task(self._generate_answer(session_id, best_effort=False))

        try:
            return await asyncio.wait_for(future, timeout=timeout_sec)
        except asyncio.TimeoutError:
            return "处理超时，请稍后重试或联系人工客服。"


# 全局单例
_manager: ConversationManager | None = None


def get_conversation_manager() -> ConversationManager:
    global _manager
    if _manager is None:
        _manager = ConversationManager()
    return _manager
