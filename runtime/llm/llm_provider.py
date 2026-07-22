"""Provider 抽象基类。

三类外部模型服务统一抽象，便于切换 / 降级 / 测试替身：
- LLMProvider:      DeepSeek V4 Flash，负责对话与工具调用
- VLMProvider:      MiMo-V2.5，多模态视觉理解 + 结构化输出
- EmbeddingProvider: 阿里云 DashScope，负责文本向量化
- RerankProvider:    Jina Reranker v2，负责召回结果二次精排
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextPart:
    text: str


@dataclass
class ImagePart:
    """图片内容。data 与 url 二选一。"""

    data: bytes | None = None  # 原始字节，会自动 base64 编码
    url: str | None = None
    mime_type: str = "image/jpeg"


ContentPart = TextPart | ImagePart


@dataclass
class Message:
    """对话消息，支持纯文本或多模态内容。

    - 纯文本：content 是 str
    - 多模态：content_parts 是 list[ContentPart]
    """

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str = ""
    content_parts: list[ContentPart] | None = None
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None

    def has_image(self) -> bool:
        if not self.content_parts:
            return False
        return any(isinstance(p, ImagePart) for p in self.content_parts)


@dataclass
class ToolSpec:
    """OpenAI function-calling 风格的工具定义。"""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str = "stop"
    raw: dict[str, Any] | None = None


class LLMProvider(ABC):
    """纯文本 LLM（用于 RAG 生成）。"""

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """对话补全，可选工具调用 / JSON 输出。"""

    @abstractmethod
    async def close(self) -> None: ...


class VLMProvider(ABC):
    """多模态 Vision LLM。"""

    @abstractmethod
    async def analyze(
        self,
        prompt: str,
        images: list[ImagePart],
        *,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        response_format_json: bool = False,
    ) -> LLMResponse:
        """对一张或多张图片做理解，可选 JSON 输出。"""

    @abstractmethod
    async def close(self) -> None: ...


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(
        self, texts: list[str], *, text_type: str = "document"
    ) -> list[list[float]]:
        """批量向量化。

        text_type:
          - "document" 写入知识库时使用
          - "query" 查询时使用
        部分服务商（如阿里云 DashScope）对两类文本采用不同编码策略。
        """

    @abstractmethod
    async def close(self) -> None: ...


@dataclass
class RerankResult:
    index: int
    score: float
    document: str


class RerankProvider(ABC):
    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        top_n: int = 4,
    ) -> list[RerankResult]:
        """对召回文档按与 query 的相关性重排。"""

    @abstractmethod
    async def close(self) -> None: ...
