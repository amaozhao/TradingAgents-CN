from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ConfigDict

from app.core.response import ok
from app.routers.account import get_current_user
from app.schemas.response import ApiResponse
from app.services.alpha.zoo.jobs import AlphaZooJobService
from app.services.alpha.zoo.schemas import AlphaBenchRequest, AlphaCompareRequest
from app.services.alpha.zoo.service import AlphaZooService
from app.services.research.agent.context import ResearchPrincipal


router = APIRouter()
alpha_service = AlphaZooService()
alpha_job_service = AlphaZooJobService()


class AlphaZooResponse(ApiResponse):
    model_config = ConfigDict(extra="allow")


def _principal(current_user: dict[str, Any]) -> ResearchPrincipal:
    try:
        return ResearchPrincipal.from_user(current_user)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户身份无效"
        ) from exc


@router.get("/list", response_model=AlphaZooResponse)
async def list_alpha_factors(
    family: str | None = None,
    zoo: str | None = None,
    theme: str | None = None,
    universe: str | None = None,
    search: str | None = None,
    limit: int | None = None,
    current_user: dict = Depends(get_current_user),
):
    _principal(current_user)
    data = alpha_service.list_factors(
        family=family,
        zoo=zoo,
        theme=theme,
        universe=universe,
        search=search,
        limit=limit,
    )
    return ok(data=data, message="Alpha因子列表获取成功")


@router.post("/bench", response_model=AlphaZooResponse)
async def create_alpha_bench_job(
    request: AlphaBenchRequest,
    current_user: dict = Depends(get_current_user),
):
    principal = _principal(current_user)
    try:
        job = await alpha_job_service.create_bench_job(
            principal=principal,
            alpha_id=request.alpha_id,
            symbols=request.symbols,
            start_date=request.start_date,
            end_date=request.end_date,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ok(data=job, message="Alpha Bench任务创建成功")


@router.post("/compare", response_model=AlphaZooResponse)
async def create_alpha_compare_job(
    request: AlphaCompareRequest,
    current_user: dict = Depends(get_current_user),
):
    principal = _principal(current_user)
    try:
        job = await alpha_job_service.create_compare_job(
            principal=principal,
            alpha_ids=request.alpha_ids,
            symbols=request.symbols,
            start_date=request.start_date,
            end_date=request.end_date,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ok(data=job, message="Alpha Compare任务创建成功")


@router.get("/jobs/{job_id}", response_model=AlphaZooResponse)
async def get_alpha_job(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    principal = _principal(current_user)
    job = await alpha_job_service.get_job(job_id, principal.user_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return ok(data=job, message="Alpha任务获取成功")


@router.get("/jobs/{job_id}/events", response_model=AlphaZooResponse)
async def list_alpha_job_events(
    job_id: str,
    after_event_id: int = 0,
    current_user: dict = Depends(get_current_user),
):
    principal = _principal(current_user)
    events = await alpha_job_service.list_events(
        job_id, principal.user_id, after_event_id
    )
    if events is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return ok(data=events, message="Alpha任务事件获取成功")


@router.get("/{alpha_id}", response_model=AlphaZooResponse)
async def get_alpha_factor(
    alpha_id: str,
    current_user: dict = Depends(get_current_user),
):
    _principal(current_user)
    factor = alpha_service.get_factor(alpha_id)
    if not factor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="因子不存在")
    return ok(data=factor, message="Alpha因子详情获取成功")
