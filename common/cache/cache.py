"""缓存抽象（预留接口）。"""
from __future__ import annotations
from typing import Any


class Cache:
    """缓存接口（预留）。
    TODO: 后续实现 Redis 缓存
    """
    async def get(self, key: str) -> Any | None:
        raise NotImplementedError
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        raise NotImplementedError
    
    async def delete(self, key: str) -> None:
        raise NotImplementedError
