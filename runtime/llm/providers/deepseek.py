"""DeepSeek V4 Flash LLM 实现。

走 OpenAI 兼容协议：POST {base}/chat/completions
- 模型名：deepseek-v4-flash（旧 deepseek-chat 已于 2026-07-24 停用，遵循官方迁移文档）
- 支持 tools / tool_choice，符合 function-calling 规范
- 支持 response_format json_object，用于结构化输出
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from common.config.config import settings
from common.logger.logger import get_logger
from runtime.llm.llm_provider import LLMProvider, LLMResponse, Message, ToolSpec

log = get_logger(__name__)


class DeepSeekLLM(LLMProvider):
    def __init__(
        self,
        *,
        api_base: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.api_base = (api_base or settings.deepseek_api_base).rstrip("/")
        self.api_key = api_key or settings.deepseek_api_key
        self.model = model or settings.deepseek_model
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.api_base,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=timeout,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def chat(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [self._dump_message(m) for m in messages],
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
        if response_format:
            payload["response_format"] = response_format

        resp = await self._client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]["message"]
        return LLMResponse(
            content=choice.get("content") or "",
            tool_calls=choice.get("tool_calls") or [],
            finish_reason=data["choices"][0].get("finish_reason", "stop"),
            raw=data,
        )

    @staticmethod
    def _dump_message(m: Message) -> dict[str, Any]:
        out: dict[str, Any] = {"role": m.role, "content": m.content}
        if m.name:
            out["name"] = m.name
        if m.tool_calls:
            out["tool_calls"] = m.tool_calls
        if m.tool_call_id:
            out["tool_call_id"] = m.tool_call_id
        return out

    async def close(self) -> None:
        await self._client.aclose()


# 便捷单例工厂
_llm: DeepSeekLLM | None = None


def get_llm() -> DeepSeekLLM:
    global _llm
    if _llm is None:
        _llm = DeepSeekLLM()
    return _llm
