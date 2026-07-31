"""电商平台 Webhook 入口。

POST /webhooks/doudian  — 抖店（抖音电商）消息推送
POST /webhooks/taobao   — 淘宝千牛消息推送（保留兼容）

一期默认接入抖店：
- 解析 payload → 验签 → 按 buyer_id 恢复会话 → 走 AgentLoop → 回复消息
- 安全：签名校验失败直接返回 403，拒绝处理
- 多轮：通过 SessionStore 按 buyer_id 恢复历史对话
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from apps.customer_service_agent.adapters.base import PlatformAdapter
from apps.customer_service_agent.adapters.doudian.adapter import (
    SignatureVerificationError,
    get_adapter,
)
from apps.customer_service_agent.agent.loop import AgentLoop
from apps.customer_service_agent.agent.session_store import get_session_store
from common.logger.logger import get_logger
from knowledge_platform.knowledge_service.service import RAGPipeline
from runtime.llm.llm_provider import Message
from runtime.llm.providers.deepseek import get_llm
from security.data_mask.masker import Masker

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = get_logger(__name__)

# 复用 RAGPipeline 单例，避免每条消息重复初始化 ChromaDB
_rag: RAGPipeline | None = None


def _get_rag() -> RAGPipeline:
    global _rag
    if _rag is None:
        _rag = RAGPipeline()
    return _rag


async def _handle_message(
    adapter: PlatformAdapter,
    platform: str,
    buyer_id: str,
    shop_id: str,
    content: str,
) -> dict[str, Any]:
    """通用消息处理：恢复会话 → AgentLoop → 持久化 → 回复。

    被 doudian / taobao 两个 webhook 共用，消除重复逻辑。

    安全：DB 中只存脱敏后文本（手机号/订单号等敏感信息不落明文），
    重启恢复时历史消息天然安全，不会把真实敏感信息发给 LLM。
    """
    store = get_session_store()
    session = await store.get_or_create(
        platform=platform,
        buyer_id=buyer_id,
        shop_id=shop_id,
    )

    # 脱敏后持久化用户消息（DB 不落明文）
    masked_content = Masker().mask_text(content).masked
    await store.save_message(session, Message(role="user", content=masked_content))

    loop = AgentLoop(
        llm=get_llm(),
        adapter=adapter,
        rag=_get_rag(),
    )
    result = await loop.handle(session, content)

    # 持久化助手回复（存脱敏版，masked_answer 含占位符不含明文）
    await store.save_message(
        session,
        Message(role="assistant", content=result.masked_answer or result.reply),
    )

    # 转人工任务落库
    if result.handoff:
        await store.save_handoff(session, reason=masked_content)

    # 回复买家（发送恢复后的真实文本）
    await adapter.send_message(shop_id, buyer_id, result.reply)

    log.info(
        f"webhook.{platform}.handled",
        session_id=session.session_id,
        buyer_id=buyer_id,
        handoff=result.handoff,
        tools=result.tool_calls_made,
    )

    return {"ok": True, "reply": result.reply, "handoff": result.handoff}


@router.post("/doudian")
async def doudian_webhook(request: Request) -> JSONResponse:
    """抖店消息推送回调。

    抖店开放平台推送买家消息到本接口，格式参见 adapter.parse_incoming。
    验签失败返回 403。
    """
    payload: dict[str, Any] = await request.json()

    adapter = get_adapter()
    try:
        msg = await adapter.parse_incoming(payload)
    except SignatureVerificationError as e:
        log.warning("webhook.doudian.sign_rejected", error=str(e))
        return JSONResponse(
            status_code=403,
            content={"ok": False, "error": "signature verification failed"},
        )

    result = await _handle_message(
        adapter=adapter,
        platform=msg.platform,
        buyer_id=msg.buyer_id,
        shop_id=msg.shop_id,
        content=msg.content,
    )
    return JSONResponse(result)


@router.post("/taobao")
async def taobao_webhook(request: Request) -> JSONResponse:
    """淘宝千牛消息推送回调（保留兼容）。"""
    payload: dict[str, Any] = await request.json()

    from apps.customer_service_agent.adapters.taobao.adapter import (
        get_adapter as get_taobao_adapter,
    )

    adapter = get_taobao_adapter()
    msg = await adapter.parse_incoming(payload)

    result = await _handle_message(
        adapter=adapter,
        platform=msg.platform,
        buyer_id=msg.buyer_id,
        shop_id=msg.shop_id,
        content=msg.content,
    )
    return JSONResponse(result)
