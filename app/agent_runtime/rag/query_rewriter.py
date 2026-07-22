"""RAG Query Rewriter - 从 context_builder 导出。

实际实现在 app.agent_runtime.conversation.context_builder.ContextBuilder
"""
from app.agent_runtime.conversation.context_builder import ContextBuilder

# 兼容旧名称
QueryRewriteService = ContextBuilder

__all__ = ["ContextBuilder", "QueryRewriteService"]
