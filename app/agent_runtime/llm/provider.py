"""LLM Provider 统一入口。

re-export 基础抽象类 + 提供工厂函数。
"""
from app.llm.base import (
    ContentPart,
    EmbeddingProvider,
    ImagePart,
    LLMProvider,
    LLMResponse,
    Message,
    RerankProvider,
    TextPart,
    ToolSpec,
    VLMProvider,
)

__all__ = [
    "ContentPart",
    "EmbeddingProvider",
    "ImagePart",
    "LLMProvider",
    "LLMResponse",
    "Message",
    "RerankProvider",
    "TextPart",
    "ToolSpec",
    "VLMProvider",
    "get_llm_provider",
    "get_vlm_provider",
    "get_embedding_provider",
    "get_rerank_provider",
]


def get_llm_provider() -> LLMProvider:
    """获取默认文本 LLM Provider（DeepSeek）。"""
    from app.llm.deepseek import get_llm

    return get_llm()


def get_vlm_provider() -> VLMProvider:
    """获取默认 Vision LLM Provider（MiMo-V2.5）。"""
    from app.llm.mimo import get_vlm

    return get_vlm()


def get_embedding_provider() -> EmbeddingProvider:
    """获取默认 Embedding Provider（DashScope）。"""
    from app.llm.embedding_dashscope import get_embedding

    return get_embedding()


def get_rerank_provider() -> RerankProvider:
    """获取默认 Rerank Provider（Jina）。"""
    from app.llm.rerank_jina import get_reranker

    return get_reranker()
