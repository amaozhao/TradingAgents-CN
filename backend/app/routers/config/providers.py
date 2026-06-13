from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .imports import (
        ActionType,
        Any,
        Depends,
        Dict,
        HTTPException,
        LLMProvider,
        LLMProviderRequest,
        User,
        config_service,
        get_current_user,
        importlib,
        log_operation,
        logger,
        ok,
        router,
        status,
    )
    from .setup import (
        ConfigApiResponse,
        FetchProviderModelsRequest,
        ToggleProviderRequest,
        require_admin_user,
    )


def _normalize_provider_secret_fields(
    data: Dict[str, Any], *, preserve_existing_on_blank: bool
) -> Dict[str, Any]:
    """Validate provider secrets without logging or echoing their values."""
    keys_module = importlib.import_module("app.utils.keys")
    is_valid_api_key = getattr(keys_module, "is_valid_api_key")
    should_skip_api_key_update = getattr(keys_module, "should_skip_api_key_update")

    for field, label in (("api_key", "API Key"), ("api_secret", "API Secret")):
        if field not in data:
            continue

        raw_value = data[field]
        if raw_value is None:
            if preserve_existing_on_blank:
                data.pop(field, None)
            else:
                data[field] = ""
            continue

        value = str(raw_value).strip()
        if value == "" or should_skip_api_key_update(value):
            if preserve_existing_on_blank:
                data.pop(field, None)
            else:
                data[field] = ""
            continue

        if not is_valid_api_key(value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{label} 无效：长度必须大于 10 个字符，且不能是占位符或缩略值",
            )

        data[field] = value

    return data


@router.post("/llm/providers", response_model=ConfigApiResponse)
async def add_llm_provider(
    request: LLMProviderRequest, current_user: User = Depends(get_current_user)
):
    """添加大模型厂家"""
    require_admin_user(current_user)
    try:
        provider_data = _normalize_provider_secret_fields(
            request.model_dump(exclude_unset=True), preserve_existing_on_blank=False
        )

        provider = LLMProvider(**provider_data)
        provider_id = await config_service.add_llm_provider(provider)

        # 审计日志（忽略异常）
        try:
            await log_operation(
                user_id=str(getattr(current_user, "id", "")),
                username=getattr(current_user, "username", "unknown"),
                action_type=ActionType.CONFIG_MANAGEMENT,
                action="add_llm_provider",
                details={"provider_id": str(provider_id), "name": request.name},
                success=True,
            )
        except Exception:
            pass

        return ok(
            data={"message": "厂家添加成功", "id": str(provider_id)},
            message="厂家添加成功",
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="添加厂家失败",
        )


@router.put("/llm/providers/{provider_id}", response_model=ConfigApiResponse)
async def update_llm_provider(
    provider_id: str,
    request: LLMProviderRequest,
    current_user: User = Depends(get_current_user),
):
    """更新大模型厂家"""
    require_admin_user(current_user)
    try:
        update_data = _normalize_provider_secret_fields(
            request.model_dump(exclude_unset=True), preserve_existing_on_blank=True
        )

        success = await config_service.update_llm_provider(provider_id, update_data)

        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="update_llm_provider",
                    details={
                        "provider_id": provider_id,
                        "changed_keys": list(update_data.keys()),
                    },
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "厂家更新成功"}, message="厂家更新成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="厂家不存在"
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新厂家失败",
        )


@router.delete("/llm/providers/{provider_id}", response_model=ConfigApiResponse)
async def delete_llm_provider(
    provider_id: str, current_user: User = Depends(get_current_user)
):
    """删除大模型厂家"""
    require_admin_user(current_user)
    try:
        success = await config_service.delete_llm_provider(provider_id)

        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="delete_llm_provider",
                    details={"provider_id": provider_id},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "厂家删除成功"}, message="厂家删除成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="厂家不存在"
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除厂家失败",
        )


@router.patch("/llm/providers/{provider_id}/toggle", response_model=ConfigApiResponse)
async def toggle_llm_provider(
    provider_id: str,
    request: ToggleProviderRequest,
    current_user: User = Depends(get_current_user),
):
    """切换大模型厂家状态"""
    require_admin_user(current_user)
    try:
        is_active = request.is_active
        success = await config_service.toggle_llm_provider(provider_id, is_active)

        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="toggle_llm_provider",
                    details={"provider_id": provider_id, "is_active": bool(is_active)},
                    success=True,
                )
            except Exception:
                pass
            return ok(
                data={"message": f"厂家已{'启用' if is_active else '禁用'}"},
                message=f"厂家已{'启用' if is_active else '禁用'}",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="厂家不存在"
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="切换厂家状态失败",
        )


@router.post(
    "/llm/providers/{provider_id}/fetch-models", response_model=ConfigApiResponse
)
async def fetch_provider_models(
    provider_id: str,
    request: FetchProviderModelsRequest | None = None,
    current_user: User = Depends(get_current_user),
):
    """从厂家 API 获取模型列表"""
    require_admin_user(current_user)
    try:
        filters = request.model_dump(exclude_none=True) if request else None
        logger.info(
            "🔍 [API] POST /api/config/llm/providers/%s/fetch-models user=%s filters=%s",
            provider_id,
            getattr(current_user, "username", None),
            filters,
        )
        result = await config_service.fetch_provider_models(provider_id, filters)
        logger.info(
            "📦 [API] fetch-models result provider_id=%s success=%s models=%s message=%s",
            provider_id,
            result.get("success"),
            len(result.get("models") or []),
            result.get("message"),
        )
        return ok(data=result, message=result.get("message", "获取模型列表成功"))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取模型列表失败: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取模型列表失败",
        )


@router.post("/llm/providers/migrate-env", response_model=ConfigApiResponse)
async def migrate_env_to_providers(current_user: User = Depends(get_current_user)):
    """将环境变量配置迁移到厂家管理"""
    require_admin_user(current_user)
    try:
        result = await config_service.migrate_env_to_providers()
        # 审计日志（忽略异常）
        try:
            await log_operation(
                user_id=str(getattr(current_user, "id", "")),
                username=getattr(current_user, "username", "unknown"),
                action_type=ActionType.CONFIG_MANAGEMENT,
                action="migrate_env_to_providers",
                details={
                    "migrated_count": result.get("migrated_count", 0),
                    "skipped_count": result.get("skipped_count", 0),
                },
                success=bool(result.get("success", False)),
            )
        except Exception:
            pass

        return ok(
            data={
                "message": result["message"],
                "data": {
                    "migrated_count": result.get("migrated_count", 0),
                    "skipped_count": result.get("skipped_count", 0),
                },
            },
            message=result["message"],
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="环境变量迁移失败",
        )


@router.post("/llm/providers/init-aggregators", response_model=ConfigApiResponse)
async def init_aggregator_providers(current_user: User = Depends(get_current_user)):
    """初始化聚合渠道厂家配置（302.AI、OpenRouter等）"""
    require_admin_user(current_user)
    try:
        result = await config_service.init_aggregator_providers()

        # 审计日志（忽略异常）
        try:
            await log_operation(
                user_id=str(getattr(current_user, "id", "")),
                username=getattr(current_user, "username", "unknown"),
                action_type=ActionType.CONFIG_MANAGEMENT,
                action="init_aggregator_providers",
                details={
                    "added_count": result.get("added", 0),
                    "skipped_count": result.get("skipped", 0),
                },
                success=bool(result.get("success", False)),
            )
        except Exception:
            pass

        return ok(
            data={
                "success": result["success"],
                "message": result["message"],
                "data": {
                    "added_count": result.get("added", 0),
                    "skipped_count": result.get("skipped", 0),
                },
            },
            message=result["message"],
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="初始化聚合渠道失败",
        )


@router.post("/llm/providers/{provider_id}/test", response_model=ConfigApiResponse)
async def test_provider_api(
    provider_id: str, current_user: User = Depends(get_current_user)
):
    """测试厂家API密钥"""
    try:
        logger.info(f"🧪 收到API测试请求 - provider_id: {provider_id}")
        result = await config_service.test_provider_api(provider_id)
        logger.info(f"🧪 API测试结果: {result}")
        return ok(data=result, message=result.get("message", "测试厂家API完成"))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("测试厂家API失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="测试厂家API失败")


# ========== 大模型配置管理 ==========
