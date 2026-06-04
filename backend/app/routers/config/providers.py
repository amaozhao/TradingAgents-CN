# ruff: noqa: F401,F403,F405,F821
@router.post("/llm/providers", response_model=ConfigApiResponse)
async def add_llm_provider(
    request: LLMProviderRequest, current_user: User = Depends(get_current_user)
):
    """添加大模型厂家"""
    try:
        getattr(importlib.import_module("app.utils.keys"), "should_skip_api_key_update")

        provider_data = request.model_dump()

        # Provider catalog endpoints must not persist secrets directly. Secret
        # values are managed through dedicated config paths/env bridges.
        if "api_key" in provider_data:
            provider_data["api_key"] = ""

        if "api_secret" in provider_data:
            provider_data["api_secret"] = ""

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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加厂家失败: {str(e)}",
        )


@router.put("/llm/providers/{provider_id}", response_model=ConfigApiResponse)
async def update_llm_provider(
    provider_id: str,
    request: LLMProviderRequest,
    current_user: User = Depends(get_current_user),
):
    """更新大模型厂家"""
    try:
        getattr(importlib.import_module("app.utils.keys"), "should_skip_api_key_update")

        update_data = request.model_dump(exclude_unset=True)

        # Provider catalog endpoints must not persist secrets directly. Secret
        # values are managed through dedicated config paths/env bridges.
        if "api_key" in update_data:
            update_data["api_key"] = ""

        if "api_secret" in update_data:
            update_data["api_secret"] = ""

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
                        "changed_keys": list(request.model_dump().keys()),
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新厂家失败: {str(e)}",
        )


@router.delete("/llm/providers/{provider_id}", response_model=ConfigApiResponse)
async def delete_llm_provider(
    provider_id: str, current_user: User = Depends(get_current_user)
):
    """删除大模型厂家"""
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除厂家失败: {str(e)}",
        )


@router.patch("/llm/providers/{provider_id}/toggle", response_model=ConfigApiResponse)
async def toggle_llm_provider(
    provider_id: str,
    request: ToggleProviderRequest,
    current_user: User = Depends(get_current_user),
):
    """切换大模型厂家状态"""
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"切换厂家状态失败: {str(e)}",
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
        print(f"获取模型列表失败: {e}")
        traceback = importlib.import_module("traceback")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模型列表失败: {str(e)}",
        )


@router.post("/llm/providers/migrate-env", response_model=ConfigApiResponse)
async def migrate_env_to_providers(current_user: User = Depends(get_current_user)):
    """将环境变量配置迁移到厂家管理"""
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"环境变量迁移失败: {str(e)}",
        )


@router.post("/llm/providers/init-aggregators", response_model=ConfigApiResponse)
async def init_aggregator_providers(current_user: User = Depends(get_current_user)):
    """初始化聚合渠道厂家配置（302.AI、OpenRouter等）"""
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"初始化聚合渠道失败: {str(e)}",
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
    except Exception as e:
        logger.error(f"测试厂家API失败: {e}")
        raise HTTPException(status_code=500, detail=f"测试厂家API失败: {str(e)}")


# ========== 大模型配置管理 ==========
