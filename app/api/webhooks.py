"""淘宝千牛 Webhook 入口。

POST /webhooks/taobao
- 一期：解析 payload → 入 Session → 走 AgentLoop → 回复消息
- 安全：通过 X-Taobao-Signature / webhook_secret 校验（TODO）
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.adapters.taobao.adapter import get_adapter
from app.agent.loop import AgentLoop
from app.agent.session import Session
from app.core.logging import get_logger
from app.llm.deepseek import get_llm
from app.retrieval.rag import RAGPipeline

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = get_logger(__name__)


@router.post("/taobao")
async def taobao_webhook(request: Request) -> JSONResponse:
    payload: dict[str, Any] = await request.json()

    adapter = get_adapter()
    msg = await adapter.parse_incoming(payload)

    session = Session(
        session_id=str(uuid.uuid4()),
        platform=msg.platform,
        buyer_id=msg.buyer_id,
        shop_id=msg.shop_id,
    )

    loop = AgentLoop(
        llm=get_llm(),
        adapter=adapter,
        rag=RAGPipeline(),
    )
    result = await loop.handle(session, msg.content)

    # 回复买家
    await adapter.send_message(msg.shop_id, msg.buyer_id, result.reply)

    log.info(
        "webhook.taobao.handled",
        session_id=session.session_id,
        handoff=result.handoff,
        tools=result.tool_calls_made,
    )

    return JSONResponse(
        {"ok": True, "reply": result.reply, "handoff": result.handoff}
    )
