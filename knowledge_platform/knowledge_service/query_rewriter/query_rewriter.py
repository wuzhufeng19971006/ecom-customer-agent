"""Query Rewriter - re-export context_builder。"""
from runtime.conversation.context_builder import ContextBuilder

# 兼容旧名称
QueryRewriteService = ContextBuilder

__all__ = ["ContextBuilder", "QueryRewriteService"]
