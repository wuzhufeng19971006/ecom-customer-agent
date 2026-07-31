"""冒烟测试：验证新架构模块可正常导入、配置可加载。"""

import pytest


def test_imports():
    import apps.customer_service_agent  # noqa: F401
    import apps.customer_service_agent.main  # noqa: F401
    import common.config.config  # noqa: F401
    import runtime.llm.llm_provider  # noqa: F401
    import apps.customer_service_agent.adapters.base  # noqa: F401
    import apps.customer_service_agent.agent.loop  # noqa: F401
    import common.database.database  # noqa: F401


def test_settings_loaded():
    from common.config.config import settings

    assert settings.deepseek_model == "deepseek-v4-flash"
    assert settings.dashscope_embedding_model.startswith("text-embedding")
    assert settings.jina_reranker_model.startswith("jina-reranker")


def test_app_factory():
    from apps.customer_service_agent.main import create_app

    app = create_app()
    assert app.title == "ecom-customer-agent"


@pytest.mark.asyncio
async def test_chroma_collections():
    from knowledge_platform.knowledge_service.retriever.retriever import COLLECTIONS

    assert set(COLLECTIONS) == {"kb_faq", "kb_product", "kb_policy"}


def test_legacy_app_compat():
    """app.* 兼容层已移除，直接验证 apps 路径可用。"""
    from apps.customer_service_agent.main import create_app

    app = create_app()
    assert app.title == "ecom-customer-agent"
