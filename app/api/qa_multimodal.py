"""多模态答疑 API：POST /api/qa/multimodal。

支持场景：
1. 图片 + 文本（一次请求中包含两者）
2. 仅图片（后端走图片分析，置信度足够时直接回答）
3. 多轮：通过 session_id 关联多次请求（先发图、后发文本）

请求格式：multipart/form-data
    - session_id (可选，不传则新建)
    - text (可选)
    - image (可选，文件)
    - wait (默认 true，是否同步等待回答)

响应：
{
    "session_id": "...",
    "answer": "...",
    "matched": true,
    "status": "ANSWERED",
    "vision_confidence": 0.85
}
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel, Field

from app.conversation.manager import get_conversation_manager
from app.conversation.state import ConversationStatus
from app.core.logging import get_logger

router = APIRouter(prefix="/api", tags=["qa_multimodal"])
log = get_logger(__name__)


class MultimodalResponse(BaseModel):
    session_id: str
    answer: str = ""
    matched: bool = False
    status: str = "PROCESSING"
    vision_confidence: float = 0.0
    message: str = ""


@router.post("/qa/multimodal", response_model=MultimodalResponse)
async def qa_multimodal(
    text: str | None = Form(default=None),
    image: UploadFile | None = File(default=None),
    session_id: str | None = Form(default=None),
    wait: bool = Form(default=True),
) -> MultimodalResponse:
    sid = session_id or f"sess-{uuid.uuid4().hex[:12]}"
    manager = get_conversation_manager()

    has_image = image is not None and image.filename
    has_text = bool(text and text.strip())

    if not has_image and not has_text:
        return MultimodalResponse(
            session_id=sid,
            status="REJECTED",
            message="必须提供 text 或 image 中的至少一个",
        )

    # 仅图片、无文本场景：触发图片分析，等待后续输入或置信度足够时直接回答
    if has_image and not has_text:
        img_bytes = await image.read()  # type: ignore[union-attr]
        await manager.ingest_image(
            sid,
            img_bytes,
            mime_type=image.content_type or "image/jpeg",  # type: ignore[union-attr]
        )
        if not wait:
            return MultimodalResponse(
                session_id=sid,
                status="WAITING_USER",
                message="图片已接收，正在分析。请继续描述您的问题，或等待自动回答。",
            )
        # 等待图片分析完成，若置信度足够会自动回答
        # 这里给一个较短的等待窗口，不强制立即回答
        state = manager.get_session(sid)
        if state:
            import asyncio
            for _ in range(30):  # 最多等 9 秒
                await asyncio.sleep(0.3)
                if state.status in (ConversationStatus.ANSWERED, ConversationStatus.WAITING_USER):
                    break
            if state.status == ConversationStatus.ANSWERED:
                return MultimodalResponse(
                    session_id=sid,
                    answer=state.messages[-1].text if state.messages else "",
                    matched=True,
                    status=state.status.value,
                    vision_confidence=state.extracted_context.confidence,
                )
        return MultimodalResponse(
            session_id=sid,
            status="WAITING_USER",
            vision_confidence=state.extracted_context.confidence if state else 0.0,
            message="图片已分析。请描述您的问题，我会结合图片为您解答。",
        )

    # 图片 + 文本：完整请求，直接同步等待回答
    if has_image and has_text:
        img_bytes = await image.read()  # type: ignore[union-attr]
        answer = await manager.handle_image_and_text_and_wait(
            sid,
            img_bytes,
            text.strip(),  # type: ignore[union-attr]
            mime_type=image.content_type or "image/jpeg",  # type: ignore[union-attr]
        )
        state = manager.get_session(sid)
        return MultimodalResponse(
            session_id=sid,
            answer=answer,
            matched=bool(answer and "无法回答" not in answer),
            status=state.status.value if state else "ANSWERED",
            vision_confidence=state.extracted_context.confidence if state else 0.0,
        )

    # 纯文本：走标准 RAG 流程
    answer = await manager.handle_text_and_wait(sid, text.strip())  # type: ignore[union-attr]
    state = manager.get_session(sid)
    return MultimodalResponse(
        session_id=sid,
        answer=answer,
        matched=bool(answer and "无法回答" not in answer),
        status=state.status.value if state else "ANSWERED",
        vision_confidence=0.0,
    )
