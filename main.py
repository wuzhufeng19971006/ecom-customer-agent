"""AI 电商客服平台 - 统一入口。

启动 customer_service_agent 应用。
"""
import os
import sys

# 确保 Windows 环境下使用 UTF-8 编码，避免中文写入数据库时出现乱码
os.environ.setdefault("PYTHONUTF8", "1")
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

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
