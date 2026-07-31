"""AnswerEngine 单元测试。

验证：
1. get_answer_engine 不再是单例 — 每次创建新实例，注入参数生效
2. 脱敏/恢复流程 — 敏感信息不进入 LLM
3. JSON 结构化解析 — matched 判定可靠
4. 转人工关键词检测
5. answer_qa / answer_agent 核心流程（mock LLM + RAG）
6. masked_answer 字段 — 用于 DB 持久化的脱敏版回复
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.customer_service_agent.agent.answer_engine import (
    AnswerEngine,
    AnswerResult,
    get_answer_engine,
)
from apps.customer_service_agent.agent.session import Session
from knowledge_platform.knowledge_service.retriever.retriever import RetrievalHit
from knowledge_platform.knowledge_service.service import RAGContext, RAGPipeline
from runtime.llm.llm_provider import LLMProvider, LLMResponse, Message


# ===== Mock 工厂 =====


class MockLLM(LLMProvider):
    """可控的 LLM mock，返回预设响应。"""

    def __init__(self, response: LLMResponse | None = None) -> None:
        self._response = response or LLMResponse(
            content='{"answer": "测试回复", "matched": true}'
        )
        self.received_messages: list[list[Message]] = []
        self.call_count = 0

    async def chat(
        self,
        messages: list[Message],
        *,
        tools: Any = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        self.received_messages.append(messages)
        self.call_count += 1
        return self._response

    async def close(self) -> None:
        pass


class MockRAG(RAGPipeline):
    """可控的 RAG mock，返回预设检索结果。"""

    def __init__(self, hits: list[RetrievalHit] | None = None) -> None:
        self._hits = hits or []
        self.received_queries: list[str] = []

    async def retrieve(
        self,
        query: str,
        *,
        collections: list[str] | None = None,
        top_k: int = 20,
        top_n: int = 4,
    ) -> RAGContext:
        self.received_queries.append(query)
        return RAGContext(hits=self._hits, prompt_block="mock context")


def _make_hit(text: str = "发货时间为24小时内") -> RetrievalHit:
    return RetrievalHit(
        collection="kb_faq",
        id="hit_1",
        text=text,
        score=0.9,
        metadata={},
    )


# ===== 1. get_answer_engine 非单例测试 =====


class TestGetAnswerEngineNoSingleton:
    """验证 get_answer_engine 每次创建新实例。"""

    def test_creates_new_instance_each_call(self):
        """两次调用应返回不同实例。"""
        e1 = get_answer_engine()
        e2 = get_answer_engine()
        assert e1 is not e2

    def test_injected_llm_is_used(self):
        """注入的 mock LLM 应被使用，而非被忽略。"""
        mock_llm = MockLLM()
        engine = get_answer_engine(llm=mock_llm, rag=MockRAG())
        assert engine.llm is mock_llm

    def test_injected_rag_is_used(self):
        """注入的 mock RAG 应被使用。"""
        mock_rag = MockRAG()
        engine = get_answer_engine(llm=MockLLM(), rag=mock_rag)
        assert engine.rag is mock_rag

    def test_injected_adapter_is_used(self):
        """注入的 adapter 应被使用（之前单例会忽略第二次的 adapter）。"""
        adapter_a = MagicMock()
        adapter_b = MagicMock()
        e1 = get_answer_engine(llm=MockLLM(), rag=MockRAG(), adapter=adapter_a)
        e2 = get_answer_engine(llm=MockLLM(), rag=MockRAG(), adapter=adapter_b)
        assert e1.adapter is adapter_a
        assert e2.adapter is adapter_b
        assert e1.tool_executor is not e2.tool_executor

    def test_max_steps_injected_via_constructor(self):
        """max_steps 通过构造函数传入，不通过事后修改共享属性。"""
        e1 = get_answer_engine(llm=MockLLM(), rag=MockRAG(), max_steps=2)
        e2 = get_answer_engine(llm=MockLLM(), rag=MockRAG(), max_steps=8)
        assert e1.max_steps == 2
        assert e2.max_steps == 8
        # 修改 e1 不影响 e2
        e1.max_steps = 99
        assert e2.max_steps == 8


# ===== 2. 脱敏/恢复测试 =====


class TestMaskRestore:
    """验证 AnswerEngine 的 mask/restore 静态方法。"""

    def test_mask_phone(self):
        masked, masker = AnswerEngine.mask("我的手机号是 13812345678")
        assert "13812345678" not in masked
        assert "138****5678" in masked

    def test_restore_phone(self):
        masked, masker = AnswerEngine.mask("我的手机号是 13812345678")
        restored = AnswerEngine.restore(masker, "您的手机号 138****5678 已验证")
        assert "13812345678" in restored

    def test_mask_order_id(self):
        masked, masker = AnswerEngine.mask("订单号 1234567890123456")
        assert "1234567890123456" not in masked
        assert "1234****3456" in masked

    def test_mask_creates_new_masker_each_call(self):
        """每次 mask 创建新 Masker，避免映射表跨请求污染。"""
        m1, masker1 = AnswerEngine.mask("手机 13812345678")
        m2, masker2 = AnswerEngine.mask("手机 13987654321")
        assert masker1 is not masker2
        # masker1 不能 restore masker2 的占位符
        assert masker1.restore("139****4321") == "139****4321"


# ===== 3. JSON 解析测试 =====


class TestParseJsonResponse:
    """验证 LLM 回复的 JSON 结构化解析。"""

    def test_valid_json_matched_true(self):
        raw = '{"answer": "24小时内发货", "matched": true}'
        answer, matched = AnswerEngine.parse_json_response(raw)
        assert answer == "24小时内发货"
        assert matched is True

    def test_valid_json_matched_false(self):
        raw = '{"answer": "无法回答", "matched": false}'
        answer, matched = AnswerEngine.parse_json_response(raw)
        assert answer == "无法回答"
        assert matched is False

    def test_invalid_json_fallback(self):
        """非 JSON 回退到字符串启发式。"""
        raw = "这是一个纯文本回复，包含无法回答"
        answer, matched = AnswerEngine.parse_json_response(raw)
        assert answer == raw
        assert matched is False  # 包含"无法回答"

    def test_empty_json_answer(self):
        """answer 为空时回退。"""
        raw = '{"answer": "", "matched": true}'
        answer, matched = AnswerEngine.parse_json_response(raw)
        # answer 为空，回退到原始文本
        assert "无法回答" not in answer
        assert matched is True

    def test_json_with_extra_fields(self):
        raw = '{"answer": "你好", "matched": true, "extra": "ignored"}'
        answer, matched = AnswerEngine.parse_json_response(raw)
        assert answer == "你好"
        assert matched is True


# ===== 4. 转人工关键词检测 =====


class TestHumanKeywords:
    """验证转人工关键词命中检测。"""

    def test_keyword_hit(self):
        assert AnswerEngine.check_human_keywords("我要转人工") is True

    def test_keyword_complaint(self):
        assert AnswerEngine.check_human_keywords("我要投诉你们") is True

    def test_no_keyword(self):
        assert AnswerEngine.check_human_keywords("发货时间是多久") is False

    def test_empty_string(self):
        assert AnswerEngine.check_human_keywords("") is False


# ===== 5. answer_qa 测试 =====


class TestAnswerQa:
    """验证简单问答流程。"""

    @pytest.mark.asyncio
    async def test_empty_question(self):
        engine = AnswerEngine(llm=MockLLM(), rag=MockRAG())
        result = await engine.answer_qa("")
        assert result.matched is False
        assert "请描述" in result.answer

    @pytest.mark.asyncio
    async def test_no_rag_hits(self):
        """RAG 无命中时返回转人工。"""
        rag = MockRAG(hits=[])
        engine = AnswerEngine(llm=MockLLM(), rag=rag)
        result = await engine.answer_qa("不相关的问题")
        assert result.matched is False
        assert "转人工" in result.answer

    @pytest.mark.asyncio
    async def test_masking_before_rag(self):
        """用户输入在送入 RAG 前应已脱敏。"""
        rag = MockRAG(hits=[_make_hit()])
        engine = AnswerEngine(llm=MockLLM(), rag=rag)
        await engine.answer_qa("我的手机号是 13812345678，什么时候发货？")
        # RAG 收到的 query 不应包含明文手机号
        assert len(rag.received_queries) == 1
        assert "13812345678" not in rag.received_queries[0]
        assert "138****5678" in rag.received_queries[0]

    @pytest.mark.asyncio
    async def test_masking_before_llm(self):
        """用户输入在送入 LLM 前应已脱敏。"""
        llm = MockLLM(
            response=LLMResponse(
                content='{"answer": "24小时内发货", "matched": true}'
            )
        )
        engine = AnswerEngine(llm=llm, rag=MockRAG(hits=[_make_hit()]))
        await engine.answer_qa("我的手机号是 13812345678，什么时候发货？")
        # LLM 收到的 messages 不应包含明文手机号
        user_msg_content = llm.received_messages[0][-1].content
        assert "13812345678" not in user_msg_content
        assert "138****5678" in user_msg_content

    @pytest.mark.asyncio
    async def test_restore_in_answer(self):
        """回复中的占位符应被恢复为真实值。"""
        llm = MockLLM(
            response=LLMResponse(
                content='{"answer": "您的手机号 138****5678 已验证", "matched": true}'
            )
        )
        engine = AnswerEngine(llm=llm, rag=MockRAG(hits=[_make_hit()]))
        result = await engine.answer_qa("我的手机号是 13812345678")
        assert "13812345678" in result.answer
        assert "138****5678" not in result.answer


# ===== 6. answer_agent 测试 =====


class TestAnswerAgent:
    """验证 Agent 模式流程。"""

    @pytest.mark.asyncio
    async def test_human_keyword_triggers_handoff(self):
        """命中转人工关键词时直接返回 handoff。"""
        engine = AnswerEngine(llm=MockLLM(), rag=MockRAG())
        session = Session("s1", "doudian", "b1", "shop1")
        result = await engine.answer_agent(session, "我要转人工")
        assert result.handoff is True
        assert "转接人工" in result.answer

    @pytest.mark.asyncio
    async def test_masked_answer_set_on_response(self):
        """正常回复时 masked_answer 应包含占位符（未恢复）。"""
        llm = MockLLM(
            response=LLMResponse(
                content='{"answer": "您的订单 1234****3456 已发货", "matched": true}'
            )
        )
        # answer_agent 不要求 JSON 格式，直接返回 content
        llm._response = LLMResponse(content="您的订单 1234****3456 已发货")
        engine = AnswerEngine(llm=llm, rag=MockRAG(hits=[_make_hit()]))
        session = Session("s1", "doudian", "b1", "shop1")
        result = await engine.answer_agent(session, "订单 1234567890123456 到哪了")
        # answer 已恢复
        assert "1234567890123456" in result.answer
        # masked_answer 保留占位符
        assert "1234****3456" in result.masked_answer
        assert "1234567890123456" not in result.masked_answer

    @pytest.mark.asyncio
    async def test_session_stores_masked_text(self):
        """session.messages 中存储的应是脱敏后的文本。"""
        llm = MockLLM(response=LLMResponse(content="已发货"))
        engine = AnswerEngine(llm=llm, rag=MockRAG(hits=[_make_hit()]))
        session = Session("s1", "doudian", "b1", "shop1")
        await engine.answer_agent(session, "我的手机号是 13812345678")
        # session 中第一条 user 消息应已脱敏
        user_msgs = [m for m in session.messages if m.role == "user"]
        assert len(user_msgs) == 1
        assert "13812345678" not in user_msgs[0].content
        assert "138****5678" in user_msgs[0].content

    @pytest.mark.asyncio
    async def test_handoff_returns_masked_answer(self):
        """转人工时 masked_answer 与 answer 相同（无敏感信息）。"""
        llm = MockLLM(
            response=LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "function": {
                            "name": "handoff_human",
                            "arguments": '{"reason": "用户投诉"}',
                        },
                    }
                ],
            )
        )
        engine = AnswerEngine(llm=llm, rag=MockRAG(hits=[_make_hit()]))
        session = Session("s1", "doudian", "b1", "shop1")
        result = await engine.answer_agent(session, "正常问题")
        assert result.handoff is True
        assert result.masked_answer == result.answer
