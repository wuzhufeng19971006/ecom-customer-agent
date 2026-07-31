"""Webhook 签名验证安全测试。

验证：
1. 验签失败返回 403 — 不继续处理消息
2. 缺少签名字段返回 403
3. 签名为空字符串返回 403
4. 正确签名通过验证（mock 下游）
5. parse_incoming 对无效签名抛出 SignatureVerificationError
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from apps.customer_service_agent.adapters.doudian.adapter import (
    DoudianAdapter,
    SignatureVerificationError,
)


# ===== 辅助函数 =====


def _make_valid_sign(app_secret: str, msg: str, timestamp: str) -> str:
    """计算正确的推送签名。"""
    raw = f"{app_secret}msg{msg}timestamp{timestamp}{app_secret}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _make_payload(
    *,
    msg: str = '{"content":"你好","from_user_id":"b1","shop_id":"s1"}',
    timestamp: str = "1700000000",
    sign: str = "",
) -> dict[str, Any]:
    """构造抖店推送 payload。"""
    return {
        "tag": "im_message",
        "msg_id": "msg_test",
        "app_id": "app_001",
        "msg": msg,
        "timestamp": timestamp,
        "sign": sign,
    }


def _make_adapter_with_secret(secret: str = "test_secret_123") -> DoudianAdapter:
    """创建带 app_secret 的 adapter（跳过 __init__ 的 settings 依赖）。"""
    adapter = DoudianAdapter.__new__(DoudianAdapter)
    adapter.app_key = "test_key"
    adapter.app_secret = secret
    adapter.shop_id = "shop1"
    adapter.access_token = "token"
    adapter.api_base = "https://api.example.com"
    adapter.webhook_secret = ""
    adapter._http_client = MagicMock()
    return adapter


# ===== 1. parse_incoming 签名验证 =====


class TestParseIncomingSignature:
    """验证 adapter.parse_incoming 的签名校验逻辑。"""

    @pytest.mark.asyncio
    async def test_invalid_signature_raises(self):
        """错误签名应抛 SignatureVerificationError。"""
        adapter = _make_adapter_with_secret("my_secret")
        payload = _make_payload(sign="wrong_sign_abc")

        with pytest.raises(SignatureVerificationError, match="signature mismatch"):
            await adapter.parse_incoming(payload)

    @pytest.mark.asyncio
    async def test_missing_signature_raises(self):
        """缺少 sign 字段应抛 SignatureVerificationError。"""
        adapter = _make_adapter_with_secret("my_secret")
        payload = _make_payload()
        payload["sign"] = ""

        with pytest.raises(SignatureVerificationError, match="missing sign"):
            await adapter.parse_incoming(payload)

    @pytest.mark.asyncio
    async def test_no_sign_field_raises(self):
        """payload 中完全没有 sign 字段应抛 SignatureVerificationError。"""
        adapter = _make_adapter_with_secret("my_secret")
        payload = _make_payload()
        del payload["sign"]

        with pytest.raises(SignatureVerificationError):
            await adapter.parse_incoming(payload)

    @pytest.mark.asyncio
    async def test_valid_signature_passes(self):
        """正确签名应通过验证，返回 IncomingMessage。"""
        secret = "my_secret"
        msg = '{"content":"你好","from_user_id":"b1","shop_id":"s1"}'
        timestamp = "1700000000"
        sign = _make_valid_sign(secret, msg, timestamp)

        adapter = _make_adapter_with_secret(secret)
        payload = _make_payload(msg=msg, timestamp=timestamp, sign=sign)

        result = await adapter.parse_incoming(payload)
        assert result.platform == "doudian"
        assert result.buyer_id == "b1"
        assert result.content == "你好"

    @pytest.mark.asyncio
    async def test_empty_secret_skips_verification(self):
        """app_secret 为空时跳过验签（开发模式）。"""
        adapter = _make_adapter_with_secret("")
        payload = _make_payload(sign="")

        # 不应抛异常
        result = await adapter.parse_incoming(payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_tampered_msg_invalidates_sign(self):
        """篡改 msg 内容后签名不再匹配。"""
        secret = "my_secret"
        msg = '{"content":"原价100","from_user_id":"b1","shop_id":"s1"}'
        timestamp = "1700000000"
        sign = _make_valid_sign(secret, msg, timestamp)

        adapter = _make_adapter_with_secret(secret)
        # 篡改内容
        tampered_msg = '{"content":"原价1","from_user_id":"b1","shop_id":"s1"}'
        payload = _make_payload(msg=tampered_msg, timestamp=timestamp, sign=sign)

        with pytest.raises(SignatureVerificationError):
            await adapter.parse_incoming(payload)

    @pytest.mark.asyncio
    async def test_tampered_timestamp_invalidates_sign(self):
        """篡改 timestamp 后签名不再匹配。"""
        secret = "my_secret"
        msg = '{"content":"你好","from_user_id":"b1","shop_id":"s1"}'
        timestamp = "1700000000"
        sign = _make_valid_sign(secret, msg, timestamp)

        adapter = _make_adapter_with_secret(secret)
        payload = _make_payload(msg=msg, timestamp="1700000001", sign=sign)

        with pytest.raises(SignatureVerificationError):
            await adapter.parse_incoming(payload)


# ===== 2. Webhook 端点 403 响应 =====


class TestWebhook403Response:
    """验证 webhook 端点在验签失败时返回 403。"""

    @pytest.mark.asyncio
    async def test_invalid_signature_returns_403(self):
        """无效签名 → HTTP 403。"""
        from apps.customer_service_agent.api.webhooks import router

        app = FastAPI()
        app.include_router(router)

        adapter = _make_adapter_with_secret("my_secret")

        with patch(
            "apps.customer_service_agent.api.webhooks.get_adapter",
            return_value=adapter,
        ):
            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/webhooks/doudian",
                    json=_make_payload(sign="invalid"),
                )
                assert resp.status_code == 403
                body = resp.json()
                assert body["ok"] is False
                assert "signature" in body["error"]

    @pytest.mark.asyncio
    async def test_missing_signature_returns_403(self):
        """缺少签名 → HTTP 403。"""
        from apps.customer_service_agent.api.webhooks import router

        app = FastAPI()
        app.include_router(router)

        adapter = _make_adapter_with_secret("my_secret")

        with patch(
            "apps.customer_service_agent.api.webhooks.get_adapter",
            return_value=adapter,
        ):
            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                payload = _make_payload()
                payload["sign"] = ""
                resp = await client.post("/webhooks/doudian", json=payload)
                assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_valid_signature_not_403(self):
        """正确签名不应返回 403（mock 下游，走真实 AgentLoop 链路）。"""
        from apps.customer_service_agent.api.webhooks import router
        from apps.customer_service_agent.agent.session import Session
        from knowledge_platform.knowledge_service.service import RAGContext
        from runtime.llm.llm_provider import LLMResponse

        app = FastAPI()
        app.include_router(router)

        secret = "my_secret"
        msg_content = '{"content":"你好","from_user_id":"b1","shop_id":"s1"}'
        timestamp = "1700000000"
        sign = _make_valid_sign(secret, msg_content, timestamp)

        adapter = _make_adapter_with_secret(secret)

        # mock 下游：LLM 直接返回最终回答，RAG 无命中
        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(
            return_value=LLMResponse(content="您好，请问有什么可以帮您？")
        )
        mock_rag = MagicMock()
        mock_rag.retrieve = AsyncMock(return_value=RAGContext(hits=[], prompt_block=""))
        adapter.send_message = AsyncMock(return_value="ok")

        with (
            patch(
                "apps.customer_service_agent.api.webhooks.get_adapter",
                return_value=adapter,
            ),
            patch(
                "apps.customer_service_agent.api.webhooks.get_llm",
                return_value=mock_llm,
            ),
            patch(
                "apps.customer_service_agent.api.webhooks._get_rag",
                return_value=mock_rag,
            ),
            patch(
                "apps.customer_service_agent.api.webhooks.get_session_store"
            ) as mock_store_fn,
        ):
            mock_store = AsyncMock()
            mock_store.get_or_create = AsyncMock(
                return_value=Session(
                    session_id="s1",
                    platform="doudian",
                    buyer_id="b1",
                    shop_id="s1",
                )
            )
            mock_store.save_message = AsyncMock()
            mock_store.save_handoff = AsyncMock()
            mock_store_fn.return_value = mock_store

            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/webhooks/doudian",
                    json=_make_payload(
                        msg=msg_content, timestamp=timestamp, sign=sign
                    ),
                )
                assert resp.status_code == 200
                body = resp.json()
                assert body["ok"] is True
                assert body["reply"] == "您好，请问有什么可以帮您？"

            # 真实 AgentLoop 链路应完成：用户消息 + 助手回复各落库一次
            assert mock_store.save_message.await_count == 2

    @pytest.mark.asyncio
    async def test_403_does_not_call_agent_loop(self):
        """验签失败时不应调用 AgentLoop（不烧 token）。"""
        from apps.customer_service_agent.api.webhooks import router

        app = FastAPI()
        app.include_router(router)

        adapter = _make_adapter_with_secret("my_secret")

        with (
            patch(
                "apps.customer_service_agent.api.webhooks.get_adapter",
                return_value=adapter,
            ),
            patch(
                "apps.customer_service_agent.api.webhooks.AgentLoop"
            ) as mock_loop_cls,
        ):
            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/webhooks/doudian",
                    json=_make_payload(sign="invalid"),
                )
                assert resp.status_code == 403
                # AgentLoop 不应被实例化
                mock_loop_cls.assert_not_called()
