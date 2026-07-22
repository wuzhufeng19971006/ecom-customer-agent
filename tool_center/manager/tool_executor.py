"""工具执行器：调用 LLM 返回的 tool_call。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tool_center.registry.tool_registry import ToolRegistry, get_default_registry
from common.logger.logger import get_logger

log = get_logger(__name__)


@dataclass
class ToolExecutionResult:
    """工具执行结果。"""
    tool_name: str
    success: bool
    output: str
    error: str = ""
    raw: Any = None


class ToolExecutor:
    """工具执行器。

    根据工具名查找对应的 handler 函数并执行。
    handler 是一个 async 函数，接受 dict 参数，返回 str。
    """

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or get_default_registry()
        self._handlers: dict[str, Any] = {}  # name -> async callable

    def register_handler(self, tool_name: str, handler: Any) -> None:
        """注册工具的实际执行函数。"""
        self._handlers[tool_name] = handler

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolExecutionResult:
        """执行一个工具调用。"""
        if tool_name not in self._handlers:
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                output="",
                error=f"no handler registered for tool: {tool_name}",
            )

        try:
            result = await self._handlers[tool_name](**arguments)
            return ToolExecutionResult(
                tool_name=tool_name,
                success=True,
                output=str(result),
                raw=result,
            )
        except Exception as e:
            log.error("tool_executor.failed", tool=tool_name, error=str(e))
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                output="",
                error=str(e),
            )

    async def execute_tool_calls(self, tool_calls: list[dict[str, Any]]) -> list[ToolExecutionResult]:
        """批量执行 LLM 返回的 tool_calls。"""
        import asyncio
        tasks = []
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", {})
            if isinstance(args, str):
                import json
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            tasks.append(self.execute(name, args))
        return await asyncio.gather(*tasks)
