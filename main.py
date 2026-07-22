"""AI 电商客服平台 - 统一入口。

启动 customer_service_agent 应用。
"""
import uvicorn
from common.config.config import settings


def main() -> None:
    uvicorn.run(
        "apps.customer_service_agent.main:create_app",
        factory=True,
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "dev",
    )


if __name__ == "__main__":
    main()
