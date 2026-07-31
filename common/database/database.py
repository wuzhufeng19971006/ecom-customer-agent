"""SQLAlchemy 异步引擎与 ORM 模型。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from common.config.config import settings


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    platform: Mapped[str] = mapped_column(String(16), index=True)
    shop_id: Mapped[str] = mapped_column(String(64), index=True)
    buyer_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    messages: Mapped[list["MessageRow"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class MessageRow(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    session: Mapped[SessionRow] = relationship(back_populates="messages")


class HandoffTask(Base):
    """转人工任务表。"""

    __tablename__ = "handoff_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    platform: Mapped[str] = mapped_column(String(16), index=True)
    buyer_id: Mapped[str] = mapped_column(String(64), index=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|done
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class BatchTestTask(Base):
    """批量测试任务表。"""

    __tablename__ = "batch_test_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    filename: Mapped[str] = mapped_column(String(256))
    total: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|running|completed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    items: Mapped[list["BatchTestItem"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class BatchTestItem(Base):
    """批量测试条目表：每条问题及其测试结果。"""

    __tablename__ = "batch_test_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("batch_test_tasks.id"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer, default=0)  # 行号
    question: Mapped[str] = mapped_column(Text)
    expected_answer: Mapped[str | None] = mapped_column(Text, default=None)
    category: Mapped[str | None] = mapped_column(String(64), default=None)
    # 测试结果
    actual_answer: Mapped[str | None] = mapped_column(Text, default=None)
    matched: Mapped[bool | None] = mapped_column(Boolean, default=None)
    sources_count: Mapped[int | None] = mapped_column(Integer, default=None)
    sources_text: Mapped[str | None] = mapped_column(Text, default=None)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    test_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|done|error
    error_msg: Mapped[str | None] = mapped_column(Text, default=None)
    # 人工审核
    review_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|correct|incorrect
    review_reason: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    task: Mapped[BatchTestTask] = relationship(back_populates="items")


async def init_db() -> None:
    """创建表（开发期使用，生产用 Alembic 迁移）。"""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
