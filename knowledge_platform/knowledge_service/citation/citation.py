"""引用溯源（预留接口）。"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Citation:
    """知识引用。"""
    source: str
    content: str
    score: float = 0.0


class CitationService:
    """引用溯源服务。
    TODO: 后续实现答案引用溯源
    """
    pass
