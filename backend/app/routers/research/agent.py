from __future__ import annotations

import json
import re
from typing import Any
from io import BytesIO

import asyncio

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    status,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from app.core.response import ok
from app.routers.account import get_current_user
from app.schemas.response import ApiResponse
from app.services.research.agent.artifacts import ResearchArtifactService
from app.services.research.agent.context import ResearchPrincipal
from app.services.research.agent.events import ResearchEventService
from app.services.research.agent.goals import (
    ResearchGoalConflictError,
    ResearchGoalService,
)
from app.services.research.agent.jobs import ResearchJobService
from app.services.research.agent.provider.client import describe_agent_model_resolution
from app.services.research.agent.live import (
    LivePermissionError,
    LiveSafetyError,
    LiveSafetyService,
)
from app.services.research.agent.runtime import ResearchAgentRuntime
from app.services.research.agent.sessions import ResearchSessionService
from app.services.research.agent.skills import ResearchSkillCatalogService
from app.services.research.agent.swarm import ResearchSwarmService


router = APIRouter()
session_service = ResearchSessionService()
event_service = ResearchEventService()
artifact_service = ResearchArtifactService()
goal_service = ResearchGoalService(event_service=event_service)
swarm_service = ResearchSwarmService(event_service=event_service)
live_service = LiveSafetyService(event_service=event_service)
skill_service = ResearchSkillCatalogService()
job_service = ResearchJobService(event_service=event_service)
runtime_service = ResearchAgentRuntime(event_service=event_service, job_service=job_service)


class ResearchAgentResponse(ApiResponse):
    model_config = ConfigDict(extra="allow")


class ResearchSessionCreateRequest(BaseModel):
    title: str | None = None


class ResearchSessionUpdateRequest(BaseModel):
    title: str


class ResearchMessageCreateRequest(BaseModel):
    role: str
    content: str
    metadata: dict[str, Any] = {}


class ResearchGoalCreateRequest(BaseModel):
    title: str
    description: str = ""
    criteria: list[str] = []


class ResearchGoalUpdateRequest(BaseModel):
    expected_goal_id: str
    title: str | None = None
    description: str | None = None
    criteria: list[str] | None = None


class ResearchGoalStatusRequest(BaseModel):
    expected_goal_id: str
    status: str
    reason: str = ""


class ResearchGoalEvidenceRequest(BaseModel):
    expected_goal_id: str
    evidence: dict[str, Any]


class ResearchSwarmRunCreateRequest(BaseModel):
    preset: str
    variables: dict[str, Any] = {}
    session_id: str | None = None


class LiveActionRequest(BaseModel):
    reason: str = ""
    broker: str | None = None
    session_id: str | None = None


class LiveBrokerRequest(BaseModel):
    broker: str = "paper"
    session_id: str | None = None


class MandateCommitRequest(BaseModel):
    proposal: dict[str, Any]
    session_id: str | None = None


class ResearchSettingsUpdateRequest(BaseModel):
    values: dict[str, Any] = {}


def _current_user_id(current_user: dict[str, Any]) -> str:
    user_id = current_user.get("id") or current_user.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户身份无效"
        )
    return str(user_id)


def _principal(current_user: dict[str, Any], session_id: str | None = None):
    return ResearchPrincipal.from_user(current_user, session_id=session_id)


def _is_admin(current_user: dict[str, Any]) -> bool:
    roles = set(current_user.get("roles") or [])
    return bool(current_user.get("is_admin")) or "admin" in roles


@router.post("/sessions", response_model=ResearchAgentResponse)
async def create_research_session(
    request: ResearchSessionCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    session = await session_service.create_session(
        _principal(current_user), title=request.title
    )
    return ok(data=session, message="研究会话创建成功")


@router.get("/sessions", response_model=ResearchAgentResponse)
async def list_research_sessions(current_user: dict = Depends(get_current_user)):
    sessions = await session_service.list_sessions(_current_user_id(current_user))
    return ok(data=sessions, message="研究会话列表获取成功")


@router.get("/sessions/{session_id}", response_model=ResearchAgentResponse)
async def get_research_session(
    session_id: str, current_user: dict = Depends(get_current_user)
):
    session = await session_service.get_session(
        session_id, _current_user_id(current_user)
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return ok(data=session, message="研究会话获取成功")


@router.patch("/sessions/{session_id}", response_model=ResearchAgentResponse)
async def update_research_session(
    session_id: str,
    request: ResearchSessionUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    title = request.title.strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标题不能为空")
    session = await session_service.rename_session(
        session_id, _current_user_id(current_user), title[:100]
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return ok(data=session, message="研究会话已重命名")


@router.delete("/sessions/{session_id}", response_model=ResearchAgentResponse)
async def delete_research_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    deleted = await session_service.delete_session(
        session_id, _current_user_id(current_user)
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return ok(data={"status": "deleted", "session_id": session_id}, message="研究会话已删除")


@router.post("/sessions/{session_id}/messages", response_model=ResearchAgentResponse)
async def append_research_message(
    session_id: str,
    request: ResearchMessageCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    if request.role == "user":
        if not await session_service.get_session(session_id, user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
        principal = _principal(current_user, session_id=session_id)
        result = await runtime_service.enqueue_user_prompt(
            principal=_principal(current_user, session_id=session_id),
            session_id=session_id,
            user_message=request.content,
        )
        background_tasks.add_task(
            runtime_service.run_queued_user_prompt,
            principal=principal,
            session_id=session_id,
            user_message=request.content,
            job_id=result["job_id"],
            attempt_id=result["attempt_id"],
        )
        return ok(data=result, message="研究任务已开始")

    message = await session_service.append_message(
        session_id=session_id,
        user_id=user_id,
        role=request.role,
        content=request.content,
        metadata=request.metadata,
    )
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    await event_service.append(
        session_id=session_id,
        user_id=user_id,
        event_type="message",
        payload={"message_id": message["message_id"], "role": request.role},
    )
    return ok(data=message, message="研究消息保存成功")


@router.get("/sessions/{session_id}/messages", response_model=ResearchAgentResponse)
async def list_research_messages(
    session_id: str, current_user: dict = Depends(get_current_user)
):
    messages = await session_service.list_messages(
        session_id, _current_user_id(current_user)
    )
    return ok(data=messages, message="研究消息列表获取成功")


@router.get("/sessions/{session_id}/attempts", response_model=ResearchAgentResponse)
async def list_research_attempts(
    session_id: str, current_user: dict = Depends(get_current_user)
):
    user_id = _current_user_id(current_user)
    if not await session_service.get_session(session_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    attempts = await runtime_service.list_attempts(session_id=session_id, user_id=user_id)
    return ok(data=attempts, message="研究执行记录获取成功")


@router.post("/sessions/{session_id}/goal", response_model=ResearchAgentResponse)
async def create_research_goal(
    session_id: str,
    request: ResearchGoalCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    if not await session_service.get_session(session_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    goal = await goal_service.create_goal(
        principal=_principal(current_user, session_id=session_id),
        session_id=session_id,
        title=request.title,
        description=request.description,
        criteria=request.criteria,
    )
    return ok(data=goal, message="研究目标已创建")


@router.get("/sessions/{session_id}/goal", response_model=ResearchAgentResponse)
async def get_research_goal(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    if not await session_service.get_session(session_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    goal = await goal_service.get_goal(session_id, user_id)
    return ok(data=goal, message="研究目标获取成功")


@router.patch("/sessions/{session_id}/goal", response_model=ResearchAgentResponse)
async def update_research_goal(
    session_id: str,
    request: ResearchGoalUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    if not await session_service.get_session(session_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    try:
        goal = await goal_service.update_goal(
            session_id=session_id,
            user_id=user_id,
            expected_goal_id=request.expected_goal_id,
            updates=request.model_dump(exclude={"expected_goal_id"}, exclude_none=True),
        )
    except ResearchGoalConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ok(data=goal, message="研究目标已更新")


@router.post("/sessions/{session_id}/goal/evidence", response_model=ResearchAgentResponse)
async def add_research_goal_evidence(
    session_id: str,
    request: ResearchGoalEvidenceRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    if not await session_service.get_session(session_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    try:
        goal = await goal_service.add_evidence(
            session_id=session_id,
            user_id=user_id,
            expected_goal_id=request.expected_goal_id,
            evidence=request.evidence,
        )
    except ResearchGoalConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ok(data=goal, message="研究目标证据已添加")


@router.patch("/sessions/{session_id}/goal/status", response_model=ResearchAgentResponse)
async def update_research_goal_status(
    session_id: str,
    request: ResearchGoalStatusRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    if not await session_service.get_session(session_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    try:
        goal = await goal_service.update_status(
            session_id=session_id,
            user_id=user_id,
            expected_goal_id=request.expected_goal_id,
            status=request.status,
            reason=request.reason,
        )
    except ResearchGoalConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ok(data=goal, message="研究目标状态已更新")


@router.post("/sessions/{session_id}/cancel", response_model=ResearchAgentResponse)
async def cancel_research_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    if not await session_service.get_session(session_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    result = await runtime_service.cancel_session(
        principal=_principal(current_user, session_id=session_id),
        session_id=session_id,
    )
    return ok(data=result, message="研究任务已取消")


@router.get("/sessions/{session_id}/events", response_model=ResearchAgentResponse)
async def list_research_events(
    request: Request,
    session_id: str,
    after_event_id: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    if not await session_service.get_session(session_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    events = await event_service.list_after(
        session_id=session_id, user_id=user_id, after_event_id=after_event_id
    )
    if "text/event-stream" in request.headers.get("accept", ""):
        return StreamingResponse(
            _stream_research_events(
                session_id=session_id,
                user_id=user_id,
                after_event_id=after_event_id,
            ),
            media_type="text/event-stream",
        )
    return ok(data=events, message="研究事件列表获取成功")


@router.post("/upload", response_model=ResearchAgentResponse)
async def upload_research_file(
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
    current_user: dict = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    owner_session_id = session_id or f"user:{user_id}:uploads"
    if session_id and not await session_service.get_session(session_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    raw = await file.read()
    extracted = _extract_uploaded_text(
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        raw=raw,
    )
    artifact = await artifact_service.create_artifact(
        session_id=owner_session_id,
        user_id=user_id,
        artifact_type="upload",
        payload={
            "filename": file.filename or "upload",
            "content_type": file.content_type or "application/octet-stream",
            "size": len(raw),
            "text": extracted["text"],
            "extraction": extracted,
        },
    )
    if session_id:
        await event_service.append(
            session_id=session_id,
            user_id=user_id,
            event_type="artifact.created",
            payload={
                "artifact_id": artifact["artifact_id"],
                "artifact_type": "upload",
                "filename": file.filename,
            },
        )
    return ok(
        data={
            "status": "uploaded",
            "file_id": artifact["artifact_id"],
            "artifact_id": artifact["artifact_id"],
            "filename": file.filename or "upload",
            "size": len(raw),
        },
        message="文件已上传",
    )


def _extract_uploaded_text(
    *,
    filename: str,
    content_type: str,
    raw: bytes,
) -> dict[str, Any]:
    lowered = filename.lower()
    normalized_type = content_type.lower()
    if normalized_type.startswith("text/") or lowered.endswith((".txt", ".md", ".csv", ".json", ".log")):
        return {"status": "completed", "parser": "text", "text": raw.decode("utf-8", errors="replace")}
    if lowered.endswith(".docx") or normalized_type in {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }:
        try:
            from docx import Document

            document = Document(BytesIO(raw))
            text = "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text)
            return {"status": "completed", "parser": "python-docx", "text": text}
        except Exception as exc:
            return {"status": "failed", "parser": "python-docx", "text": "", "error": str(exc)}
    if lowered.endswith(".pdf") or normalized_type == "application/pdf":
        text = _extract_basic_pdf_text(raw)
        if text:
            return {"status": "completed", "parser": "basic-pdf", "text": text}
        return {
            "status": "unsupported",
            "parser": "basic-pdf",
            "text": "",
            "error": "PDF text extraction requires embedded literal text; scanned PDFs are not supported by the current dependency set.",
        }
    decoded = raw.decode("utf-8", errors="replace")
    if decoded.strip():
        return {"status": "completed", "parser": "utf8-fallback", "text": decoded}
    return {"status": "unsupported", "parser": "none", "text": "", "error": "Unsupported binary document type"}


def _extract_basic_pdf_text(raw: bytes) -> str:
    decoded = raw.decode("latin-1", errors="ignore")
    values = []
    for value in re.findall(r"\((?:\\.|[^\\()])*\)", decoded):
        text = value[1:-1]
        text = (
            text.replace(r"\(", "(")
            .replace(r"\)", ")")
            .replace(r"\\", "\\")
            .replace(r"\n", "\n")
            .replace(r"\r", "\r")
            .replace(r"\t", "\t")
        )
        cleaned = re.sub(r"\s+", " ", text).strip()
        if cleaned and any(char.isalnum() for char in cleaned):
            values.append(cleaned)
    return "\n".join(values)


@router.get("/artifacts/{artifact_id}", response_model=ResearchAgentResponse)
async def get_research_artifact(
    artifact_id: str,
    current_user: dict = Depends(get_current_user),
):
    artifact = await artifact_service.get_artifact(
        artifact_id, _current_user_id(current_user)
    )
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="产物不存在")
    return ok(data=artifact, message="研究产物获取成功")


@router.get("/sessions/{session_id}/artifacts", response_model=ResearchAgentResponse)
async def list_research_artifacts(
    session_id: str,
    artifact_type: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    if not await session_service.get_session(session_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    artifacts = await artifact_service.list_artifacts(
        session_id=session_id,
        user_id=user_id,
        artifact_type=artifact_type,
    )
    return ok(data=artifacts, message="研究产物列表获取成功")


@router.get("/runs", response_model=ResearchAgentResponse)
async def list_research_runs(current_user: dict = Depends(get_current_user)):
    user_id = _current_user_id(current_user)
    runs = await artifact_service.list_user_artifacts(user_id=user_id, artifact_type="run")
    backtests = await artifact_service.list_user_artifacts(
        user_id=user_id, artifact_type="backtest_run"
    )
    return ok(data=[*runs, *backtests], message="研究运行产物列表获取成功")


@router.get("/skills", response_model=ResearchAgentResponse)
async def list_research_skills(current_user: dict = Depends(get_current_user)):
    _current_user_id(current_user)
    return ok(data=skill_service.list_skills(), message="Agent 技能目录获取成功")


@router.get("/api", response_model=ResearchAgentResponse)
async def get_research_agent_capabilities(current_user: dict = Depends(get_current_user)):
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
async def get_research_agent_llm_settings(current_user: dict = Depends(get_current_user)):
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="运行产物不存在")
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
        payload = run.get("payload") if run and isinstance(run.get("payload"), dict) else {}
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="运行代码不存在")
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
        payload = run.get("payload") if run and isinstance(run.get("payload"), dict) else {}
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pine 产物不存在")
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shadow 报告不存在")
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
        _stream_research_events(
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Swarm run 不存在")
    return ok(data=run, message="Swarm run 获取成功")


@router.get("/swarm/runs/{run_id}/events", response_model=ResearchAgentResponse)
async def list_swarm_run_events(
    run_id: str,
    after_event_id: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    if not await swarm_service.get_run(run_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Swarm run 不存在")
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Swarm run 不存在")
    return ok(data=run, message="Swarm run 已取消")


@router.post("/swarm/runs/{run_id}/retry", response_model=ResearchAgentResponse)
async def retry_swarm_run(
    run_id: str,
    current_user: dict = Depends(get_current_user),
):
    run = await swarm_service.retry_run(run_id, _principal(current_user))
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Swarm run 不存在")
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LiveSafetyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return ok(data=result, message="Mandate 已提交")


def _format_research_events_as_sse(events: list[dict[str, Any]]):
    for event in events:
        yield (
            f"id: {event['event_id']}\n"
            f"event: {event['event_type']}\n"
            f"data: {json.dumps(event['payload'], ensure_ascii=False)}\n\n"
        )


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


async def _stream_research_events(
    *,
    session_id: str,
    user_id: str,
    after_event_id: int = 0,
    idle_timeout_seconds: float = 120.0,
):
    last_event_id = int(after_event_id or 0)
    idle_elapsed = 0.0
    poll_interval = 0.5
    terminal_events = {"task_completed", "task_failed"}

    while idle_elapsed < idle_timeout_seconds:
        events = await event_service.list_after(
            session_id=session_id,
            user_id=user_id,
            after_event_id=last_event_id,
        )
        if events:
            idle_elapsed = 0.0
            for chunk in _format_research_events_as_sse(events):
                yield chunk
            last_event_id = int(events[-1]["event_id"])
            if any(event["event_type"] in terminal_events for event in events):
                return
            continue

        yield "event: heartbeat\ndata: {}\n\n"
        await asyncio.sleep(poll_interval)
        idle_elapsed += poll_interval
