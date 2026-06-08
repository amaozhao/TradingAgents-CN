from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.response import ok
from app.routers.account import get_current_user
from app.schemas.response import ApiResponse
from app.services.research_agent.context import ResearchPrincipal
from app.services.research_agent.tools.correlation import ResearchMatrixJobService


router = APIRouter()
matrix_job_service = ResearchMatrixJobService()


class ResearchMatrixResponse(ApiResponse):
    model_config = ConfigDict(extra="allow")


class CorrelationMatrixRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    method: str = "pearson"
    window: int = 60
    screening_result_id: str | None = None
    sector: str | None = None
    favorites_id: str | None = None
    universe_id: str | None = None


def _principal(current_user: dict[str, Any]) -> ResearchPrincipal:
    try:
        return ResearchPrincipal.from_user(current_user)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户身份无效"
        ) from exc


@router.post("/correlation", response_model=ResearchMatrixResponse)
async def create_correlation_matrix_job(
    request: CorrelationMatrixRequest,
    current_user: dict = Depends(get_current_user),
):
    principal = _principal(current_user)
    try:
        job = await matrix_job_service.create_correlation_job(
            principal=principal,
            symbols=request.symbols,
            method=request.method,
            window=request.window,
            screening_result_id=request.screening_result_id,
            sector=request.sector,
            favorites_id=request.favorites_id,
            universe_id=request.universe_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ok(data=job, message="相关性矩阵任务创建成功")


@router.get("/jobs/{job_id}", response_model=ResearchMatrixResponse)
async def get_matrix_job(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    principal = _principal(current_user)
    job = await matrix_job_service.get_job(job_id, principal.user_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return ok(data=job, message="相关性矩阵任务获取成功")


@router.get("/jobs/{job_id}/events", response_model=ResearchMatrixResponse)
async def list_matrix_job_events(
    job_id: str,
    after_event_id: int = 0,
    current_user: dict = Depends(get_current_user),
):
    principal = _principal(current_user)
    events = await matrix_job_service.list_events(
        job_id, principal.user_id, after_event_id
    )
    if events is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return ok(data=events, message="相关性矩阵任务事件获取成功")
