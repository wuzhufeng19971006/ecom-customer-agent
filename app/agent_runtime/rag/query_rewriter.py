"""兼容层：实际代码在 runtime.conversation.context_builder"""
from runtime.conversation.context_builder import ContextBuilder

# 兼容旧名称
QueryRewriteService = ContextBuilder

__all__ = ["ContextBuilder", "QueryRewriteService"]
