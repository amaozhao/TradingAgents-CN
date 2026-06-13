from .imports import (
    ActionType,
    Depends,
    HTTPException,
    User,
    config_provider,
    config_service,
    get_current_user,
    log_operation,
    logger,
    now_tz,
    ok,
    router,
    status,
)
from .setup import (
    ConfigApiResponse,
    ImportConfigRequest,
    SetDefaultRequest,
    SystemSettingsUpdateRequest,
    _sanitize_kv,
)


@router.post("/datasource/set-default", response_model=ConfigApiResponse)
async def set_default_data_source_legacy(
    request: SetDefaultRequest, current_user: User = Depends(get_current_user)
):
    """设置默认数据源"""
    try:
        success = await config_service.set_default_data_source(request.name)
        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="set_default_datasource",
                    details={"name": request.name},
                    success=True,
                )
            except Exception:
                pass
            return ok(
                data={
                    "message": "默认数据源设置成功",
                    "default_data_source": request.name,
                },
                message="默认数据源设置成功",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="指定的数据源不存在"
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="设置默认数据源失败",
        )


@router.get("/settings", response_model=ConfigApiResponse)
async def get_system_settings(current_user: User = Depends(get_current_user)):
    """获取系统设置"""
    try:
        effective = await config_provider.get_effective_system_settings()
        sanitized = _sanitize_kv(effective)
        response = ok(data=sanitized, message="获取系统设置成功")
        if isinstance(sanitized, dict):
            for key, value in sanitized.items():
                if key not in response:
                    response[key] = value
        return response
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取系统设置失败",
        )


@router.get("/settings/meta", response_model=ConfigApiResponse)
async def get_system_settings_meta(current_user: User = Depends(get_current_user)):
    """获取系统设置的元数据（敏感性、可编辑性、来源、是否有值）。
    返回结构：{success, data: {items: [{key,sensitive,editable,source,has_value}]}, message}
    """
    try:
        meta_map = await config_provider.get_system_settings_meta()
        items = [{"key": k, **v} for k, v in meta_map.items()]
        return ok(data={"items": items}, message="获取系统设置元数据成功")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取系统设置元数据失败",
        )


@router.put("/settings", response_model=ConfigApiResponse)
async def update_system_settings(
    settings: SystemSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    """更新系统设置"""
    settings_data = settings.model_dump()
    try:
        # 打印接收到的设置（用于调试）
        logger.info(f"📝 接收到的系统设置更新请求，包含 {len(settings_data)} 项")
        if "quick_analysis_model" in settings_data:
            logger.info(
                f"  ✓ quick_analysis_model: {settings_data['quick_analysis_model']}"
            )
        else:
            logger.warning("  ⚠️  未包含 quick_analysis_model")
        if "deep_analysis_model" in settings_data:
            logger.info(
                f"  ✓ deep_analysis_model: {settings_data['deep_analysis_model']}"
            )
        else:
            logger.warning("  ⚠️  未包含 deep_analysis_model")

        success = await config_service.update_system_settings(settings_data)
        if success:
            # 审计日志（忽略日志异常，不影响主流程）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="update_system_settings",
                    details={"changed_keys": list(settings_data.keys())},
                    success=True,
                )
            except Exception:
                pass
            # 失效缓存
            try:
                config_provider.invalidate()
            except Exception:
                pass
            return ok(data={"message": "系统设置更新成功"}, message="系统设置更新成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="系统设置更新失败",
            )
    except HTTPException:
        raise
    except Exception as e:
        # 审计失败记录（忽略日志异常）
        try:
            await log_operation(
                user_id=str(getattr(current_user, "id", "")),
                username=getattr(current_user, "username", "unknown"),
                action_type=ActionType.CONFIG_MANAGEMENT,
                action="update_system_settings",
                details={"changed_keys": list(settings_data.keys())},
                success=False,
                error_message=str(e),
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新系统设置失败",
        )


@router.post("/export", response_model=ConfigApiResponse)
async def export_config(current_user: User = Depends(get_current_user)):
    """导出配置"""
    try:
        config_data = await config_service.export_config()
        # 审计日志（忽略异常）
        try:
            await log_operation(
                user_id=str(getattr(current_user, "id", "")),
                username=getattr(current_user, "username", "unknown"),
                action_type=ActionType.DATA_EXPORT,
                action="export_config",
                details={"size": len(str(config_data))},
                success=True,
            )
        except Exception:
            pass
        return ok(
            data={
                "message": "配置导出成功",
                "data": config_data,
                "exported_at": now_tz().isoformat(),
            },
            message="配置导出成功",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="导出配置失败",
        )


@router.post("/import", response_model=ConfigApiResponse)
async def import_config(
    config_data: ImportConfigRequest, current_user: User = Depends(get_current_user)
):
    """导入配置"""
    try:
        import_data = config_data.model_dump()
        success = await config_service.import_config(import_data)
        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.DATA_IMPORT,
                    action="import_config",
                    details={"keys": list(import_data.keys())[:10]},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "配置导入成功"}, message="配置导入成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="配置导入失败"
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="导入配置失败",
        )


@router.post("/migrate-legacy", response_model=ConfigApiResponse)
async def migrate_legacy_config(current_user: User = Depends(get_current_user)):
    """迁移传统配置"""
    try:
        success = await config_service.migrate_legacy_config()
        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="migrate_legacy_config",
                    details={},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "传统配置迁移成功"}, message="传统配置迁移成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="传统配置迁移失败",
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="迁移传统配置失败",
        )
