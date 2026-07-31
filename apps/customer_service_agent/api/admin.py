"""后台管理 API。

知识点管理：
- GET    /admin/api/knowledge          列表（支持 collection 筛选/分页/搜索）
- POST   /admin/api/knowledge          新增知识点（同步写入 ChromaDB）
- PUT    /admin/api/knowledge/{id}     更新知识点
- DELETE /admin/api/knowledge/{id}     删除知识点
- POST   /admin/api/knowledge/ingest   批量导入 JSONL

会话记录管理：
- GET    /admin/api/sessions           会话列表（分页）
- GET    /admin/api/sessions/{id}      会话详情（含消息）
- POST   /admin/api/sessions           录入历史会话记录
- DELETE /admin/api/sessions/{id}      删除会话

统计：
- GET    /admin/api/stats              知识库数量 + 会话数量统计
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update, func

from common.config.config import settings
from common.database.database import Base, HandoffTask, MessageRow, SessionRow
from common.logger.logger import get_logger
from knowledge_platform.knowledge_service.retriever.retriever import (
    COLLECTIONS,
    ChromaStore,
    get_store,
)

router = APIRouter(prefix="/admin/api", tags=["admin"])
log = get_logger(__name__)


# ===== 共享 DB 引擎（避免每个请求创建/销毁连接池）=====

_async_engine: Any = None
_async_session_maker: Any = None


def _get_db():
    """获取共享的异步 DB session maker，惰性初始化。"""
    global _async_engine, _async_session_maker
    if _async_engine is None:
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        _async_engine = create_async_engine(settings.database_url, echo=False)
        _async_session_maker = async_sessionmaker(
            _async_engine, expire_on_commit=False
        )
    return _async_session_maker


# ===== Pydantic 模型 =====


class KnowledgeCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    answer: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)
    collection: str = Field(default="kb_faq")


class KnowledgeUpdate(BaseModel):
    question: str | None = None
    answer: str | None = None
    tags: list[str] | None = None


class KnowledgeBatchIngest(BaseModel):
    collection: str = Field(default="kb_faq")
    records: list[dict[str, Any]] = Field(..., min_length=1)


class SessionCreate(BaseModel):
    platform: str = Field(default="doudian")
    shop_id: str = Field(default="")
    buyer_id: str = Field(..., min_length=1)
    messages: list[dict[str, str]] = Field(
        ..., min_length=1
    )  # [{"role":"user","content":"..."},{"role":"assistant","content":"..."}]


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    meta: dict[str, Any] | None = None
    created_at: datetime


class SessionOut(BaseModel):
    id: str
    platform: str
    shop_id: str
    buyer_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class SessionDetail(SessionOut):
    messages: list[MessageOut] = []


# ===== 知识点管理 =====


@router.get("/knowledge")
async def list_knowledge(
    collection: str = Query(default="kb_faq"),
    search: str = Query(default=""),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """列出知识点（从 ChromaDB 读取）。"""
    if collection not in COLLECTIONS:
        raise HTTPException(400, f"无效集合，可选: {COLLECTIONS}")

    store = get_store()
    chroma_collection = store._collections[collection]
    result = chroma_collection.get()

    items = []
    for i, doc_id in enumerate(result["ids"]):
        doc = result["documents"][i]
        meta = result["metadatas"][i] or {}

        # 解析 Q: / A: 格式
        question = ""
        answer = ""
        if doc.startswith("Q:"):
            parts = doc.split("\nA:", 1)
            question = parts[0][3:].strip() if len(parts) > 0 else ""
            answer = parts[1].strip() if len(parts) > 1 else ""
        else:
            answer = doc

        # 搜索过滤
        if search:
            search_lower = search.lower()
            if search_lower not in question.lower() and search_lower not in answer.lower():
                continue

        tags_str = meta.get("tags", "")
        tags = tags_str.split(",") if tags_str else []

        items.append(
            {
                "id": doc_id,
                "question": question,
                "answer": answer,
                "tags": tags,
                "collection": collection,
                "metadata": meta,
            }
        )

    total = len(items)
    paged = items[offset : offset + limit]
    return {"items": paged, "total": total, "limit": limit, "offset": offset}


@router.post("/knowledge")
async def create_knowledge(item: KnowledgeCreate) -> dict[str, Any]:
    """新增知识点，同步写入 ChromaDB。"""
    if item.collection not in COLLECTIONS:
        raise HTTPException(400, f"无效集合，可选: {COLLECTIONS}")

    store = get_store()
    doc_id = str(uuid4())
    doc = f"Q: {item.question}\nA: {item.answer}"
    meta = {"tags": ",".join(item.tags)} if item.tags else {}

    await store.add(item.collection, ids=[doc_id], documents=[doc], metadatas=[meta])

    log.info("admin.knowledge_created", id=doc_id, collection=item.collection)

    return {
        "id": doc_id,
        "question": item.question,
        "answer": item.answer,
        "tags": item.tags,
        "collection": item.collection,
    }


@router.put("/knowledge/{doc_id}")
async def update_knowledge(
    doc_id: str, item: KnowledgeUpdate, collection: str = Query(default="kb_faq")
) -> dict[str, Any]:
    """更新知识点（先删后增，因为 ChromaDB 不支持原地编辑文档+向量）。"""
    if collection not in COLLECTIONS:
        raise HTTPException(400, f"无效集合，可选: {COLLECTIONS}")

    store = get_store()
    chroma_collection = store._collections[collection]

    # 读取原记录
    existing = chroma_collection.get(ids=[doc_id])
    if not existing["ids"]:
        raise HTTPException(404, "知识点不存在")

    old_doc = existing["documents"][0]
    old_meta = existing["metadatas"][0] or {}

    # 解析原值
    old_q = ""
    old_a = ""
    if old_doc.startswith("Q:"):
        parts = old_doc.split("\nA:", 1)
        old_q = parts[0][3:].strip()
        old_a = parts[1].strip() if len(parts) > 1 else ""

    # 合并更新
    new_q = item.question if item.question is not None else old_q
    new_a = item.answer if item.answer is not None else old_a
    new_tags = item.tags if item.tags is not None else (
        old_meta.get("tags", "").split(",") if old_meta.get("tags") else []
    )

    # 删除旧记录
    chroma_collection.delete(ids=[doc_id])

    # 写入新记录
    new_doc = f"Q: {new_q}\nA: {new_a}"
    new_meta = {"tags": ",".join(new_tags)} if new_tags else {}
    await store.add(collection, ids=[doc_id], documents=[new_doc], metadatas=[new_meta])

    log.info("admin.knowledge_updated", id=doc_id, collection=collection)

    return {
        "id": doc_id,
        "question": new_q,
        "answer": new_a,
        "tags": new_tags,
        "collection": collection,
    }


@router.delete("/knowledge/{doc_id}")
async def delete_knowledge(
    doc_id: str, collection: str = Query(default="kb_faq")
) -> dict[str, Any]:
    """删除知识点。"""
    if collection not in COLLECTIONS:
        raise HTTPException(400, f"无效集合，可选: {COLLECTIONS}")

    store = get_store()
    chroma_collection = store._collections[collection]

    existing = chroma_collection.get(ids=[doc_id])
    if not existing["ids"]:
        raise HTTPException(404, "知识点不存在")

    chroma_collection.delete(ids=[doc_id])
    log.info("admin.knowledge_deleted", id=doc_id, collection=collection)

    return {"deleted": doc_id, "collection": collection}


@router.post("/knowledge/ingest")
async def batch_ingest(item: KnowledgeBatchIngest) -> dict[str, Any]:
    """批量导入知识点。"""
    if item.collection not in COLLECTIONS:
        raise HTTPException(400, f"无效集合，可选: {COLLECTIONS}")

    store = get_store()
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for r in item.records:
        q = str(r.get("question", "")).strip()
        a = str(r.get("answer", "")).strip()
        if not q or not a:
            continue
        doc = f"Q: {q}\nA: {a}"
        meta = {k: v for k, v in r.items() if k not in ("question", "answer")}
        meta = {k: (",".join(v) if isinstance(v, list) else str(v)) for k, v in meta.items()}
        ids.append(str(uuid4()))
        documents.append(doc)
        metadatas.append(meta)

    if not documents:
        raise HTTPException(400, "无有效记录")

    await store.add(item.collection, ids=ids, documents=documents, metadatas=metadatas)

    log.info("admin.knowledge_batch_ingested", collection=item.collection, count=len(documents))

    return {"ingested": len(documents), "collection": item.collection}


# ===== 会话记录管理 =====


@router.get("/sessions")
async def list_sessions(
    platform: str = Query(default=""),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """列出会话记录（使用 JOIN+GROUP BY 避免 N+1 查询）。"""
    db_maker = _get_db()

    async with db_maker() as session:
        query = select(SessionRow).order_by(SessionRow.created_at.desc())
        if platform:
            query = query.where(SessionRow.platform == platform)

        # 总数
        count_query = select(func.count()).select_from(SessionRow)
        if platform:
            count_query = count_query.where(SessionRow.platform == platform)
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        # 分页
        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        rows = result.scalars().all()

        if not rows:
            return {"items": [], "total": total, "limit": limit, "offset": offset}

        # 一次性获取所有会话的消息数（避免 N+1）
        session_ids = [row.id for row in rows]
        msg_count_query = (
            select(MessageRow.session_id, func.count().label("cnt"))
            .where(MessageRow.session_id.in_(session_ids))
            .group_by(MessageRow.session_id)
        )
        msg_count_result = await session.execute(msg_count_query)
        msg_counts = {row.session_id: row.cnt for row in msg_count_result}

        items = [
            SessionOut(
                id=row.id,
                platform=row.platform,
                shop_id=row.shop_id,
                buyer_id=row.buyer_id,
                created_at=row.created_at,
                updated_at=row.updated_at,
                message_count=msg_counts.get(row.id, 0),
            ).model_dump()
            for row in rows
        ]

    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    """获取会话详情（含所有消息）。"""
    db_maker = _get_db()

    async with db_maker() as session:
        result = await session.execute(
            select(SessionRow).where(SessionRow.id == session_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(404, "会话不存在")

        msg_result = await session.execute(
            select(MessageRow)
            .where(MessageRow.session_id == session_id)
            .order_by(MessageRow.id)
        )
        msgs = msg_result.scalars().all()

        messages = [
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                meta=m.meta,
                created_at=m.created_at,
            ).model_dump()
            for m in msgs
        ]

    detail = SessionDetail(
        id=row.id,
        platform=row.platform,
        shop_id=row.shop_id,
        buyer_id=row.buyer_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        message_count=len(messages),
    ).model_dump()
    detail["messages"] = messages

    return detail


@router.post("/sessions")
async def create_session(item: SessionCreate) -> dict[str, Any]:
    """录入历史会话记录。"""
    from common.database.database import init_db

    # 确保表存在
    await init_db()

    db_maker = _get_db()
    session_id = str(uuid4())

    async with db_maker() as session:
        # 创建会话
        session_row = SessionRow(
            id=session_id,
            platform=item.platform,
            shop_id=item.shop_id,
            buyer_id=item.buyer_id,
        )
        session.add(session_row)

        # 添加消息
        for msg in item.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if not content:
                continue
            session.add(
                MessageRow(
                    session_id=session_id,
                    role=role,
                    content=content,
                )
            )

        await session.commit()

    log.info("admin.session_created", session_id=session_id, messages=len(item.messages))

    return {"id": session_id, "message_count": len(item.messages)}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, Any]:
    """删除会话及其所有消息。"""
    db_maker = _get_db()

    async with db_maker() as session:
        result = await session.execute(
            select(SessionRow).where(SessionRow.id == session_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(404, "会话不存在")

        await session.execute(
            delete(MessageRow).where(MessageRow.session_id == session_id)
        )
        await session.execute(
            delete(SessionRow).where(SessionRow.id == session_id)
        )
        await session.commit()

    log.info("admin.session_deleted", session_id=session_id)

    return {"deleted": session_id}


# ===== 统计 =====


@router.get("/stats")
async def get_stats() -> dict[str, Any]:
    """知识库 + 会话统计。"""
    store = get_store()
    kb_stats = {}
    for col in COLLECTIONS:
        kb_stats[col] = store.count(col)

    db_maker = _get_db()

    session_count = 0
    message_count = 0
    try:
        async with db_maker() as session:
            r1 = await session.execute(select(func.count()).select_from(SessionRow))
            session_count = r1.scalar() or 0
            r2 = await session.execute(select(func.count()).select_from(MessageRow))
            message_count = r2.scalar() or 0
    except Exception:
        pass  # 表可能尚未创建

    return {
        "knowledge_base": kb_stats,
        "knowledge_total": sum(kb_stats.values()),
        "sessions": session_count,
        "messages": message_count,
    }
