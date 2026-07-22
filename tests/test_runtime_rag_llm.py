"""测试 RAG / LLM 模块迁移到 agent_runtime 后的导入与兼容性。"""

import pytest


def test_import_rag_retriever():
    from app.agent_runtime.rag.retriever import (
        ChromaStore,
        RetrievalHit,
        get_store,
        COLLECTIONS,
    )

    assert ChromaStore is not None
    assert RetrievalHit is not None
    assert callable(get_store)
    assert set(COLLECTIONS) == {"kb_faq", "kb_product", "kb_policy"}


def test_import_query_rewriter():
    from app.agent_runtime.rag.query_rewriter import (
        ContextBuilder,
        QueryRewriteService,
    )

    assert ContextBuilder is not None
    # QueryRewriteService 是 ContextBuilder 的兼容别名
    assert QueryRewriteService is ContextBuilder


def test_import_llm_provider():
    from app.agent_runtime.llm.provider import (
        LLMProvider,
        VLMProvider,
        EmbeddingProvider,
        RerankProvider,
        get_llm_provider,
        get_vlm_provider,
        get_embedding_provider,
        get_rerank_provider,
    )

    assert LLMProvider is not None
    assert VLMProvider is not None
    assert EmbeddingProvider is not None
    assert RerankProvider is not None
    assert callable(get_llm_provider)
    assert callable(get_vlm_provider)
    assert callable(get_embedding_provider)
    assert callable(get_rerank_provider)


def test_compatibility_chroma_store():
    # 旧路径仍可用，且指向新模块的同一对象
    from app.retrieval.chroma_store import (
        ChromaStore,
        RetrievalHit,
        get_store,
        COLLECTIONS,
    )
    from app.agent_runtime.rag.retriever import (
        ChromaStore as NewChromaStore,
        RetrievalHit as NewRetrievalHit,
        get_store as NewGetStore,
        COLLECTIONS as NewCollections,
    )

    assert ChromaStore is NewChromaStore
    assert RetrievalHit is NewRetrievalHit
    assert get_store is NewGetStore
    assert COLLECTIONS is NewCollections


def test_compatibility_query_rewrite():
    from app.agent.query_rewrite import QueryRewriteService
    from app.agent_runtime.conversation.context_builder import ContextBuilder

    assert QueryRewriteService is ContextBuilder
