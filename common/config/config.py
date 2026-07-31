"""全局配置：从环境变量加载，集中管理所有外部服务凭证。"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根路径
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用
    app_env: str = Field(default="dev")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    log_level: str = Field(default="INFO")

    # DeepSeek (RAG 生成 LLM)
    deepseek_api_base: str = Field(default="https://api.deepseek.com")
    deepseek_api_key: str = Field(default="")
    deepseek_model: str = Field(default="deepseek-v4-flash")

    # 小米 MiMo-V2.5 (Vision LLM，多模态)
    mimo_api_base: str = Field(default="https://api.xiaomimimo.com/v1")
    mimo_api_key: str = Field(default="")
    mimo_model: str = Field(default="mimo-v2.5")

    # 魔搭 ModelScope Embedding（实际不可用，魔搭 API-Inference 暂未提供 embedding 接口）
    modelscope_api_base: str = Field(default="https://api-inference.modelscope.cn/v1")
    modelscope_api_token: str = Field(default="")
    modelscope_embedding_model: str = Field(default="bge-large-zh-v1.5")

    # 阿里云 DashScope Embedding（推荐，OpenAI 兼容协议）
    dashscope_api_base: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    dashscope_api_key: str = Field(default="")
    dashscope_embedding_model: str = Field(default="text-embedding-v3")

    # 会话合并窗口：500ms 内连续消息合并为一次回答
    conversation_debounce_ms: int = Field(default=500)
    # Vision 置信度阈值（高于此值才直接回答）
    vision_confidence_threshold: float = Field(default=0.85)
    # 会话超时（秒），超时后触发 BEST_EFFORT
    conversation_timeout_sec: int = Field(default=30)

    # Jina Reranker
    jina_api_base: str = Field(default="https://api.jina.ai/v1")
    jina_api_key: str = Field(default="")
    jina_reranker_model: str = Field(default="jina-reranker-v2-base-multilingual")

    # 淘宝
    taobao_app_key: str = Field(default="")
    taobao_app_secret: str = Field(default="")
    taobao_session_key: str = Field(default="")
    taobao_webhook_secret: str = Field(default="")
    taobao_api_base: str = Field(default="https://eco.taobao.com")

    # 抖店（抖音电商）
    doudian_app_key: str = Field(default="")
    doudian_app_secret: str = Field(default="")
    doudian_shop_id: str = Field(default="")
    doudian_access_token: str = Field(default="")
    doudian_webhook_secret: str = Field(default="")
    doudian_api_base: str = Field(default="https://openapi-fxg.jinritemai.com")

    # 数据
    database_url: str = Field(default="sqlite+aiosqlite:///./data/app.db")
    chroma_persist_dir: str = Field(default="./data/chroma")

    @property
    def chroma_path(self) -> Path:
        p = Path(self.chroma_persist_dir)
        if not p.is_absolute():
            p = BASE_DIR / p
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
