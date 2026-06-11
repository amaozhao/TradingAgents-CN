from __future__ import annotations

import re
from typing import Any
from io import BytesIO

from importlib import import_module

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
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
from app.services.research.agent.live import LiveSafetyService
from app.services.research.agent.runtime import ResearchAgentRuntime
from app.services.research.agent.sessions import ResearchSessionService
from app.services.research.agent.skills import ResearchSkillCatalogService
from app.services.research.agent.swarm import ResearchSwarmService
from app.routers.research.stream import stream_events


router = APIRouter()
session_service = ResearchSessionService()
event_service = ResearchEventService()
artifact_service = ResearchArtifactService()
goal_service = ResearchGoalService(event_service=event_service)
swarm_service = ResearchSwarmService(event_service=event_service)
live_service = LiveSafetyService(event_service=event_service)
skill_service = ResearchSkillCatalogService()
job_service = ResearchJobService(event_service=event_service)
runtime_service = ResearchAgentRuntime(
    event_service=event_service, job_service=job_service
)


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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="标题不能为空"
        )
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
    return ok(
        data={"status": "deleted", "session_id": session_id}, message="研究会话已删除"
    )


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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在"
            )
        principal = _principal(current_user, session_id=session_id)
        result = await runtime_service.enqueue_user_prompt(
            principal=_principal(current_user, session_id=session_id),
            session_id=session_id,
            user_message=request.content,
            metadata=request.metadata,
        )
        background_tasks.add_task(
            runtime_service.run_queued_user_prompt,
            principal=principal,
            session_id=session_id,
            user_message=request.content,
            job_id=result["job_id"],
            attempt_id=result["attempt_id"],
            metadata=request.metadata,
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
    attempts = await runtime_service.list_attempts(
        session_id=session_id, user_id=user_id
    )
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return ok(data=goal, message="研究目标已更新")


@router.post(
    "/sessions/{session_id}/goal/evidence", response_model=ResearchAgentResponse
)
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return ok(data=goal, message="研究目标证据已添加")


@router.patch(
    "/sessions/{session_id}/goal/status", response_model=ResearchAgentResponse
)
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
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
            stream_events(
                event_service=event_service,
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
    if normalized_type.startswith("text/") or lowered.endswith(
        (".txt", ".md", ".csv", ".json", ".log")
    ):
        return {
            "status": "completed",
            "parser": "text",
            "text": raw.decode("utf-8", errors="replace"),
        }
    if lowered.endswith(".docx") or normalized_type in {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }:
        try:
            from docx import Document

            document = Document(BytesIO(raw))
            text = "\n".join(
                paragraph.text for paragraph in document.paragraphs if paragraph.text
            )
            return {"status": "completed", "parser": "python-docx", "text": text}
        except Exception as exc:
            return {
                "status": "failed",
                "parser": "python-docx",
                "text": "",
                "error": str(exc),
            }
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
    return {
        "status": "unsupported",
        "parser": "none",
        "text": "",
        "error": "Unsupported binary document type",
    }


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


extra = import_module("app.routers.research.extra")

router.include_router(extra.router)


def _sync_extra_state() -> None:
    for name in (
        "artifact_service",
        "event_service",
        "live_service",
        "runtime_service",
        "session_service",
        "skill_service",
        "swarm_service",
    ):
        setattr(extra, name, globals()[name])


def __getattr__(name: str):
    if hasattr(extra, name):
        _sync_extra_state()
        return getattr(extra, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
