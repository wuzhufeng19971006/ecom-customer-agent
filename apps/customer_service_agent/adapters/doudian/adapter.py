"""抖店（抖音电商）开放平台适配器。

接入抖店开放平台（https://op.jinritemai.com/）：
- parse_incoming: 解析抖店消息推送回调 → IncomingMessage
- send_message: 调用 IM 消息接口回复买家
- query_order: 调用 order.detail 查询订单详情
- query_logistics: 调用 logistics.logisticsTrace 查询物流轨迹
- query_product: 调用 product.detail 查询商品详情

签名算法（HMAC-SHA256，推荐）：
1. 序列化 param_json（按 Key 字典序排列，数值不带多余小数点，禁用 HTML Escape）
2. 拼接: app_key{app_key}method{method}param_json{param_json}timestamp{timestamp}v{v}
3. 头尾拼接 app_secret: {app_secret}{上述拼接}{app_secret}
4. HMAC-SHA256(app_secret, 上述字符串)

参考文档:
- API 调用指南: https://op.jinritemai.com/docs/guide-docs/10/23
- API 列表: https://op.jinritemai.com/docs/api-docs/13
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from apps.customer_service_agent.adapters.base import (
    IncomingMessage,
    LogisticsInfo,
    OrderInfo,
    PlatformAdapter,
    ProductInfo,
)
from common.config.config import settings
from common.logger.logger import get_logger

log = get_logger(__name__)


class SignatureVerificationError(Exception):
    """推送签名校验失败。"""


def _sort_dict_recursive(obj: Any) -> Any:
    """递归地对 dict 按 key 字典序排列，保证 JSON 序列化后 key 有序。"""
    if isinstance(obj, dict):
        return {k: _sort_dict_recursive(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        return [_sort_dict_recursive(item) for item in obj]
    return obj


def _normalize_json(obj: Any) -> str:
    """序列化为满足抖店签名要求的 JSON 字符串。

    - 所有层级 key 按字典序排列
    - 数值不带多余小数点（1.0 → 1）
    - 禁用 HTML Escape（ensure_ascii=False, 不转义特殊字符）
    """
    sorted_obj = _sort_dict_recursive(obj)
    return json.dumps(sorted_obj, ensure_ascii=False, separators=(",", ":"))


class DoudianAdapter(PlatformAdapter):
    """抖店开放平台适配器。"""

    platform = "doudian"

    def __init__(self) -> None:
        self.app_key = settings.doudian_app_key
        self.app_secret = settings.doudian_app_secret
        self.shop_id = settings.doudian_shop_id
        self.access_token = settings.doudian_access_token
        self.api_base = settings.doudian_api_base
        self.webhook_secret = settings.doudian_webhook_secret
        # 复用 HTTP 连接，避免高频场景每次新建 client
        self._http_client = httpx.AsyncClient(timeout=10.0)

    # ===== 签名 =====

    def _sign(self, method: str, param_json: str, timestamp: str, v: str = "2") -> str:
        """计算 HMAC-SHA256 签名。

        拼接顺序: app_secret + app_key{app_key}method{method}param_json{param_json}timestamp{timestamp}v{v} + app_secret
        HMAC key: app_secret
        """
        param_pattern = (
            f"app_key{self.app_key}"
            f"method{method}"
            f"param_json{param_json}"
            f"timestamp{timestamp}"
            f"v{v}"
        )
        sign_pattern = f"{self.app_secret}{param_pattern}{self.app_secret}"
        signature = hmac.new(
            self.app_secret.encode("utf-8"),
            sign_pattern.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def _verify_push_sign(self, msg: str, timestamp: str, received_sign: str) -> bool:
        """验证消息推送签名。

        抖店推送签名: MD5(app_secret + "msg" + msg + "timestamp" + timestamp + app_secret)
        参考抖店消息推送文档。
        """
        raw = f"{self.app_secret}msg{msg}timestamp{timestamp}{self.app_secret}"
        expected = hashlib.md5(raw.encode("utf-8")).hexdigest()
        return hmac.compare_digest(expected, received_sign)

    # ===== 统一 API 调用 =====

    async def _call_doudian(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        """调用抖店开放平台 API。

        Args:
            method: API 方法名，如 "order.detail"
            params: 业务参数 dict
            timeout: HTTP 超时秒数

        Returns:
            API 响应 JSON（包含 err_no / message / data）
        """
        params = params or {}
        param_json = _normalize_json(params)
        timestamp = str(int(time.time()))

        sign = self._sign(method, param_json, timestamp)

        query_params = {
            "method": method,
            "app_key": self.app_key,
            "access_token": self.access_token,
            "timestamp": timestamp,
            "v": "2",
            "sign": sign,
            "sign_method": "hmac-sha256",
        }

        url = f"{self.api_base}/{method.replace('.', '/')}"
        url_with_params = f"{url}?{urlencode(query_params)}"

        log.info(
            "doudian.api_call",
            method=method,
            url=url,
        )

        resp = await self._http_client.post(
            url_with_params,
            content=param_json,
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        result = resp.json()

        if result.get("err_no", -1) != 0:
            log.warning(
                "doudian.api_error",
                method=method,
                err_no=result.get("err_no"),
                message=result.get("message", ""),
            )
        return result

    # ===== 消息收发 =====

    async def parse_incoming(self, payload: dict[str, Any]) -> IncomingMessage:
        """解析抖店消息推送回调 payload。

        抖店推送格式:
        {
            "tag": "im_message",           # 消息类型标签
            "msg_id": "xxx",               # 消息 ID
            "app_id": "12345",             # 应用 ID
            "msg": "{...}",                # 业务数据 JSON 字符串
            "timestamp": "1700000000",     # 时间戳
            "sign": "abc123"               # 签名
        }

        msg 内层 JSON（IM 消息）:
        {
            "from_user_id": "买家open_id",
            "to_user_id": "店铺 ID",
            "content": "买家发送的文本",
            "msg_type": "text",
            "shop_id": "店铺 ID"
        }
        """
        tag = str(payload.get("tag", ""))
        msg_id = str(payload.get("msg_id", ""))
        msg_raw = payload.get("msg", "")
        timestamp = str(payload.get("timestamp", ""))
        received_sign = str(payload.get("sign", ""))

        # 验签（如果配置了 app_secret 则必须校验）
        if self.app_secret:
            if not received_sign:
                raise SignatureVerificationError(
                    f"missing sign in payload, msg_id={msg_id}"
                )
            if not self._verify_push_sign(msg_raw, timestamp, received_sign):
                log.warning("doudian.push_sign_invalid", msg_id=msg_id)
                raise SignatureVerificationError(
                    f"signature mismatch, msg_id={msg_id}"
                )

        # 解析内层 msg
        try:
            msg_data = json.loads(msg_raw) if isinstance(msg_raw, str) else (msg_raw or {})
        except (json.JSONDecodeError, TypeError):
            msg_data = {}

        content = str(msg_data.get("content", ""))
        buyer_id = str(msg_data.get("from_user_id", ""))
        shop_id = str(msg_data.get("shop_id", self.shop_id))

        return IncomingMessage(
            platform="doudian",
            platform_msg_id=msg_id,
            shop_id=shop_id,
            buyer_id=buyer_id,
            content=content,
            received_at=datetime.now(timezone.utc),
            raw=payload,
        )

    async def send_message(self, shop_id: str, buyer_id: str, text: str) -> str:
        """调用抖店 IM 接口向买家回复消息。

        使用 im.sendMsg 接口（method: im.sendMsg）发送文本消息。
        """
        log.info(
            "doudian.send_message",
            shop_id=shop_id,
            buyer_id=buyer_id,
            text_len=len(text),
        )
        try:
            result = await self._call_doudian(
                "im.sendMsg",
                {
                    "shop_id": int(shop_id) if shop_id else int(self.shop_id),
                    "open_id": buyer_id,
                    "msg_type": "text",
                    "content": text,
                },
            )
            if result.get("err_no") == 0:
                return str(result.get("data", {}).get("msg_id", ""))
            log.warning("doudian.send_message_failed", message=result.get("message"))
        except Exception as e:  # noqa: BLE001
            log.error("doudian.send_message_error", error=str(e))
        return ""

    # ===== 业务查询 =====

    async def query_order(self, order_id: str) -> OrderInfo | None:
        """调用 order.detail 查询抖店订单详情。

        API: https://op.jinritemai.com/docs/api-docs/15/68
        method: order.detail
        """
        try:
            result = await self._call_doudian("order.detail", {"shop_order_id": order_id})
            if result.get("err_no") != 0:
                return None
            data = result.get("data", {})
            # 抖店订单详情返回结构
            order = data if isinstance(data, dict) else {}
            sub_orders = order.get("sub_orders", [])
            sku_titles = [so.get("product_name", "") for so in sub_orders] if sub_orders else []

            return OrderInfo(
                order_id=str(order.get("shop_order_id", order_id)),
                status=str(order.get("order_status", "")),
                total_amount=float(order.get("pay_amount", 0)) / 100,  # 抖店金额单位为分
                sku_titles=sku_titles,
                created_at=datetime.fromtimestamp(
                    int(order.get("created_time", 0)), tz=timezone.utc
                ) if order.get("created_time") else datetime.now(timezone.utc),
                raw=data,
            )
        except Exception as e:  # noqa: BLE001
            log.error("doudian.query_order_error", order_id=order_id, error=str(e))
            return None

    async def query_logistics(self, order_id: str) -> LogisticsInfo | None:
        """调用 logistics.logisticsTrace 查询物流轨迹。

        API: https://op.jinritemai.com/docs/api-docs/16/
        method: logistics.logisticsTrace
        """
        try:
            result = await self._call_doudian(
                "logistics.logisticsTrace",
                {"shop_order_id": order_id},
            )
            if result.get("err_no") != 0:
                return None
            data = result.get("data", {})
            traces = data if isinstance(data, list) else data.get("trace_list", [])
            latest = traces[-1] if traces else {}

            return LogisticsInfo(
                order_id=order_id,
                company=str(data.get("company", latest.get("company", ""))),
                tracking_no=str(data.get("tracking_no", latest.get("tracking_number", ""))),
                status=str(latest.get("desc", data.get("status", ""))),
                latest_event=str(latest.get("event", "")),
                updated_at=datetime.fromtimestamp(
                    int(latest.get("timestamp", 0)), tz=timezone.utc
                ) if latest.get("timestamp") else datetime.now(timezone.utc),
                raw=data,
            )
        except Exception as e:  # noqa: BLE001
            log.error("doudian.query_logistics_error", order_id=order_id, error=str(e))
            return None

    async def query_product(self, sku_id: str) -> ProductInfo | None:
        """调用 product.detail 查询抖店商品详情。

        API: https://op.jinritemai.com/docs/api-docs/14/56
        method: product.detail
        """
        try:
            result = await self._call_doudian("product.detail", {"product_id": int(sku_id)})
            if result.get("err_no") != 0:
                return None
            data = result.get("data", {})
            product = data if isinstance(data, dict) else {}

            return ProductInfo(
                sku_id=str(product.get("product_id", sku_id)),
                title=str(product.get("name", "")),
                price=float(product.get("market_price", 0)) / 100,  # 单位为分
                stock=int(product.get("stock_num", 0)),
                attributes={
                    k: v
                    for k, v in product.items()
                    if k in ("pic", "description", "category_leaf_id", "product_format")
                },
                raw=data,
            )
        except Exception as e:  # noqa: BLE001
            log.error("doudian.query_product_error", sku_id=sku_id, error=str(e))
            return None


_adapter: DoudianAdapter | None = None


def get_adapter() -> DoudianAdapter:
    global _adapter
    if _adapter is None:
        _adapter = DoudianAdapter()
    return _adapter
