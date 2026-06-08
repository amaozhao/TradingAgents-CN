from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
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


@router.post("/sessions/{session_id}/messages", response_model=ResearchAgentResponse)
async def append_research_message(
    session_id: str,
    request: ResearchMessageCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    if request.role == "user":
        if not await session_service.get_session(session_id, user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
        result = await runtime_service.run_user_prompt(
            principal=_principal(current_user, session_id=session_id),
            session_id=session_id,
            user_message=request.content,
        )
        return ok(data=result, message="研究任务执行完成")

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
            _format_research_events_as_sse(events), media_type="text/event-stream"
        )
    return ok(data=events, message="研究事件列表获取成功")


@router.get("/sessions/{session_id}/events/stream", response_model=None)
async def stream_research_events(
    session_id: str,
    after_event_id: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    if not await session_service.get_session(session_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

    async def replay_existing_events():
        events = await event_service.list_after(
            session_id=session_id, user_id=user_id, after_event_id=after_event_id
        )
        for chunk in _format_research_events_as_sse(events):
            yield chunk

    return StreamingResponse(replay_existing_events(), media_type="text/event-stream")


def _format_research_events_as_sse(events: list[dict[str, Any]]):
    for event in events:
        yield (
            f"id: {event['event_id']}\n"
            f"event: {event['event_type']}\n"
            f"data: {json.dumps(event['payload'], ensure_ascii=False)}\n\n"
        )
