"""多模态改造后的冒烟测试。

只做导入与基本逻辑测试，不调真实 API。
"""

import pytest


def test_imports_multimodal():
    import runtime.llm.llm_provider  # noqa: F401
    import runtime.llm.providers.mimo  # noqa: F401
    import runtime.llm.providers.deepseek  # noqa: F401
    import runtime.llm.providers.embedding_dashscope  # noqa: F401
    import runtime.llm.providers.rerank_jina  # noqa: F401
    import runtime.multimodal.vision_service  # noqa: F401
    import runtime.multimodal.ocr_service  # noqa: F401
    import runtime.multimodal.image_analyzer  # noqa: F401
    import runtime.conversation.state  # noqa: F401
    import runtime.conversation.event  # noqa: F401
    import runtime.decision.decision_engine  # noqa: F401
    import runtime.conversation.session_manager  # noqa: F401
    import apps.customer_service_agent.agent.query_rewrite  # noqa: F401
    import apps.customer_service_agent.agent.qa  # noqa: F401
    import apps.customer_service_agent.api.qa_multimodal  # noqa: F401


def test_settings_multimodal():
    from common.config.config import settings

    assert settings.mimo_model == "mimo-v2.5"
    assert settings.mimo_api_base.endswith("/v1")
    assert 0.0 < settings.vision_confidence_threshold < 1.0
    assert settings.conversation_debounce_ms == 500


def test_message_supports_image():
    from runtime.llm.llm_provider import ImagePart, Message, TextPart

    # 纯文本消息
    m1 = Message(role="user", content="hi")
    assert not m1.has_image()

    # 多模态消息
    m2 = Message(
        role="user",
        content_parts=[TextPart(text="看这张图"), ImagePart(data=b"fake")],
    )
    assert m2.has_image()


def test_conversation_state():
    from runtime.conversation.state import (
        ConversationState,
        ConversationStatus,
        ExtractedContext,
        MessageItem,
    )

    s = ConversationState(session_id="test")
    assert s.status == ConversationStatus.COLLECTING
    assert not s.has_text()
    assert not s.has_image()

    s.messages.append(MessageItem(role="user", text="你好"))
    assert s.has_text()
    assert s.latest_text() == "你好"

    s.images.append(MessageItem(role="user", image_data=b"fake"))
    assert s.has_image()

    # 合并上下文
    ctx = ExtractedContext(
        vision_summary="page_type=order_detail",
        ocr_filtered=["订单号"],
        possible_intent=["查询订单"],
        confidence=0.9,
    )
    s.merge_context(ctx)
    assert s.extracted_context.confidence == 0.9
    assert "订单号" in s.extracted_context.ocr_filtered


def test_event_bus():
    import asyncio

    from runtime.conversation.event import Event, EventBus, EventType

    bus = EventBus()
    received = []

    async def handler(e: Event) -> None:
        received.append(e)

    bus.subscribe(EventType.TEXT_MESSAGE, handler)

    async def run() -> None:
        await bus.publish(Event(type=EventType.TEXT_MESSAGE, session_id="s1", payload={"text": "hi"}))

    asyncio.run(run())
    assert len(received) == 1
    assert received[0].type == EventType.TEXT_MESSAGE


def test_decision_engine():
    from datetime import datetime, timedelta, timezone

    from runtime.decision.decision_engine import Decision, DecisionEngine
    from runtime.conversation.state import (
        ConversationState,
        ConversationStatus,
        ExtractedContext,
        MessageItem,
    )

    engine = DecisionEngine(confidence_threshold=0.85, timeout_sec=30)
    state = ConversationState(session_id="t")

    # 纯文本 → ANSWER
    state.messages.append(MessageItem(role="user", text="你好"))
    assert engine.decide(state) == Decision.ANSWER

    # 清空，加图片 + 文本 → ANSWER
    state2 = ConversationState(session_id="t2")
    state2.messages.append(MessageItem(role="user", text="这张图"))
    state2.images.append(MessageItem(role="user", image_data=b"fake"))
    assert engine.decide(state2) == Decision.ANSWER

    # 仅图片 + 高置信度 → ANSWER
    state3 = ConversationState(session_id="t3")
    state3.images.append(MessageItem(role="user", image_data=b"fake"))
    state3.extracted_context = ExtractedContext(confidence=0.9)
    assert engine.decide(state3) == Decision.ANSWER

    # 仅图片 + 低置信度 + 未超时 → WAIT
    state4 = ConversationState(session_id="t4")
    state4.images.append(MessageItem(role="user", image_data=b"fake"))
    state4.extracted_context = ExtractedContext(confidence=0.5)
    state4.last_event_at = datetime.now(timezone.utc)
    assert engine.decide(state4) == Decision.WAIT

    # 仅图片 + 低置信度 + 超时 → BEST_EFFORT
    state5 = ConversationState(session_id="t5")
    state5.images.append(MessageItem(role="user", image_data=b"fake"))
    state5.extracted_context = ExtractedContext(confidence=0.5)
    state5.last_event_at = datetime.now(timezone.utc) - timedelta(seconds=60)
    assert engine.decide(state5) == Decision.BEST_EFFORT


def test_ocr_filter():
    from runtime.multimodal.ocr_service import OCRResult, filter_ocr_text
    from runtime.multimodal.vision_service import VisionContext

    ocr = OCRResult(
        full_text=["首页", "我的订单", "订单号: 12345", "退出登录"],
        blocks=[
            {"text": "首页", "category": "navigation"},
            {"text": "我的订单", "category": "menu"},
            {"text": "订单号: 12345", "category": "content"},
            {"text": "退出登录", "category": "button"},
        ],
    )
    vision = VisionContext(
        page_type="order_detail",
        focus_area="order_id",
        possible_intent=["查询订单状态"],
        confidence=0.8,
    )

    filtered = filter_ocr_text(ocr, vision)
    # 应保留 "订单号: 12345"（content 类），过滤掉导航/菜单/按钮
    assert "订单号: 12345" in filtered
    assert "首页" not in filtered
    assert "退出登录" not in filtered


def test_vision_context_prompt_block():
    from runtime.multimodal.vision_service import VisionContext

    ctx = VisionContext(
        page_type="order_detail",
        focus_area="payment_amount",
        possible_intent=["优惠未显示"],
        confidence=0.78,
    )
    block = ctx.to_prompt_block()
    assert "page_type=order_detail" in block
    assert "focus_area=payment_amount" in block
    assert "优惠未显示" in block
    assert "0.78" in block


def test_query_rewrite_fallback():
    from apps.customer_service_agent.agent.query_rewrite import QueryRewriteService

    svc = QueryRewriteService.__new__(QueryRewriteService)
    q = svc._fallback("为什么没显示", ["订单号", "支付金额", "首页"])
    # 降级路径：用户文本 + OCR 前 5 个关键词
    assert "为什么没显示" in q
    assert "订单号" in q
    assert "首页" in q  # fallback 不过滤噪声


def test_app_routes_registered():
    from apps.customer_service_agent.main import create_app

    app = create_app()
    schema = app.openapi()
    paths = set(schema.get("paths", {}).keys())
    # 多模态与文本答疑 + 淘宝 webhook 必须注册
    assert "/api/qa" in paths
    assert "/api/qa/multimodal" in paths
    assert "/webhooks/taobao" in paths
