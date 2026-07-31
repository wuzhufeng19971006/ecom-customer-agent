"""会话存储：按买家 ID 恢复多轮会话。

内存缓存 + DB 持久化：
- get_or_create: 按 buyer_id 查找已有会话，没有则创建
- save_message: 将单条消息持久化到 DB
- 服务重启后从 DB 恢复历史对话

安全设计：
- DB 中只存脱敏后文本，不落明文敏感信息
- 内存 session 与 DB 存储内容一致，重启恢复天然安全
- DB 读出的 naive datetime 统一补 tzinfo=UTC，避免时区 TypeError
"""

from __future__ import annotations

import uuid
from collections import OrderedDict
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.customer_service_agent.agent.session import Session
from common.config.config import settings
from common.database.database import HandoffTask, MessageRow, SessionRow
from common.logger.logger import get_logger
from runtime.llm.llm_provider import Message

log = get_logger(__name__)

# 会话空闲超时（秒）：超过后新建会话而非恢复旧会话
SESSION_TTL = 1800  # 30 分钟

# 内存缓存上限：超过后淘汰最久未访问的会话
CACHE_MAX = 500


def _ensure_aware_utc(dt: datetime) -> datetime:
    """确保 datetime 是 aware UTC。

    SQLite 不存储时区信息，读出的 datetime 是 naive（tzinfo=None）。
    补上 tzinfo=UTC 避免与 aware datetime 相减时抛 TypeError。
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SessionStore:
    """按 buyer_id 管理会话，内存缓存 + DB 持久化。"""

    def __init__(self) -> None:
        # key: buyer_id → Session（LRU 缓存，有上限）
        self._cache: OrderedDict[str, Session] = OrderedDict()
        self._engine = None
        self._session_maker: async_sessionmaker | None = None

    async def _ensure_db(self) -> None:
        """延迟初始化 DB 引擎，避免启动时连接。"""
        if self._engine is None:
            self._engine = create_async_engine(settings.database_url, echo=False)
            self._session_maker = async_sessionmaker(
                self._engine, expire_on_commit=False
            )

    async def get_or_create(
        self,
        *,
        platform: str,
        buyer_id: str,
        shop_id: str,
    ) -> Session:
        """按 buyer_id 获取或创建会话。

        优先从内存缓存获取；缓存未命中时尝试从 DB 恢复；
        DB 也无记录（或已超时）时创建新会话并持久化。
        """
        # 1. 内存缓存命中
        if buyer_id in self._cache:
            session = self._cache[buyer_id]
            # LRU：移到末尾（最近访问）
            self._cache.move_to_end(buyer_id)
            now = datetime.now(timezone.utc)
            # session.updated_at 在写入时已确保是 aware UTC
            updated = _ensure_aware_utc(session.updated_at)
            if (now - updated).total_seconds() < SESSION_TTL:
                return session
            # 超时：丢弃旧会话
            log.info(
                "session_store.expired",
                buyer_id=buyer_id,
                old_session_id=session.session_id,
            )
            del self._cache[buyer_id]

        # 2. 从 DB 恢复
        session = await self._restore_from_db(platform, buyer_id, shop_id)
        if session is not None:
            self._cache[buyer_id] = session
            self._evict_if_needed()
            return session

        # 3. 创建新会话
        session = Session(
            session_id=str(uuid.uuid4()),
            platform=platform,
            buyer_id=buyer_id,
            shop_id=shop_id,
        )
        await self._persist_session_row(session)
        self._cache[buyer_id] = session
        self._evict_if_needed()
        log.info(
            "session_store.created",
            session_id=session.session_id,
            buyer_id=buyer_id,
            platform=platform,
        )
        return session

    async def _restore_from_db(
        self,
        platform: str,
        buyer_id: str,
        shop_id: str,
    ) -> Session | None:
        """从 DB 恢复该买家最近一个会话及其消息。"""
        await self._ensure_db()
        assert self._session_maker is not None

        async with self._session_maker() as db:
            # 查找该买家最近活跃的会话
            result = await db.execute(
                select(SessionRow)
                .where(SessionRow.buyer_id == buyer_id)
                .where(SessionRow.platform == platform)
                .where(SessionRow.shop_id == shop_id)
                .order_by(SessionRow.updated_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None

            # 检查是否超时（DB 读出的 naive datetime 需补 tzinfo）
            now = datetime.now(timezone.utc)
            updated_at = _ensure_aware_utc(row.updated_at)
            if (now - updated_at).total_seconds() >= SESSION_TTL:
                return None

            # 加载历史消息（只恢复 user / assistant 对话，不含 tool 中间态）
            msg_result = await db.execute(
                select(MessageRow)
                .where(MessageRow.session_id == row.id)
                .where(MessageRow.role.in_(["user", "assistant"]))
                .order_by(MessageRow.id)
            )
            msgs = msg_result.scalars().all()

            session = Session(
                session_id=row.id,
                platform=row.platform,
                buyer_id=row.buyer_id,
                shop_id=row.shop_id,
            )
            # DB 读出的时间统一补 tzinfo
            session.created_at = _ensure_aware_utc(row.created_at)
            session.updated_at = updated_at

            for m in msgs:
                session.messages.append(Message(role=m.role, content=m.content))

            log.info(
                "session_store.restored",
                buyer_id=buyer_id,
                session_id=session.session_id,
                msg_count=len(msgs),
            )
            return session

    async def _persist_session_row(self, session: Session) -> None:
        """将新会话写入 DB。"""
        await self._ensure_db()
        assert self._session_maker is not None

        async with self._session_maker() as db:
            db.add(
                SessionRow(
                    id=session.session_id,
                    platform=session.platform,
                    shop_id=session.shop_id,
                    buyer_id=session.buyer_id,
                )
            )
            await db.commit()

    async def save_message(self, session: Session, msg: Message) -> None:
        """持久化单条消息到 DB，并更新会话时间戳。

        调用方负责传入脱敏后的文本（user 消息已在 AnswerEngine 中脱敏），
        DB 中只存脱敏后文本，不落明文敏感信息。

        只持久化 user / assistant 的对话消息，不保存 tool 中间态。
        """
        if msg.role not in ("user", "assistant"):
            return

        await self._ensure_db()
        assert self._session_maker is not None

        async with self._session_maker() as db:
            db.add(
                MessageRow(
                    session_id=session.session_id,
                    role=msg.role,
                    content=msg.content,
                )
            )
            now = datetime.now(timezone.utc)
            await db.execute(
                update(SessionRow)
                .where(SessionRow.id == session.session_id)
                .values(updated_at=now)
            )
            await db.commit()
            # 同步内存中的 updated_at，避免 TTL 检查使用过期值导致会话被误判过期
            session.updated_at = now

    async def save_handoff(
        self,
        session: Session,
        reason: str,
    ) -> None:
        """记录转人工任务到 DB。

        当 AgentLoop 判定需要转人工时调用，管理后台可查询待处理任务。
        """
        await self._ensure_db()
        assert self._session_maker is not None

        async with self._session_maker() as db:
            db.add(
                HandoffTask(
                    session_id=session.session_id,
                    platform=session.platform,
                    buyer_id=session.buyer_id,
                    reason=reason,
                    status="pending",
                )
            )
            await db.commit()
            log.info(
                "session_store.handoff_saved",
                session_id=session.session_id,
                buyer_id=session.buyer_id,
            )

    def invalidate(self, buyer_id: str) -> None:
        """从内存缓存中移除会话。"""
        self._cache.pop(buyer_id, None)

    def _evict_if_needed(self) -> None:
        """缓存超限时淘汰最久未访问的会话。"""
        while len(self._cache) > CACHE_MAX:
            evicted_key, _ = self._cache.popitem(last=False)
            log.info("session_store.evicted", buyer_id=evicted_key)


# ===== 全局单例 =====

_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore()
    return _store
