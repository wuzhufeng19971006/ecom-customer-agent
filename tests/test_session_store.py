"""SessionStore 单元测试。

验证：
1. _ensure_aware_utc — naive datetime 补 tzinfo=UTC（时区 TypeError 根因）
2. LRU 缓存淘汰 — 超过 CACHE_MAX 时淘汰最久未访问
3. get_or_create — 新建会话并持久化
4. save_message — 消息持久化到 DB
5. save_handoff — 转人工任务落库
6. _restore_from_db — 从 DB 恢复会话（含时区处理）
7. TTL 超时 — 过期会话不恢复
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.customer_service_agent.agent.session import Session
from apps.customer_service_agent.agent.session_store import (
    CACHE_MAX,
    SESSION_TTL,
    SessionStore,
    _ensure_aware_utc,
)
from common.database.database import Base, HandoffTask, MessageRow, SessionRow
from runtime.llm.llm_provider import Message


# ===== 测试夹具 =====


@pytest.fixture
async def store_with_db():
    """创建使用内存 SQLite 的 SessionStore。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    store = SessionStore()
    store._engine = engine
    store._session_maker = async_sessionmaker(engine, expire_on_commit=False)

    yield store

    await engine.dispose()


# ===== 1. _ensure_aware_utc 测试 =====


class TestEnsureAwareUtc:
    """验证时区修复函数。"""

    def test_naive_datetime_gets_utc(self):
        """naive datetime（tzinfo=None）应补上 UTC。"""
        naive = datetime(2024, 1, 1, 12, 0, 0)
        aware = _ensure_aware_utc(naive)
        assert aware.tzinfo is not None
        assert aware.utcoffset() == timedelta(0)

    def test_aware_datetime_unchanged(self):
        """已有 tzinfo 的 datetime 不应被修改。"""
        aware = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = _ensure_aware_utc(aware)
        assert result is aware

    def test_aware_non_utc_preserved(self):
        """非 UTC 时区的 datetime 保持不变（不强制转 UTC）。"""
        from datetime import timezone as tz

        cst = tz(timedelta(hours=8))
        aware_cst = datetime(2024, 1, 1, 12, 0, 0, tzinfo=cst)
        result = _ensure_aware_utc(aware_cst)
        assert result is aware_cst
        assert result.utcoffset() == timedelta(hours=8)

    def test_subtraction_no_typeerror(self):
        """修复后 aware - aware 不再抛 TypeError（原始 bug 场景）。"""
        naive = datetime(2024, 1, 1, 12, 0, 0)
        fixed = _ensure_aware_utc(naive)
        now = datetime.now(timezone.utc)
        # 这行在修复前会抛 TypeError
        diff = now - fixed
        assert isinstance(diff, timedelta)


# ===== 2. LRU 缓存淘汰测试 =====


class TestLRUEviction:
    """验证 LRU 缓存淘汰机制。"""

    def test_cache_evicts_when_full(self):
        """超过 CACHE_MAX 时应淘汰最久未访问的会话。"""
        store = SessionStore()
        for i in range(CACHE_MAX + 10):
            session = Session(
                session_id=f"sess_{i}",
                platform="doudian",
                buyer_id=f"buyer_{i}",
                shop_id="shop1",
            )
            store._cache[session.buyer_id] = session
            store._evict_if_needed()

        assert len(store._cache) <= CACHE_MAX
        # 最旧的应被淘汰
        assert "buyer_0" not in store._cache
        # 最新的应保留
        assert f"buyer_{CACHE_MAX + 9}" in store._cache

    def test_lru_order_on_access(self):
        """访问会话时应移到末尾（最近使用）。"""
        store = SessionStore()
        for i in range(3):
            session = Session(
                session_id=f"sess_{i}",
                platform="doudian",
                buyer_id=f"buyer_{i}",
                shop_id="shop1",
            )
            store._cache[session.buyer_id] = session

        # 访问 buyer_0（最旧的）
        store._cache.move_to_end("buyer_0")
        # buyer_0 现在应该是最后访问的
        keys = list(store._cache.keys())
        assert keys[-1] == "buyer_0"


# ===== 3. get_or_create 测试 =====


class TestGetOrCreate:
    """验证会话创建与缓存。"""

    @pytest.mark.asyncio
    async def test_creates_new_session(self, store_with_db):
        """无历史记录时创建新会话。"""
        store = store_with_db
        session = await store.get_or_create(
            platform="doudian",
            buyer_id="buyer_new",
            shop_id="shop1",
        )
        assert session.buyer_id == "buyer_new"
        assert session.platform == "doudian"
        assert session.session_id  # 非空 UUID
        # 应在缓存中
        assert "buyer_new" in store._cache

    @pytest.mark.asyncio
    async def test_cache_hit_returns_same_session(self, store_with_db):
        """缓存命中时返回同一实例。"""
        store = store_with_db
        s1 = await store.get_or_create(
            platform="doudian", buyer_id="b1", shop_id="shop1"
        )
        s2 = await store.get_or_create(
            platform="doudian", buyer_id="b1", shop_id="shop1"
        )
        assert s1 is s2

    @pytest.mark.asyncio
    async def test_different_buyers_different_sessions(self, store_with_db):
        """不同买家获得不同会话。"""
        store = store_with_db
        s1 = await store.get_or_create(
            platform="doudian", buyer_id="b1", shop_id="shop1"
        )
        s2 = await store.get_or_create(
            platform="doudian", buyer_id="b2", shop_id="shop1"
        )
        assert s1.session_id != s2.session_id
        assert s1.buyer_id != s2.buyer_id


# ===== 4. save_message 测试 =====


class TestSaveMessage:
    """验证消息持久化。"""

    @pytest.mark.asyncio
    async def test_save_user_message(self, store_with_db):
        """user 消息应写入 DB。"""
        store = store_with_db
        session = await store.get_or_create(
            platform="doudian", buyer_id="b1", shop_id="shop1"
        )
        await store.save_message(
            session, Message(role="user", content="我的手机号是 138****5678")
        )

        async with store._session_maker() as db:
            result = await db.execute(
                select(MessageRow).where(MessageRow.session_id == session.session_id)
            )
            rows = result.scalars().all()
            assert len(rows) == 1
            assert rows[0].role == "user"
            assert "138****5678" in rows[0].content
            # DB 中不应有明文
            assert "13812345678" not in rows[0].content

    @pytest.mark.asyncio
    async def test_save_assistant_message(self, store_with_db):
        """assistant 消息应写入 DB。"""
        store = store_with_db
        session = await store.get_or_create(
            platform="doudian", buyer_id="b1", shop_id="shop1"
        )
        await store.save_message(
            session, Message(role="assistant", content="已为您查询")
        )

        async with store._session_maker() as db:
            result = await db.execute(
                select(MessageRow).where(MessageRow.session_id == session.session_id)
            )
            rows = result.scalars().all()
            assert len(rows) == 1
            assert rows[0].role == "assistant"

    @pytest.mark.asyncio
    async def test_tool_message_not_persisted(self, store_with_db):
        """tool 角色消息不应持久化。"""
        store = store_with_db
        session = await store.get_or_create(
            platform="doudian", buyer_id="b1", shop_id="shop1"
        )
        await store.save_message(
            session, Message(role="tool", content="tool result")
        )

        async with store._session_maker() as db:
            result = await db.execute(
                select(MessageRow).where(MessageRow.session_id == session.session_id)
            )
            rows = result.scalars().all()
            assert len(rows) == 0


# ===== 5. save_handoff 测试 =====


class TestSaveHandoff:
    """验证转人工任务落库。"""

    @pytest.mark.asyncio
    async def test_handoff_persisted(self, store_with_db):
        """转人工任务应写入 HandoffTask 表。"""
        store = store_with_db
        session = await store.get_or_create(
            platform="doudian", buyer_id="b1", shop_id="shop1"
        )
        await store.save_handoff(session, reason="用户请求转人工")

        async with store._session_maker() as db:
            result = await db.execute(
                select(HandoffTask).where(HandoffTask.session_id == session.session_id)
            )
            rows = result.scalars().all()
            assert len(rows) == 1
            assert rows[0].buyer_id == "b1"
            assert rows[0].platform == "doudian"
            assert rows[0].reason == "用户请求转人工"
            assert rows[0].status == "pending"

    @pytest.mark.asyncio
    async def test_multiple_handoffs(self, store_with_db):
        """多次转人工应各自独立落库。"""
        store = store_with_db
        session = await store.get_or_create(
            platform="doudian", buyer_id="b1", shop_id="shop1"
        )
        await store.save_handoff(session, reason="第一次")
        await store.save_handoff(session, reason="第二次")

        async with store._session_maker() as db:
            result = await db.execute(
                select(HandoffTask).where(HandoffTask.session_id == session.session_id)
            )
            rows = result.scalars().all()
            assert len(rows) == 2


# ===== 6. _restore_from_db 测试 =====


class TestRestoreFromDb:
    """验证从 DB 恢复会话（含时区处理）。"""

    @pytest.mark.asyncio
    async def test_restore_session_with_messages(self, store_with_db):
        """恢复会话时应加载历史消息。"""
        store = store_with_db
        # 先创建并保存消息
        session = await store.get_or_create(
            platform="doudian", buyer_id="b1", shop_id="shop1"
        )
        await store.save_message(session, Message(role="user", content="你好"))
        await store.save_message(
            session, Message(role="assistant", content="您好，有什么可以帮您？")
        )

        # 清除缓存，强制从 DB 恢复
        store.invalidate("b1")
        restored = await store.get_or_create(
            platform="doudian", buyer_id="b1", shop_id="shop1"
        )

        assert restored.session_id == session.session_id
        user_msgs = [m for m in restored.messages if m.role == "user"]
        assistant_msgs = [m for m in restored.messages if m.role == "assistant"]
        assert len(user_msgs) == 1
        assert user_msgs[0].content == "你好"
        assert len(assistant_msgs) == 1
        assert "有什么可以帮您" in assistant_msgs[0].content

    @pytest.mark.asyncio
    async def test_restore_does_not_crash_on_timezone(self, store_with_db):
        """从 DB 恢复时不应抛 TypeError（原始 bug 场景）。"""
        store = store_with_db
        session = await store.get_or_create(
            platform="doudian", buyer_id="b1", shop_id="shop1"
        )
        await store.save_message(session, Message(role="user", content="测试"))

        # 清除缓存，触发 DB 恢复
        store.invalidate("b1")
        # 这行在修复前会抛 TypeError
        restored = await store.get_or_create(
            platform="doudian", buyer_id="b1", shop_id="shop1"
        )
        assert restored is not None
        # 恢复后的时间应为 aware UTC
        assert restored.updated_at.tzinfo is not None

    @pytest.mark.asyncio
    async def test_restore_expired_session_returns_none(self, store_with_db):
        """过期会话不应被恢复。"""
        store = store_with_db
        session = await store.get_or_create(
            platform="doudian", buyer_id="b1", shop_id="shop1"
        )

        # 手动将 DB 中的 updated_at 设为过期
        async with store._session_maker() as db:
            from sqlalchemy import update

            expired_time = datetime.now(timezone.utc) - timedelta(seconds=SESSION_TTL + 1)
            await db.execute(
                update(SessionRow)
                .where(SessionRow.id == session.session_id)
                .values(updated_at=expired_time)
            )
            await db.commit()

        # 清除缓存，尝试恢复
        store.invalidate("b1")
        restored = await store.get_or_create(
            platform="doudian", buyer_id="b1", shop_id="shop1"
        )
        # 应创建新会话而非恢复旧的
        assert restored.session_id != session.session_id

    @pytest.mark.asyncio
    async def test_cache_hit_with_naive_updated_at(self, store_with_db):
        """缓存命中路径也不应因 naive datetime 崩溃。"""
        store = store_with_db
        session = await store.get_or_create(
            platform="doudian", buyer_id="b1", shop_id="shop1"
        )

        # 模拟 DB 读出的 naive datetime 赋给 session
        session.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        # 缓存命中路径应正常工作
        result = await store.get_or_create(
            platform="doudian", buyer_id="b1", shop_id="shop1"
        )
        assert result is not None
