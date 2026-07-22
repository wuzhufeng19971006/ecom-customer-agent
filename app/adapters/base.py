"""平台适配器抽象基类。

所有平台（淘宝/拼多多/抖店）必须实现以下能力：
- 收发消息
- 查询订单
- 查询物流
- 查询商品
- 申请售后（占位，一期不强制实现）

Agent 内核只依赖本抽象，不感知具体平台。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class IncomingMessage:
    """从平台收到的消息（统一格式）。"""

    platform: str            # "taobao" | "pdd" | "doudian"
    platform_msg_id: str
    shop_id: str
    buyer_id: str
    content: str
    received_at: datetime
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderInfo:
    order_id: str
    status: str
    total_amount: float
    sku_titles: list[str]
    created_at: datetime
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class LogisticsInfo:
    order_id: str
    company: str
    tracking_no: str
    status: str
    latest_event: str | None
    updated_at: datetime
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProductInfo:
    sku_id: str
    title: str
    price: float
    stock: int
    attributes: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


class PlatformAdapter(ABC):
    """平台适配器抽象。"""

    platform: str = ""

    @abstractmethod
    async def send_message(self, shop_id: str, buyer_id: str, text: str) -> str:
        """向买家回复消息，返回平台消息 ID。"""

    @abstractmethod
    async def parse_incoming(self, payload: dict[str, Any]) -> IncomingMessage:
        """把平台 webhook 原始 payload 解析为统一 IncomingMessage。"""

    @abstractmethod
    async def query_order(self, order_id: str) -> OrderInfo | None:
        """查询订单。"""

    @abstractmethod
    async def query_logistics(self, order_id: str) -> LogisticsInfo | None:
        """查询物流。"""

    @abstractmethod
    async def query_product(self, sku_id: str) -> ProductInfo | None:
        """查询商品。"""
