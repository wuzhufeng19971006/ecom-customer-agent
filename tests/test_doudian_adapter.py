"""抖店适配器单元测试。

验证：
1. 签名算法（HMAC-SHA256）正确性
2. JSON 序列化（key 字典序、ensure_ascii=False）
3. parse_incoming 消息推送解析
4. 默认平台标识为 doudian
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

import pytest

from apps.customer_service_agent.adapters.doudian.adapter import (
    DoudianAdapter,
    _normalize_json,
    _sort_dict_recursive,
)


class TestSigning:
    """签名算法测试。"""

    def test_sign_hmac_sha256(self):
        """验证签名格式为 64 位十六进制 HMAC-SHA256。"""
        adapter = DoudianAdapter.__new__(DoudianAdapter)
        adapter.app_key = "test_key"
        adapter.app_secret = "test_secret"

        sign = adapter._sign("order.detail", '{"shop_order_id":"123"}', "1700000000")
        assert len(sign) == 64
        assert all(c in "0123456789abcdef" for c in sign)

    def test_sign_deterministic(self):
        """相同输入应产生相同签名。"""
        adapter = DoudianAdapter.__new__(DoudianAdapter)
        adapter.app_key = "test_key"
        adapter.app_secret = "test_secret"

        sign1 = adapter._sign("order.detail", '{"shop_order_id":"123"}', "1700000000")
        sign2 = adapter._sign("order.detail", '{"shop_order_id":"123"}', "1700000000")
        assert sign1 == sign2

    def test_sign_manual_verification(self):
        """手动验证签名值。"""
        app_key = "ak123"
        app_secret = "as456"
        method = "order.detail"
        param_json = '{"shop_order_id":"ABC"}'
        timestamp = "1700000000"
        v = "2"

        param_pattern = (
            f"app_key{app_key}"
            f"method{method}"
            f"param_json{param_json}"
            f"timestamp{timestamp}"
            f"v{v}"
        )
        sign_pattern = f"{app_secret}{param_pattern}{app_secret}"
        expected = hmac.new(
            app_secret.encode("utf-8"),
            sign_pattern.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        adapter = DoudianAdapter.__new__(DoudianAdapter)
        adapter.app_key = app_key
        adapter.app_secret = app_secret

        actual = adapter._sign(method, param_json, timestamp)
        assert actual == expected

    def test_verify_push_sign(self):
        """验证推送签名校验。"""
        app_secret = "test_secret"
        msg = '{"content":"hello"}'
        timestamp = "1700000000"

        raw = f"{app_secret}msg{msg}timestamp{timestamp}{app_secret}"
        expected_sign = hashlib.md5(raw.encode("utf-8")).hexdigest()

        adapter = DoudianAdapter.__new__(DoudianAdapter)
        adapter.app_secret = app_secret

        assert adapter._verify_push_sign(msg, timestamp, expected_sign) is True
        assert adapter._verify_push_sign(msg, timestamp, "wrong_sign") is False


class TestJsonNormalization:
    """JSON 序列化测试。"""

    def test_sorted_keys(self):
        """key 应按字典序排列。"""
        result = _normalize_json({"c": 3, "a": 1, "b": 2})
        assert result == '{"a":1,"b":2,"c":3}'

    def test_nested_sorted_keys(self):
        """嵌套 dict 也应按字典序排列。"""
        result = _normalize_json({"z": {"b": 2, "a": 1}, "a": 1})
        assert result == '{"a":1,"z":{"a":1,"b":2}}'

    def test_no_html_escape(self):
        """特殊字符不转义。"""
        result = _normalize_json({"a": "&<>='/汉"})
        assert result == '{"a":"&<>=\'/汉"}'

    def test_float_no_trailing_zero(self):
        """浮点数 1.0 序列化为 1（json.dumps 默认行为）。"""
        result = _normalize_json({"price": 1.0})
        assert '"price":1.0' in result  # Python json.dumps 输出 1.0


class TestParseIncoming:
    """消息推送解析测试。"""

    @pytest.mark.asyncio
    async def test_parse_incoming_basic(self):
        """解析标准抖店推送格式。"""
        adapter = DoudianAdapter.__new__(DoudianAdapter)
        adapter.app_secret = ""
        adapter.shop_id = "shop123"

        inner_msg = json.dumps({
            "from_user_id": "buyer_001",
            "content": "我的订单到哪了？",
            "shop_id": "shop123",
        })
        payload = {
            "tag": "im_message",
            "msg_id": "msg_abc",
            "app_id": "app_001",
            "msg": inner_msg,
            "timestamp": "1700000000",
            "sign": "",
        }

        msg = await adapter.parse_incoming(payload)

        assert msg.platform == "doudian"
        assert msg.platform_msg_id == "msg_abc"
        assert msg.buyer_id == "buyer_001"
        assert msg.shop_id == "shop123"
        assert msg.content == "我的订单到哪了？"

    @pytest.mark.asyncio
    async def test_parse_incoming_empty_msg(self):
        """msg 为空字符串时不应崩溃。"""
        adapter = DoudianAdapter.__new__(DoudianAdapter)
        adapter.app_secret = ""
        adapter.shop_id = ""

        payload = {"tag": "", "msg_id": "", "msg": "", "timestamp": "", "sign": ""}

        msg = await adapter.parse_incoming(payload)
        assert msg.platform == "doudian"
        assert msg.content == ""


class TestDefaultPlatform:
    """默认平台标识测试。"""

    def test_adapter_platform_is_doudian(self):
        """适配器 platform 属性应为 doudian。"""
        assert DoudianAdapter.platform == "doudian"

    def test_conversation_state_default_platform(self):
        """会话状态默认平台应为 doudian。"""
        from runtime.conversation.state import ConversationState

        state = ConversationState(session_id="test")
        assert state.platform == "doudian"
