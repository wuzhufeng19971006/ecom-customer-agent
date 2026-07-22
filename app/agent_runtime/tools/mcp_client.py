"""MCP (Model Context Protocol) 客户端。

预留接口，用于后续接入外部 MCP 服务器（如 GitHub MCP / Slack MCP）。
当前淘宝客服场景不使用 MCP，所有工具通过 tool_registry 注册。

参考: https://modelcontextprotocol.io
"""
from __future__ import annotations
from typing import Any


class MCPClient:
    """MCP 客户端（预留接口）。

    TODO: 后续实现：
    1. 连接 MCP 服务器（stdio / SSE 传输）
    2. 发现可用工具
    3. 转发工具调用
    """

    def __init__(self, server_config: dict[str, Any] | None = None) -> None:
        self.server_config = server_config or {}

    async def connect(self) -> None:
        """连接 MCP 服务器。"""
        raise NotImplementedError("MCP client not implemented yet")

    async def list_tools(self) -> list[dict[str, Any]]:
        """列出 MCP 服务器提供的工具。"""
        raise NotImplementedError("MCP client not implemented yet")

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """调用 MCP 工具。"""
        raise NotImplementedError("MCP client not implemented yet")
