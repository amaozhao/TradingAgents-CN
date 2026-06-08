# ruff: noqa: F401,F403,F405,F821
@router.post("/default/llm", response_model=ConfigApiResponse)
async def set_default_llm(
    request: SetDefaultRequest, current_user: User = Depends(get_current_user)
):
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
                data={"message": f"默认大模型已设置为: {request.name}"},
                message=f"默认大模型已设置为: {request.name}",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="设置默认大模型失败，请检查模型名称是否正确",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"设置默认大模型失败: {str(e)}",
        )


@router.post("/default/datasource", response_model=ConfigApiResponse)
async def set_default_data_source(
    request: SetDefaultRequest, current_user: User = Depends(get_current_user)
):
    """设置默认数据源"""
    try:
        # 开源版本：所有用户都可以修改配置

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
                data={"message": f"默认数据源已设置为: {request.name}"},
                message=f"默认数据源已设置为: {request.name}",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="设置默认数据源失败，请检查数据源名称是否正确",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"设置默认数据源失败: {str(e)}",
        )


@router.get("/models", response_model=ConfigApiResponse)
async def get_available_models(current_user: User = Depends(get_current_user)):
    """获取可用的模型列表"""
    try:
        models = await config_service.get_available_models()
        return ok(data=models, message="获取模型列表成功")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模型列表失败: {str(e)}",
        )


# ========== 模型目录管理 ==========


def _current_user_value(current_user, key: str, default: str = ""):
    if isinstance(current_user, dict):
        return current_user.get(key, default)
    return getattr(current_user, key, default)


@router.get("/model-catalog", response_model=ConfigApiResponse)
async def get_model_catalog(current_user: User = Depends(get_current_user)):
    """获取所有模型目录"""
    try:
        catalogs = await config_service.get_model_catalog()
        return ok(
            data=[catalog.model_dump(by_alias=False) for catalog in catalogs],
            message="获取模型目录成功",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模型目录失败: {str(e)}",
        )


@router.get("/model-catalog/{provider}", response_model=ConfigApiResponse)
async def get_provider_model_catalog(
    provider: str, current_user: User = Depends(get_current_user)
):
    """获取指定厂家的模型目录"""
    try:
        catalog = await config_service.get_provider_models(provider)
        if not catalog:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到厂家 {provider} 的模型目录",
            )
        return ok(data=catalog.model_dump(by_alias=False), message="获取模型目录成功")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模型目录失败: {str(e)}",
        )


class ModelCatalogRequest(BaseModel):
    """模型目录请求"""

    provider: str
    provider_name: str
    models: List[Dict[str, Any]]


@router.post("/model-catalog", response_model=ConfigApiResponse)
async def save_model_catalog(
    request: ModelCatalogRequest, current_user: User = Depends(get_current_user)
):
    """保存或更新模型目录"""
    require_admin_user(current_user)
    try:
        logger.info(
            f"📝 收到保存模型目录请求: provider={request.provider}, models数量={len(request.models)}"
        )
        logger.info(f"📝 请求数据: {request.model_dump()}")

        # 转换为 ModelInfo 列表
        models = [ModelInfo(**m) for m in request.models]
        logger.info(f"✅ 成功转换 {len(models)} 个模型")

        catalog = ModelCatalog(
            provider=request.provider,
            provider_name=request.provider_name,
            models=models,
        )
        logger.info("✅ 创建 ModelCatalog 对象成功")

        success = await config_service.save_model_catalog(catalog)
        logger.info(f"💾 保存结果: {success}")

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="保存模型目录失败",
            )

        # 审计日志不应影响模型目录保存结果。
        try:
            await log_operation(
                user_id=str(_current_user_value(current_user, "id")),
                username=_current_user_value(current_user, "username", "unknown"),
                action_type=ActionType.CONFIG_MANAGEMENT,
                action="update_model_catalog",
                details={
                    "provider": request.provider,
                    "provider_name": request.provider_name,
                    "models_count": len(request.models),
                },
                success=True,
            )
        except Exception:
            pass

        return ok(
            data={"success": True, "message": "模型目录保存成功"},
            message="模型目录保存成功",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 保存模型目录失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"保存模型目录失败: {str(e)}",
        )


@router.delete("/model-catalog/{provider}", response_model=ConfigApiResponse)
async def delete_model_catalog(
    provider: str, current_user: User = Depends(get_current_user)
):
    """删除模型目录"""
    require_admin_user(current_user)
    try:
        success = await config_service.delete_model_catalog(provider)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到厂家 {provider} 的模型目录",
            )

        # 审计日志不应影响模型目录删除结果。
        try:
            await log_operation(
                user_id=str(_current_user_value(current_user, "id")),
                username=_current_user_value(current_user, "username", "unknown"),
                action_type=ActionType.CONFIG_MANAGEMENT,
                action="delete_model_catalog",
                details={"provider": provider},
                success=True,
            )
        except Exception:
            pass

        return ok(
            data={"success": True, "message": "模型目录删除成功"},
            message="模型目录删除成功",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除模型目录失败: {str(e)}",
        )


@router.post("/model-catalog/init", response_model=ConfigApiResponse)
async def init_model_catalog(current_user: User = Depends(get_current_user)):
    """初始化默认模型目录"""
    require_admin_user(current_user)
    try:
        success = await config_service.init_default_model_catalog()
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="初始化模型目录失败",
            )

        return ok(
            data={"success": True, "message": "模型目录初始化成功"},
            message="模型目录初始化成功",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"初始化模型目录失败: {str(e)}",
        )


# ===== 数据库配置管理端点 =====
