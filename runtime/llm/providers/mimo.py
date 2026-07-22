"""小米 MiMo-V2.5 多模态 LLM 客户端。

走 OpenAI 兼容协议：POST {base}/chat/completions
- 模型名：mimo-v2.5
- 支持图片输入（content 数组，含 image_url 项）
- 支持 response_format: {"type": "json_object"} 强制 JSON 输出
- 文档：https://platform.xiaomimimo.com
"""

from __future__ import annotations

import base64
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from common.config.config import settings
from common.logger.logger import get_logger
from runtime.llm.llm_provider import ImagePart, LLMResponse, VLMProvider

log = get_logger(__name__)


class MiMoVLM(VLMProvider):
    def __init__(
        self,
        *,
        api_base: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 90.0,  # VLM 调用通常较慢
    ) -> None:
        self.api_base = (api_base or settings.mimo_api_base).rstrip("/")
        self.api_key = api_key or settings.mimo_api_key
        self.model = model or settings.mimo_model
        if not self.api_key:
            log.warning("vlm.no_api_key", hint="set MIMO_API_KEY in .env")
        self._client = httpx.AsyncClient(
            base_url=self.api_base,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=timeout,
        )

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=10))
    async def analyze(
        self,
        prompt: str,
        images: list[ImagePart],
        *,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        response_format_json: bool = False,
    ) -> LLMResponse:
        if not images:
            raise ValueError("MiMoVLM.analyze requires at least one image")

        # 组装 OpenAI vision 格式的 content
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for img in images:
            if img.data:
                b64 = base64.b64encode(img.data).decode("ascii")
                url = f"data:{img.mime_type};base64,{b64}"
            elif img.url:
                url = img.url
            else:
                continue
            content.append({"type": "image_url", "image_url": {"url": url}})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}

        resp = await self._client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]["message"]
        return LLMResponse(
            content=choice.get("content") or "",
            finish_reason=data["choices"][0].get("finish_reason", "stop"),
            raw=data,
        )

    async def close(self) -> None:
        await self._client.aclose()


_vlm: MiMoVLM | None = None


def get_vlm() -> MiMoVLM:
    global _vlm
    if _vlm is None:
        _vlm = MiMoVLM()
    return _vlm
