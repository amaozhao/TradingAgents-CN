from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .imports import (
        ActionType,
        ConfigTestRequest,
        ConfigTestResponse,
        DataSourceConfig,
        DataSourceConfigRequest,
        DataSourceGrouping,
        DatabaseConfig,
        DatabaseConfigRequest,
        Depends,
        HTTPException,
        LLMConfig,
        LLMConfigRequest,
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
    from .setup import ConfigApiResponse, require_admin_user

@router.post("/llm", response_model=ConfigApiResponse)
async def add_llm_config(request: LLMConfigRequest, current_user: User = Depends(get_current_user)):
    """添加或更新大模型配置"""
    require_admin_user(current_user)
    try:
        logger.info("🔧 添加/更新大模型配置开始")
        logger.info(f"📊 请求数据: {request.model_dump()}")
        logger.info(f"🏷️ 厂家: {request.provider}, 模型: {request.model_name}")

        # 创建LLM配置
        llm_config_data = request.model_dump()
        logger.info(f"📋 原始配置数据: {llm_config_data}")

        # 如果没有提供API密钥，从厂家配置中获取
        if not llm_config_data.get("api_key"):
            logger.info(f"🔑 API密钥为空，从厂家配置获取: {request.provider}")

            # 获取厂家配置
            providers = await config_service.get_llm_providers()
            logger.info(f"📊 找到 {len(providers)} 个厂家配置")

            for p in providers:
                logger.info(f"   - 厂家: {p.name}, 有API密钥: {bool(p.api_key)}")

            provider_config = next((p for p in providers if p.name == request.provider), None)

            if provider_config:
                logger.info(f"✅ 找到厂家配置: {provider_config.name}")
                if provider_config.api_key:
                    llm_config_data["api_key"] = provider_config.api_key
                    logger.info(f"✅ 成功获取厂家API密钥 (长度: {len(provider_config.api_key)})")
                else:
                    logger.warning(f"⚠️ 厂家 {request.provider} 没有配置API密钥")
                    llm_config_data["api_key"] = ""
            else:
                logger.warning(f"⚠️ 未找到厂家 {request.provider} 的配置")
                llm_config_data["api_key"] = ""
        else:
            logger.info(f"🔑 使用提供的API密钥 (长度: {len(llm_config_data.get('api_key', ''))})")

        logger.info(f"📋 最终配置数据: {llm_config_data}")
        # 🔥 修改：允许通过 REST 写入密钥，但如果是无效的密钥则清空
        # 无效的密钥：空字符串、占位符（your_xxx）、长度不够
        if "api_key" in llm_config_data:
            api_key = llm_config_data.get("api_key", "")
            # 如果是无效的 Key，则清空（让系统使用环境变量）
            if not api_key or api_key.startswith("your_") or api_key.startswith("your-") or len(api_key) <= 10:
                llm_config_data["api_key"] = ""

        # 尝试创建LLMConfig对象
        try:
            llm_config = LLMConfig(**llm_config_data)
            logger.info("✅ LLMConfig对象创建成功")
        except Exception as e:
            logger.error(f"❌ LLMConfig对象创建失败: {e}")
            logger.error(f"📋 失败的数据: {llm_config_data}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"配置数据验证失败: {str(e)}",
            )

        # 保存配置
        success = await config_service.update_llm_config(llm_config)

        if success:
            logger.info(f"✅ 大模型配置更新成功: {llm_config.provider}/{llm_config.model_name}")

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
                    action="update_llm_config",
                    details={
                        "provider": llm_config.provider,
                        "model_name": llm_config.model_name,
                    },
                    success=True,
                )
            except Exception:
                pass
            return ok(
                data={
                    "message": "大模型配置更新成功",
                    "model_name": llm_config.model_name,
                },
                message="大模型配置更新成功",
            )
        else:
            logger.error("❌ 大模型配置保存失败")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="大模型配置更新失败",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 添加大模型配置异常: {e}")
        traceback = importlib.import_module("traceback")
        logger.error(f"📋 异常堆栈: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加大模型配置失败: {str(e)}",
        )


@router.post("/datasource", response_model=ConfigApiResponse)
async def add_data_source_config(request: DataSourceConfigRequest, current_user: User = Depends(get_current_user)):
    """添加数据源配置"""
    try:
        # 开源版本：所有用户都可以修改配置

        # 获取当前配置
        config = await config_service.get_system_config()
        if not config:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="系统配置不存在")

        # 添加新的数据源配置
        # 🔥 修改：支持保存 API Key（与大模型厂家管理逻辑一致）
        should_skip_api_key_update = getattr(importlib.import_module("app.utils.keys"), "should_skip_api_key_update")
        is_valid_api_key = getattr(importlib.import_module("app.utils.keys"), "is_valid_api_key")

        _req = request.model_dump()

        # 处理 API Key
        if "api_key" in _req:
            api_key = _req.get("api_key", "")
            # 如果是占位符或截断的密钥，清空该字段
            if should_skip_api_key_update(api_key):
                _req["api_key"] = ""
            # 如果是空字符串，保留（表示使用环境变量）
            elif api_key == "":
                _req["api_key"] = ""
            # 如果是新输入的密钥，必须验证有效性
            elif not is_valid_api_key(api_key):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="API Key 无效：长度必须大于 10 个字符，且不能是占位符",
                )
            # 有效的完整密钥，保留

        # 处理 API Secret
        if "api_secret" in _req:
            api_secret = _req.get("api_secret", "")
            if should_skip_api_key_update(api_secret):
                _req["api_secret"] = ""
            # 如果是空字符串，保留
            elif api_secret == "":
                _req["api_secret"] = ""
            # 如果是新输入的密钥，必须验证有效性
            elif not is_valid_api_key(api_secret):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="API Secret 无效：长度必须大于 10 个字符，且不能是占位符",
                )

        ds_config = DataSourceConfig(**_req)
        config.data_source_configs.append(ds_config)

        success = await config_service.save_system_config(config)
        if success:
            # 🆕 自动创建数据源分组关系
            market_categories = _req.get("market_categories", [])
            if market_categories:
                for category_id in market_categories:
                    try:
                        grouping = DataSourceGrouping(
                            data_source_name=ds_config.name,
                            market_category_id=category_id,
                            priority=ds_config.priority,
                            enabled=ds_config.enabled,
                        )
                        await config_service.add_datasource_to_category(grouping)
                    except Exception as e:
                        # 如果分组已存在或其他错误，记录但不影响主流程
                        logger.warning(f"自动创建数据源分组失败: {str(e)}")

            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="add_data_source_config",
                    details={
                        "name": ds_config.name,
                        "market_categories": market_categories,
                    },
                    success=True,
                )
            except Exception:
                pass
            return ok(
                data={"message": "数据源配置添加成功", "name": ds_config.name},
                message="数据源配置添加成功",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="数据源配置添加失败",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加数据源配置失败: {str(e)}",
        )


@router.post(
    "/database",
    response_model=ConfigApiResponse,
    operation_id="add_database_config_legacy",
)
async def add_database_config_legacy(request: DatabaseConfigRequest, current_user: User = Depends(get_current_user)):
    """添加数据库配置"""
    try:
        # 开源版本：所有用户都可以修改配置

        # 获取当前配置
        config = await config_service.get_system_config()
        if not config:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="系统配置不存在")

        # 添加新的数据库配置（方案A：清洗敏感字段）
        _req = request.model_dump()
        _req["password"] = ""
        db_config = DatabaseConfig(**_req)
        config.database_configs.append(db_config)

        success = await config_service.save_system_config(config)
        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="add_database_config",
                    details={"name": db_config.name},
                    success=True,
                )
            except Exception:
                pass
            return ok(
                data={
                    "success": True,
                    "message": "数据库配置添加成功",
                    "name": db_config.name,
                },
                message="数据库配置添加成功",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="数据库配置添加失败",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加数据库配置失败: {str(e)}",
        )


@router.post("/test", response_model=ConfigApiResponse)
async def test_config(request: ConfigTestRequest, current_user: User = Depends(get_current_user)):
    """测试配置连接"""
    try:
        if request.config_type == "llm":
            llm_config = LLMConfig(**request.config_data)
            result = await config_service.test_llm_config(llm_config)
        elif request.config_type == "datasource":
            ds_config = DataSourceConfig(**request.config_data)
            result = await config_service.test_data_source_config(ds_config)
        elif request.config_type == "database":
            db_config = DatabaseConfig(**request.config_data)
            result = await config_service.test_database_config(db_config)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的配置类型")

        response = ConfigTestResponse(**result)
        return ok(data=response.model_dump(), message=response.message)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"测试配置失败: {str(e)}",
        )


@router.post("/database/{db_name}/test", response_model=ConfigApiResponse)
async def test_saved_database_config(db_name: str, current_user: dict = Depends(get_current_user)):
    """测试已保存的数据库配置（从数据库中获取完整配置包括密码）"""
    try:
        logger.info(f"🧪 测试已保存的数据库配置: {db_name}")

        # 从数据库获取完整的系统配置
        config = await config_service.get_system_config()
        if not config:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="系统配置不存在")

        # 查找指定的数据库配置
        db_config = None
        for db in config.database_configs:
            if db.name == db_name:
                db_config = db
                break

        if not db_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"数据库配置 '{db_name}' 不存在",
            )

        logger.info(f"✅ 找到数据库配置: {db_config.name} ({db_config.type})")
        logger.info(f"📍 连接信息: {db_config.host}:{db_config.port}")
        logger.info(f"🔐 用户名: {db_config.username or '(无)'}")
        logger.info(f"🔐 密码: {'***' if db_config.password else '(无)'}")

        # 使用完整配置进行测试
        result = await config_service.test_database_config(db_config)

        response = ConfigTestResponse(**result)
        return ok(data=response.model_dump(), message=response.message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 测试数据库配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"测试数据库配置失败: {str(e)}",
        )
