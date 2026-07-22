"""通用工具函数。"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone


def generate_id(prefix: str = "") -> str:
    """生成唯一 ID。"""
    return f"{prefix}{uuid.uuid4().hex[:12]}" if prefix else uuid.uuid4().hex


def now_utc() -> datetime:
    """当前 UTC 时间。"""
    return datetime.now(timezone.utc)
