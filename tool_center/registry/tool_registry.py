"""工具注册中心：统一管理 LLM function-calling 的工具定义。"""
from __future__ import annotations

from typing import Any

from runtime.llm.llm_provider import ToolSpec


class ToolRegistry:
    """工具注册表。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, tool: ToolSpec) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def register_all(self, tools: list[ToolSpec]) -> None:
        for t in tools:
            self.register(t)

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list_all(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def to_openai_format(self) -> list[dict[str, Any]]:
        """输出 OpenAI function-calling 格式。"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]


# 全局默认注册表
_default_registry: ToolRegistry | None = None


def get_default_registry() -> ToolRegistry:
    """返回预注册了客服工具的全局实例。"""
    global _default_registry
    if _default_registry is None:
        _default_registry = ToolRegistry()
        from apps.customer_service_agent.agent.tools import ALL_TOOLS  # 延迟导入以避免循环依赖
        _default_registry.register_all(ALL_TOOLS)
    return _default_registry
