from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.core.response import ok
from app.routers.account import get_current_user
from app.schemas.operations import ActionType
from app.schemas.response import ApiResponse
from app.services.operation import log_operation
from app.services.research.agent.user.model.keys import user_model_key_service


router = APIRouter(prefix="/user-model-keys")


class UserModelKeyCreateRequest(BaseModel):
    provider: str
    model: str
    api_key: str
    display_name: str | None = None
    enabled: bool = True


class UserModelKeyUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: str | None = None
    display_name: str | None = None
    enabled: bool | None = None


class UserModelKeyResponse(ApiResponse):
    model_config = ConfigDict(extra="allow")


def _current_user_value(current_user: dict[str, Any], key: str, default: Any = None):
    if isinstance(current_user, dict):
        return current_user.get(key, default)
    return getattr(current_user, key, default)


def _current_user_id(current_user: dict[str, Any]) -> str:
    user_id = _current_user_value(current_user, "id") or _current_user_value(
        current_user, "user_id"
    )
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户身份无效"
        )
    return str(user_id)


async def _audit_key_event(
    *,
    current_user: dict[str, Any],
    action: str,
    key_data: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    details = {
        "key_id": (key_data or {}).get("id"),
        "provider": (key_data or {}).get("provider"),
        "model": (key_data or {}).get("model"),
    }
    if extra:
        details.update(extra)
    details.pop("api_key", None)

    try:
        await log_operation(
            user_id=_current_user_id(current_user),
            username=str(_current_user_value(current_user, "username", "unknown")),
            action_type=ActionType.CONFIG_MANAGEMENT,
            action=action,
            details=details,
            success=True,
        )
    except Exception:
        pass


@router.post("", response_model=UserModelKeyResponse)
async def create_user_model_key(
    request: UserModelKeyCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    try:
        key = await user_model_key_service.create_key(
            user_id=user_id,
            provider=request.provider,
            model=request.model,
            api_key=request.api_key,
            display_name=request.display_name,
            enabled=request.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await _audit_key_event(
        current_user=current_user, action="create_user_model_key", key_data=key
    )
    return ok(data=key, message="用户模型密钥创建成功")


@router.get("", response_model=UserModelKeyResponse)
async def list_user_model_keys(current_user: dict = Depends(get_current_user)):
    keys = await user_model_key_service.list_keys(user_id=_current_user_id(current_user))
    return ok(data=keys, message="用户模型密钥列表获取成功")


@router.get("/{key_id}", response_model=UserModelKeyResponse)
async def get_user_model_key(
    key_id: str, current_user: dict = Depends(get_current_user)
):
    key = await user_model_key_service.get_key(
        user_id=_current_user_id(current_user), key_id=key_id
    )
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="密钥不存在")
    return ok(data=key, message="用户模型密钥获取成功")


@router.put("/{key_id}", response_model=UserModelKeyResponse)
async def update_user_model_key(
    key_id: str,
    request: UserModelKeyUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    changed_keys = [
        key
        for key, value in request.model_dump(exclude_unset=True).items()
        if value is not None
    ]
    try:
        key = await user_model_key_service.update_key(
            user_id=_current_user_id(current_user),
            key_id=key_id,
            api_key=request.api_key,
            display_name=request.display_name,
            enabled=request.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="密钥不存在")

    await _audit_key_event(
        current_user=current_user,
        action="update_user_model_key",
        key_data=key,
        extra={"changed_keys": [item for item in changed_keys if item != "api_key"]},
    )
    return ok(data=key, message="用户模型密钥更新成功")


@router.delete("/{key_id}", response_model=UserModelKeyResponse)
async def delete_user_model_key(
    key_id: str, current_user: dict = Depends(get_current_user)
):
    deleted = await user_model_key_service.delete_key(
        user_id=_current_user_id(current_user), key_id=key_id
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="密钥不存在")

    await _audit_key_event(
        current_user=current_user,
        action="delete_user_model_key",
        key_data={"id": key_id},
    )
    return ok(data={"id": key_id, "deleted": True}, message="用户模型密钥删除成功")
