"""冒烟测试：验证模块可正常导入、配置可加载。"""

import pytest


def test_imports():
    import app  # noqa: F401
    import app.main  # noqa: F401
    import app.core.config  # noqa: F401
    import app.llm.base  # noqa: F401
    import app.adapters.base  # noqa: F401
    import app.agent.loop  # noqa: F401
    import app.models.database  # noqa: F401


def test_settings_loaded():
    from app.core.config import settings

    assert settings.deepseek_model == "deepseek-chat"
    assert settings.dashscope_embedding_model.startswith("text-embedding")
    assert settings.jina_reranker_model.startswith("jina-reranker")


def test_app_factory():
    from app.main import create_app

    app = create_app()
    assert app.title == "ecom-customer-agent"


@pytest.mark.asyncio
async def test_chroma_collections():
    from app.retrieval.chroma_store import COLLECTIONS

    assert set(COLLECTIONS) == {"kb_faq", "kb_product", "kb_policy"}
