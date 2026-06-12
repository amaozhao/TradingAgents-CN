from .imports import (
    ActionType,
    Depends,
    HTTPException,
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
    SetDefaultRequest,
    _sanitize_llm_configs,
    _sort_llm_configs_by_newest,
    require_admin_user,
)

@router.get("/llm", response_model=ConfigApiResponse)
async def get_llm_configs(current_user: User = Depends(get_current_user)):
    """获取所有大模型配置"""
    try:
        logger.info("🔄 开始获取大模型配置...")
        config = await config_service.get_system_config()

        if not config:
            logger.warning("⚠️ 系统配置为空，返回空列表")
            return ok(data=[], message="获取大模型配置成功")

        logger.info(f"📊 系统配置存在，大模型配置数量: {len(config.llm_configs)}")

        # 如果没有大模型配置，创建一些示例配置
        if not config.llm_configs:
            logger.info("🔧 没有大模型配置，创建示例配置...")
            # 这里可以根据已有的厂家创建示例配置
            # 暂时返回空列表，让前端显示"暂无配置"

        # 获取所有供应商信息，用于过滤被禁用供应商的模型
        providers = await config_service.get_llm_providers()
        active_providers = [p for p in providers if p.is_active]

        # 过滤：只返回启用的模型 且 供应商也启用的模型
        filtered_configs = [
            llm_config
            for llm_config in config.llm_configs
            if llm_config.enabled
            and any(
                config_service._providers_match(llm_config.provider, provider.name) for provider in active_providers
            )
        ]

        sorted_configs = _sort_llm_configs_by_newest(filtered_configs)

        logger.info(f"✅ 过滤后的大模型配置数量: {len(sorted_configs)} (原始: {len(config.llm_configs)})")

        return ok(data=_sanitize_llm_configs(sorted_configs), message="获取大模型配置成功")
    except Exception as e:
        logger.error(f"❌ 获取大模型配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取大模型配置失败: {str(e)}",
        )


@router.delete("/llm/{provider}/{model_name}", response_model=ConfigApiResponse)
async def delete_llm_config(provider: str, model_name: str, current_user: User = Depends(get_current_user)):
    """删除大模型配置"""
    require_admin_user(current_user)
    try:
        logger.info(f"🗑️ 删除大模型配置请求 - provider: {provider}, model_name: {model_name}")
        success = await config_service.delete_llm_config(provider, model_name)

        if success:
            logger.info(f"✅ 大模型配置删除成功 - {provider}/{model_name}")

            # 同步定价配置到 trading_agents
            try:
                sync_pricing_config_now = getattr(
                    importlib.import_module("app.core.bridge"),
                    "sync_pricing_config_now",
                )
                sync_pricing_config_now()
                logger.info("✅ 定价配置已同步到 trading_agents")
            except Exception as e:
                logger.warning(f"⚠️  同步定价配置失败: {e}")

            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="delete_llm_config",
                    details={"provider": provider, "model_name": model_name},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "大模型配置删除成功"}, message="大模型配置删除成功")
        else:
            logger.warning(f"⚠️ 未找到大模型配置 - {provider}/{model_name}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="大模型配置不存在")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 删除大模型配置异常 - {provider}/{model_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除大模型配置失败: {str(e)}",
        )


@router.post("/llm/set-default", response_model=ConfigApiResponse)
async def set_default_llm_legacy(request: SetDefaultRequest, current_user: User = Depends(get_current_user)):
    """设置默认大模型"""
    require_admin_user(current_user)
    try:
        success = await config_service.set_default_llm(request.name)
        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="set_default_llm",
                    details={"name": request.name},
                    success=True,
                )
            except Exception:
                pass
            return ok(
                data={"message": "默认大模型设置成功", "default_llm": request.name},
                message="默认大模型设置成功",
            )
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="指定的大模型不存在")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"设置默认大模型失败: {str(e)}",
        )
