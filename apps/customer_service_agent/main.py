"""FastAPI 应用入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.customer_service_agent.api.qa import router as qa_router
from apps.customer_service_agent.api.qa_multimodal import router as qa_mm_router
from apps.customer_service_agent.api.webhooks import router as webhooks_router
from apps.customer_service_agent.api.admin import router as admin_router
from apps.customer_service_agent.api.admin_ui import router as admin_ui_router
from apps.customer_service_agent.api.batch_test import router as batch_test_router
from common.config.config import settings
from common.logger.logger import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.logger = setup_logging(level=settings.log_level)
    app.state.logger.info("startup", env=settings.app_env, port=settings.app_port)
    # 确保数据库表存在
    from common.database.database import init_db
    await init_db()
    yield
    app.state.logger.info("shutdown")


def create_app() -> FastAPI:
    app = FastAPI(title="ecom-customer-agent", version="0.1.0", lifespan=lifespan)
    app.include_router(webhooks_router)
    app.include_router(qa_router)
    app.include_router(qa_mm_router)
    app.include_router(admin_router)
    app.include_router(batch_test_router)
    app.include_router(admin_ui_router)
    return app


app = create_app()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
