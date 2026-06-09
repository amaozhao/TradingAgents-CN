from __future__ import annotations

import json
from typing import Any

import asyncio

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from app.core.response import ok
from app.routers.account import get_current_user
from app.schemas.response import ApiResponse
from app.services.research_agent.artifacts import ResearchArtifactService
from app.services.research_agent.context import ResearchPrincipal
from app.services.research_agent.events import ResearchEventService
from app.services.research_agent.runtime import ResearchAgentRuntime
from app.services.research_agent.sessions import ResearchSessionService


router = APIRouter()
session_service = ResearchSessionService()
event_service = ResearchEventService()
artifact_service = ResearchArtifactService()
runtime_service = ResearchAgentRuntime(event_service=event_service)


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


def _current_user_id(current_user: dict[str, Any]) -> str:
    user_id = current_user.get("id") or current_user.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户身份无效"
        )
    return str(user_id)


def _principal(current_user: dict[str, Any], session_id: str | None = None):
    return ResearchPrincipal.from_user(current_user, session_id=session_id)


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


def _format_research_events_as_sse(events: list[dict[str, Any]]):
    for event in events:
        yield (
            f"id: {event['event_id']}\n"
            f"event: {event['event_type']}\n"
            f"data: {json.dumps(event['payload'], ensure_ascii=False)}\n\n"
        )


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
