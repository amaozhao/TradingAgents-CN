from ..imports import (
    ActionType,
    DataSourceConfig,
    DataSourceConfigRequest,
    DataSourceGrouping,
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
from ..setup import ConfigApiResponse, _sanitize_datasource_configs

@router.get("/datasource", response_model=ConfigApiResponse)
async def get_data_source_configs(current_user: User = Depends(get_current_user)):
    """获取所有数据源配置"""
    try:
        config = await config_service.get_system_config()
        if not config:
            return ok(data=[], message="获取数据源配置成功")
        return ok(
            data=_sanitize_datasource_configs(config.data_source_configs),
            message="获取数据源配置成功",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取数据源配置失败: {str(e)}",
        )


@router.put("/datasource/{name}", response_model=ConfigApiResponse)
async def update_data_source_config(
    name: str,
    request: DataSourceConfigRequest,
    current_user: User = Depends(get_current_user),
):
    """更新数据源配置"""
    try:
        # 获取当前配置
        config = await config_service.get_system_config()
        if not config:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="系统配置不存在")

        # 查找并更新数据源配置
        should_skip_api_key_update = getattr(importlib.import_module("app.utils.keys"), "should_skip_api_key_update")
        is_valid_api_key = getattr(importlib.import_module("app.utils.keys"), "is_valid_api_key")

        def _truncate_api_key(api_key: str, prefix_len: int = 6, suffix_len: int = 6) -> str:
            """截断 API Key 用于显示"""
            if not api_key or len(api_key) <= prefix_len + suffix_len:
                return api_key
            return f"{api_key[:prefix_len]}...{api_key[-suffix_len:]}"

        for i, ds_config in enumerate(config.data_source_configs):
            if ds_config.name == name:
                # 更新配置
                # 🔥 修改：处理 API Key 的更新逻辑（与大模型厂家管理逻辑一致）
                _req = request.model_dump()

                # 处理 API Key
                if "api_key" in _req:
                    api_key = _req.get("api_key")
                    logger.info(
                        f"🔍 [API Key 验证] 收到的 API Key: {repr(api_key)} (类型: {type(api_key).__name__}, 长度: {len(api_key) if api_key else 0})"
                    )

                    # 如果是 None 或空字符串，保留原值（不更新）
                    if api_key is None or api_key == "":
                        logger.info("⏭️  [API Key 验证] None 或空字符串，保留原值")
                        _req["api_key"] = ds_config.api_key or ""
                    # 🔥 如果包含 "..."（截断标记），需要验证是否是未修改的原值
                    elif api_key and "..." in api_key:
                        logger.info("🔍 [API Key 验证] 检测到截断标记，验证是否与数据库原值匹配")

                        # 对数据库中的完整 API Key 进行相同的截断处理
                        if ds_config.api_key:
                            truncated_db_key = _truncate_api_key(ds_config.api_key)
                            logger.info(f"🔍 [API Key 验证] 数据库原值截断后: {truncated_db_key}")
                            logger.info(f"🔍 [API Key 验证] 收到的值: {api_key}")

                            # 比较截断后的值
                            if api_key == truncated_db_key:
                                # 相同，说明用户没有修改，保留数据库中的完整值
                                logger.info("✅ [API Key 验证] 截断值匹配，保留数据库原值")
                                _req["api_key"] = ds_config.api_key
                            else:
                                # 不同，说明用户修改了但修改得不完整
                                logger.error("❌ [API Key 验证] 截断值不匹配，用户可能修改了不完整的密钥")
                                raise HTTPException(
                                    status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="API Key 格式错误：检测到截断标记但与数据库中的值不匹配，请输入完整的 API Key",
                                )
                        else:
                            # 数据库中没有原值，但前端发送了截断值，这是不合理的
                            logger.error("❌ [API Key 验证] 数据库中没有原值，但收到了截断值")
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="API Key 格式错误：请输入完整的 API Key",
                            )
                    # 如果是占位符，则不更新（保留原值）
                    elif should_skip_api_key_update(api_key):
                        logger.info("⏭️  [API Key 验证] 跳过更新（占位符），保留原值")
                        _req["api_key"] = ds_config.api_key or ""
                    # 如果是新输入的密钥，必须验证有效性
                    elif not is_valid_api_key(api_key):
                        logger.error(f"❌ [API Key 验证] 验证失败: '{api_key}' (长度: {len(api_key)})")
                        logger.error(f"   - 长度检查: {len(api_key)} > 10? {len(api_key) > 10}")
                        logger.error(
                            f"   - 占位符前缀检查: startswith('your_')? {api_key.startswith('your_')}, startswith('your-')? {api_key.startswith('your-')}"
                        )
                        logger.error(
                            f"   - 占位符后缀检查: endswith('_here')? {api_key.endswith('_here')}, endswith('-here')? {api_key.endswith('-here')}"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"API Key 无效：长度必须大于 10 个字符，且不能是占位符（当前长度: {len(api_key)}）",
                        )
                    else:
                        logger.info(f"✅ [API Key 验证] 验证通过，将更新密钥 (长度: {len(api_key)})")
                    # 有效的完整密钥，保留（表示更新）

                # 处理 API Secret
                if "api_secret" in _req:
                    api_secret = _req.get("api_secret")
                    logger.info(
                        f"🔍 [API Secret 验证] 收到的 API Secret: {repr(api_secret)} (类型: {type(api_secret).__name__}, 长度: {len(api_secret) if api_secret else 0})"
                    )

                    # 如果是 None 或空字符串，保留原值（不更新）
                    if api_secret is None or api_secret == "":
                        logger.info("⏭️  [API Secret 验证] None 或空字符串，保留原值")
                        _req["api_secret"] = ds_config.api_secret or ""
                    # 🔥 如果包含 "..."（截断标记），需要验证是否是未修改的原值
                    elif api_secret and "..." in api_secret:
                        logger.info("🔍 [API Secret 验证] 检测到截断标记，验证是否与数据库原值匹配")

                        # 对数据库中的完整 API Secret 进行相同的截断处理
                        if ds_config.api_secret:
                            truncated_db_secret = _truncate_api_key(ds_config.api_secret)
                            logger.info(f"🔍 [API Secret 验证] 数据库原值截断后: {truncated_db_secret}")
                            logger.info(f"🔍 [API Secret 验证] 收到的值: {api_secret}")

                            # 比较截断后的值
                            if api_secret == truncated_db_secret:
                                # 相同，说明用户没有修改，保留数据库中的完整值
                                logger.info("✅ [API Secret 验证] 截断值匹配，保留数据库原值")
                                _req["api_secret"] = ds_config.api_secret
                            else:
                                # 不同，说明用户修改了但修改得不完整
                                logger.error("❌ [API Secret 验证] 截断值不匹配，用户可能修改了不完整的密钥")
                                raise HTTPException(
                                    status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="API Secret 格式错误：检测到截断标记但与数据库中的值不匹配，请输入完整的 API Secret",
                                )
                        else:
                            # 数据库中没有原值，但前端发送了截断值，这是不合理的
                            logger.error("❌ [API Secret 验证] 数据库中没有原值，但收到了截断值")
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="API Secret 格式错误：请输入完整的 API Secret",
                            )
                    # 如果是占位符，则不更新（保留原值）
                    elif should_skip_api_key_update(api_secret):
                        logger.info("⏭️  [API Secret 验证] 跳过更新（占位符），保留原值")
                        _req["api_secret"] = ds_config.api_secret or ""
                    # 如果是新输入的密钥，必须验证有效性
                    elif not is_valid_api_key(api_secret):
                        logger.error(f"❌ [API Secret 验证] 验证失败: '{api_secret}' (长度: {len(api_secret)})")
                        logger.error(f"   - 长度检查: {len(api_secret)} > 10? {len(api_secret) > 10}")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"API Secret 无效：长度必须大于 10 个字符，且不能是占位符（当前长度: {len(api_secret)}）",
                        )
                    else:
                        logger.info(f"✅ [API Secret 验证] 验证通过，将更新密钥 (长度: {len(api_secret)})")

                updated_config = DataSourceConfig(**_req)
                config.data_source_configs[i] = updated_config

                success = await config_service.save_system_config(config)
                if success:
                    # 🆕 同步市场分类关系
                    new_categories = set(_req.get("market_categories", []))

                    # 获取当前的分组关系
                    current_groupings = await config_service.get_datasource_groupings()
                    current_categories = set(
                        g.market_category_id for g in current_groupings if g.data_source_name == name
                    )

                    # 需要添加的分类
                    to_add = new_categories - current_categories
                    for category_id in to_add:
                        try:
                            grouping = DataSourceGrouping(
                                data_source_name=name,
                                market_category_id=category_id,
                                priority=updated_config.priority,
                                enabled=updated_config.enabled,
                            )
                            await config_service.add_datasource_to_category(grouping)
                        except Exception as e:
                            logger.warning(f"添加数据源分组失败: {str(e)}")

                    # 需要删除的分类
                    to_remove = current_categories - new_categories
                    for category_id in to_remove:
                        try:
                            await config_service.remove_datasource_from_category(name, category_id)
                        except Exception as e:
                            logger.warning(f"删除数据源分组失败: {str(e)}")

                    # 审计日志（忽略异常）
                    try:
                        await log_operation(
                            user_id=str(getattr(current_user, "id", "")),
                            username=getattr(current_user, "username", "unknown"),
                            action_type=ActionType.CONFIG_MANAGEMENT,
                            action="update_data_source_config",
                            details={
                                "name": name,
                                "market_categories": list(new_categories),
                            },
                            success=True,
                        )
                    except Exception:
                        pass
                    return ok(
                        data={"message": "数据源配置更新成功"},
                        message="数据源配置更新成功",
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="数据源配置更新失败",
                    )

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据源配置不存在")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新数据源配置失败: {str(e)}",
        )


@router.delete("/datasource/{name}", response_model=ConfigApiResponse)
async def delete_data_source_config(name: str, current_user: User = Depends(get_current_user)):
    """删除数据源配置"""
    try:
        # 获取当前配置
        config = await config_service.get_system_config()
        if not config:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="系统配置不存在")

        # 查找并删除数据源配置
        for i, ds_config in enumerate(config.data_source_configs):
            if ds_config.name == name:
                config.data_source_configs.pop(i)

                success = await config_service.save_system_config(config)
                if success:
                    # 审计日志（忽略异常）
                    try:
                        await log_operation(
                            user_id=str(getattr(current_user, "id", "")),
                            username=getattr(current_user, "username", "unknown"),
                            action_type=ActionType.CONFIG_MANAGEMENT,
                            action="delete_data_source_config",
                            details={"name": name},
                            success=True,
                        )
                    except Exception:
                        pass
                    return ok(
                        data={"message": "数据源配置删除成功"},
                        message="数据源配置删除成功",
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="数据源配置删除失败",
                    )

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据源配置不存在")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除数据源配置失败: {str(e)}",
        )


# ==================== 市场分类管理 ====================
