"""工具元数据定义。"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolMetadata:
    """工具元数据。"""
    name: str
    description: str
    category: str = "general"
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)
