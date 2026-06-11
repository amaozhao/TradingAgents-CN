from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.core.response import ok
from app.routers.account import get_current_user
from app.services.research.agent.provider.client import describe_agent_model_resolution
from app.services.research.agent.live import LivePermissionError, LiveSafetyError
from app.routers.research.stream import stream_events

from .agent import (
    LiveActionRequest,
    LiveBrokerRequest,
    MandateCommitRequest,
    ResearchAgentResponse,
    ResearchSettingsUpdateRequest,
    ResearchSwarmRunCreateRequest,
    _current_user_id,
    _is_admin,
    _principal,
    artifact_service,
    event_service,
    live_service,
    runtime_service,
    session_service,
    skill_service,
    swarm_service,
)


router = APIRouter()


@router.get("/runs", response_model=ResearchAgentResponse)
async def list_research_runs(current_user: dict = Depends(get_current_user)):
    user_id = _current_user_id(current_user)
    runs = await artifact_service.list_user_artifacts(
        user_id=user_id, artifact_type="run"
    )
    backtests = await artifact_service.list_user_artifacts(
        user_id=user_id, artifact_type="backtest_run"
    )
    return ok(data=[*runs, *backtests], message="研究运行产物列表获取成功")


@router.get("/skills", response_model=ResearchAgentResponse)
async def list_research_skills(current_user: dict = Depends(get_current_user)):
    _current_user_id(current_user)
    return ok(data=skill_service.list_skills(), message="Agent 技能目录获取成功")


@router.get("/api", response_model=ResearchAgentResponse)
async def get_research_agent_capabilities(
    current_user: dict = Depends(get_current_user),
):
    _current_user_id(current_user)
    return ok(
        data={
            "namespace": "/api/research-agent",
            "runtime": "current-project",
            "external_source_runtime": False,
            "capabilities": {
                "sessions": True,
                "events": True,
                "provider_loop": True,
                "tools": [
                    tool.name
                    for tool in runtime_service.registry.for_principal(
                        _principal(current_user), include_disabled=False
                    )
                ],
                "skills": len(skill_service.list_skills()),
                "live_mutation_requires_admin_surface": True,
            },
        },
        message="Research Agent capabilities 获取成功",
    )


@router.get("/settings/llm", response_model=ResearchAgentResponse)
async def get_research_agent_llm_settings(
    current_user: dict = Depends(get_current_user),
):
    _current_user_id(current_user)
    diagnostics = await describe_agent_model_resolution(_principal(current_user))
    return ok(
        data={
            **diagnostics,
            "provider": diagnostics.get("effective_provider"),
            "model": diagnostics.get("effective_model"),
            "user_model_keys_supported": True,
            "runtime_update_supported": False,
        },
        message="Agent LLM 设置获取成功",
    )


@router.put("/settings/llm", response_model=ResearchAgentResponse)
async def update_research_agent_llm_settings(
    request: ResearchSettingsUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    _current_user_id(current_user)
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限"
        )
    return ok(
        data={
            "status": "disabled_config_required",
            "accepted": False,
            "reason": "Agent LLM settings are sourced from current project settings/env and user model keys; runtime mutation is disabled.",
            "requested_keys": sorted(request.values.keys()),
        },
        message="Agent LLM 设置运行时修改未启用",
    )


@router.get("/settings/data-sources", response_model=ResearchAgentResponse)
async def get_research_agent_data_source_settings(
    current_user: dict = Depends(get_current_user),
):
    _current_user_id(current_user)
    return ok(
        data={
            "sources": ["akshare", "tushare", "yfinance", "finnhub", "baostock"],
            "secrets": "redacted",
            "runtime_update_supported": False,
        },
        message="Agent 数据源设置获取成功",
    )


@router.put("/settings/data-sources", response_model=ResearchAgentResponse)
async def update_research_agent_data_source_settings(
    request: ResearchSettingsUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    _current_user_id(current_user)
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限"
        )
    return ok(
        data={
            "status": "disabled_config_required",
            "accepted": False,
            "reason": "Data source settings are managed by current project configuration; runtime mutation is disabled.",
            "requested_keys": sorted(request.values.keys()),
        },
        message="Agent 数据源设置运行时修改未启用",
    )


@router.post("/system/shutdown", response_model=ResearchAgentResponse)
async def reject_system_shutdown(current_user: dict = Depends(get_current_user)):
    _current_user_id(current_user)
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限"
        )
    return ok(
        data={
            "status": "intentionally_rejected",
            "accepted": False,
            "reason": "Process shutdown is not exposed through the research-agent API in this project.",
        },
        message="系统关闭接口已按安全策略拒绝",
    )


@router.post("/runs/{run_id}/shutdown", response_model=ResearchAgentResponse)
async def reject_run_shutdown(
    run_id: str,
    current_user: dict = Depends(get_current_user),
):
    _current_user_id(current_user)
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限"
        )
    return ok(
        data={
            "status": "intentionally_rejected",
            "accepted": False,
            "run_id": run_id,
            "reason": "Per-run shutdown is not exposed through the research-agent API; cancellable current-project jobs use the session/job cancellation surfaces instead.",
        },
        message="运行关闭接口已按安全策略拒绝",
    )


@router.get("/runs/{run_id}", response_model=ResearchAgentResponse)
async def get_research_run(
    run_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    run = await _find_run_artifact(run_id, user_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="运行产物不存在"
        )
    return ok(data=run, message="研究运行产物获取成功")


@router.get("/runs/{run_id}/code", response_model=ResearchAgentResponse)
async def get_research_run_code(
    run_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    code = await artifact_service.find_artifact_by_payload_value(
        user_id=user_id,
        artifact_type="run_code",
        payload_key="run_id",
        payload_value=run_id,
    )
    if not code:
        run = await _find_run_artifact(run_id, user_id)
        payload = (
            run.get("payload") if run and isinstance(run.get("payload"), dict) else {}
        )
        if payload.get("code") or payload.get("generated_code"):
            code = {
                **run,
                "artifact_type": "run_code",
                "payload": {
                    "run_id": run_id,
                    "code": payload.get("code") or payload.get("generated_code"),
                },
            }
    if not code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="运行代码不存在"
        )
    return ok(data=code, message="研究运行代码获取成功")


@router.get("/runs/{run_id}/pine", response_model=ResearchAgentResponse)
async def get_research_run_pine(
    run_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    pine = await artifact_service.find_artifact_by_payload_value(
        user_id=user_id,
        artifact_type="run_pine",
        payload_key="run_id",
        payload_value=run_id,
    )
    if not pine:
        run = await _find_run_artifact(run_id, user_id)
        payload = (
            run.get("payload") if run and isinstance(run.get("payload"), dict) else {}
        )
        if payload.get("pine") or payload.get("pine_script"):
            pine = {
                **run,
                "artifact_type": "run_pine",
                "payload": {
                    "run_id": run_id,
                    "pine": payload.get("pine") or payload.get("pine_script"),
                },
            }
    if not pine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pine 产物不存在"
        )
    return ok(data=pine, message="Pine 产物获取成功")


@router.get("/shadow-reports/{shadow_id}", response_model=ResearchAgentResponse)
async def get_shadow_report(
    shadow_id: str,
    current_user: dict = Depends(get_current_user),
):
    report = await artifact_service.find_artifact_by_payload_value(
        user_id=_current_user_id(current_user),
        artifact_type="shadow_report",
        payload_key="shadow_id",
        payload_value=shadow_id,
    )
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Shadow 报告不存在"
        )
    return ok(data=report, message="Shadow 报告获取成功")


@router.get("/sessions/{session_id}/events/stream", response_model=None)
async def stream_research_events(
    session_id: str,
    after_event_id: int = Query(0, ge=0),
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
):
    current_user = await get_current_user(
        authorization or (f"Bearer {token}" if token else None)
    )
    user_id = _current_user_id(current_user)
    if not await session_service.get_session(session_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

    return StreamingResponse(
        stream_events(
            event_service=event_service,
            session_id=session_id,
            user_id=user_id,
            after_event_id=after_event_id,
        ),
        media_type="text/event-stream",
    )


@router.get("/swarm/presets", response_model=ResearchAgentResponse)
async def list_swarm_presets(current_user: dict = Depends(get_current_user)):
    _current_user_id(current_user)
    presets = await swarm_service.list_presets()
    return ok(data=presets, message="Swarm presets 获取成功")


@router.post("/swarm/runs", response_model=ResearchAgentResponse)
async def create_swarm_run(
    request: ResearchSwarmRunCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    if request.session_id and not await session_service.get_session(
        request.session_id, user_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    try:
        run = await swarm_service.create_run(
            principal=_principal(current_user, session_id=request.session_id),
            preset=request.preset,
            variables=request.variables,
            session_id=request.session_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return ok(data=run, message="Swarm run 已创建")


@router.get("/swarm/runs", response_model=ResearchAgentResponse)
async def list_swarm_runs(current_user: dict = Depends(get_current_user)):
    runs = await swarm_service.list_runs(_current_user_id(current_user))
    return ok(data=runs, message="Swarm runs 获取成功")


@router.get("/swarm/runs/{run_id}", response_model=ResearchAgentResponse)
async def get_swarm_run(
    run_id: str,
    current_user: dict = Depends(get_current_user),
):
    run = await swarm_service.get_run(run_id, _current_user_id(current_user))
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Swarm run 不存在"
        )
    return ok(data=run, message="Swarm run 获取成功")


@router.get("/swarm/runs/{run_id}/events", response_model=ResearchAgentResponse)
async def list_swarm_run_events(
    run_id: str,
    after_event_id: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    if not await swarm_service.get_run(run_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Swarm run 不存在"
        )
    events = await swarm_service.list_events(
        run_id=run_id, user_id=user_id, after_event_id=after_event_id
    )
    return ok(data=events, message="Swarm events 获取成功")


@router.post("/swarm/runs/{run_id}/cancel", response_model=ResearchAgentResponse)
async def cancel_swarm_run(
    run_id: str,
    current_user: dict = Depends(get_current_user),
):
    run = await swarm_service.cancel_run(run_id, _current_user_id(current_user))
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Swarm run 不存在"
        )
    return ok(data=run, message="Swarm run 已取消")


@router.post("/swarm/runs/{run_id}/retry", response_model=ResearchAgentResponse)
async def retry_swarm_run(
    run_id: str,
    current_user: dict = Depends(get_current_user),
):
    run = await swarm_service.retry_run(run_id, _principal(current_user))
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Swarm run 不存在"
        )
    return ok(data=run, message="Swarm run 已重试")


@router.get("/live/status", response_model=ResearchAgentResponse)
async def get_live_status(current_user: dict = Depends(get_current_user)):
    status_payload = await live_service.get_status(_principal(current_user))
    return ok(data=status_payload, message="Live runtime 状态获取成功")


@router.post("/live/halt", response_model=ResearchAgentResponse)
async def halt_live_runtime(
    request: LiveActionRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        result = await live_service.halt(
            principal=_principal(current_user, session_id=request.session_id),
            reason=request.reason or "manual halt",
            broker=request.broker,
            session_id=request.session_id,
        )
    except LivePermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    return ok(data=result, message="Live runtime 已暂停")


@router.post("/live/resume", response_model=ResearchAgentResponse)
async def resume_live_runtime(
    request: LiveActionRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        result = await live_service.resume(
            principal=_principal(current_user, session_id=request.session_id),
            reason=request.reason or "manual resume",
            broker=request.broker,
            session_id=request.session_id,
        )
    except LivePermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    return ok(data=result, message="Live runtime 已恢复")


@router.post("/live/authorize", response_model=ResearchAgentResponse)
async def authorize_live_broker(
    request: LiveBrokerRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        result = await live_service.authorize(
            principal=_principal(current_user, session_id=request.session_id),
            broker=request.broker,
            session_id=request.session_id,
        )
    except LivePermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    return ok(data=result, message="Live broker 已授权")


@router.post("/live/runner/start", response_model=ResearchAgentResponse)
async def start_live_runner(
    request: LiveBrokerRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        result = await live_service.runner_start(
            principal=_principal(current_user, session_id=request.session_id),
            broker=request.broker,
            session_id=request.session_id,
        )
    except LivePermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except LiveSafetyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return ok(data=result, message="Live runner 已启动")


@router.post("/live/runner/stop", response_model=ResearchAgentResponse)
async def stop_live_runner(
    request: LiveBrokerRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        result = await live_service.runner_stop(
            principal=_principal(current_user, session_id=request.session_id),
            broker=request.broker,
            session_id=request.session_id,
        )
    except LivePermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    return ok(data=result, message="Live runner 已停止")


@router.post("/mandate/commit", response_model=ResearchAgentResponse)
async def commit_mandate(
    request: MandateCommitRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        result = await live_service.commit_mandate(
            principal=_principal(current_user, session_id=request.session_id),
            session_id=request.session_id,
            proposal=request.proposal,
        )
    except LivePermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    return ok(data=result, message="Mandate 已提交")


async def _find_run_artifact(run_id: str, user_id: str) -> dict[str, Any] | None:
    direct = await artifact_service.get_artifact(run_id, user_id)
    if direct and direct.get("artifact_type") in {"run", "backtest_run"}:
        return direct
    for artifact_type in ("run", "backtest_run"):
        found = await artifact_service.find_artifact_by_payload_value(
            user_id=user_id,
            artifact_type=artifact_type,
            payload_key="run_id",
            payload_value=run_id,
        )
        if found:
            return found
    return None
