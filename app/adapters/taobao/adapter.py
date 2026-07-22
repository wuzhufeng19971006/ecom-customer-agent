"""淘宝适配器占位实现。

一期范围：
- parse_incoming: 解析千牛 webhook 回调 → IncomingMessage
- send_message: 调用千牛消息接口回复买家
- query_order / query_logistics / query_product: 调用淘宝开放平台 SDK

NOTE: 真实接入需注册淘宝开放平台应用、签名 top 请求、签名鉴权。
当前仅提供结构与签名占位，便于 Agent 内核先行联调。
后续在 `_call_top` 中接入 tianmao-sdk / 官方签名实现。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.adapters.base import (
    IncomingMessage,
    LogisticsInfo,
    OrderInfo,
    PlatformAdapter,
    ProductInfo,
)
from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


class TaobaoAdapter(PlatformAdapter):
    platform = "taobao"

    def __init__(self) -> None:
        self.app_key = settings.taobao_app_key
        self.app_secret = settings.taobao_app_secret
        self.session_key = settings.taobao_session_key
        self.api_base = settings.taobao_api_base

    async def send_message(self, shop_id: str, buyer_id: str, text: str) -> str:
        """调用淘宝开放平台 mtop.message.send（占位）。"""
        # TODO: 接入 tianmao-sdk，组装 sign 调用
        log.info(
            "taobao.send_message",
            shop_id=shop_id,
            buyer_id=buyer_id,
            text_len=len(text),
        )
        return ""  # 返回平台消息 ID

    async def parse_incoming(self, payload: dict[str, Any]) -> IncomingMessage:
        """解析千牛 webhook 回调 payload（结构按实际回调字段对齐）。"""
        return IncomingMessage(
            platform="taobao",
            platform_msg_id=str(payload.get("msg_id", "")),
            shop_id=str(payload.get("seller_id", "")),
            buyer_id=str(payload.get("buyer_id", "")),
            content=str(payload.get("content", "")),
            received_at=datetime.now(timezone.utc),
            raw=payload,
        )

    async def query_order(self, order_id: str) -> OrderInfo | None:
        """调用 taobao.trade.fullinfo.get（占位）。"""
        # TODO: 接入 SDK
        return None

    async def query_logistics(self, order_id: str) -> LogisticsInfo | None:
        """调用 taobao.logistics.trace.search（占位）。"""
        return None

    async def query_product(self, sku_id: str) -> ProductInfo | None:
        """调用 taobao.item.seller.get（占位）。"""
        return None

    async def _call_top(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """统一封装淘宝 TOP 请求签名 + 调用（待实现）。"""
        raise NotImplementedError("TOP 签名调用待接入")


_adapter: TaobaoAdapter | None = None


def get_adapter() -> TaobaoAdapter:
    global _adapter
    if _adapter is None:
        _adapter = TaobaoAdapter()
    return _adapter
