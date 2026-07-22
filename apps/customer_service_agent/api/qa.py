"""答疑 API：POST /api/qa。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from apps.customer_service_agent.agent.qa import QAService
from common.logger.logger import get_logger

router = APIRouter(prefix="/api", tags=["qa"])
log = get_logger(__name__)


class QARequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)


class QASource(BaseModel):
    text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class QAResponseModel(BaseModel):
    answer: str
    matched: bool
    sources: list[QASource]


@router.post("/qa", response_model=QAResponseModel)
async def qa(req: QARequest) -> QAResponseModel:
    svc = QAService()
    r = await svc.answer(req.question)
    log.info("qa.answered", matched=r.matched, n_sources=len(r.sources))
    return QAResponseModel(
        answer=r.answer,
        matched=r.matched,
        sources=[
            QASource(text=h.text, score=h.score, metadata=h.metadata) for h in r.sources
        ],
    )
