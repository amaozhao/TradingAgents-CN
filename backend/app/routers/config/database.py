# ruff: noqa: F401,F403,F405,F821
@router.get("/database", response_model=ConfigApiResponse)
async def get_database_configs(current_user: dict = Depends(get_current_user)):
    """获取所有数据库配置"""
    try:
        logger.info("🔄 获取数据库配置列表...")
        configs = await config_service.get_database_configs()
        logger.info(f"✅ 获取到 {len(configs)} 个数据库配置")
        return ok(data=configs, message="获取数据库配置成功")
    except Exception as e:
        logger.error(f"❌ 获取数据库配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取数据库配置失败: {str(e)}",
        )


@router.get("/database/{db_name}", response_model=ConfigApiResponse)
async def get_database_config(
    db_name: str, current_user: dict = Depends(get_current_user)
):
    """获取指定的数据库配置"""
    try:
        logger.info(f"🔄 获取数据库配置: {db_name}")
        config = await config_service.get_database_config(db_name)

        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"数据库配置 '{db_name}' 不存在",
            )

        return ok(data=config, message="获取数据库配置成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取数据库配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取数据库配置失败: {str(e)}",
        )


@router.post(
    "/database", response_model=ConfigApiResponse, operation_id="add_database_config"
)
async def add_database_config(
    request: DatabaseConfigRequest, current_user: dict = Depends(get_current_user)
):
    """添加数据库配置"""
    try:
        logger.info(f"➕ 添加数据库配置: {request.name}")

        # 转换为 DatabaseConfig 对象
        db_config = DatabaseConfig(**request.model_dump())

        # 添加配置
        success = await config_service.add_database_config(db_config)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="添加数据库配置失败，可能已存在同名配置",
            )

        # 记录操作日志
        await log_operation(
            user_id=current_user["id"],
            username=current_user.get("username", "unknown"),
            action_type=ActionType.CONFIG_MANAGEMENT,
            action=f"添加数据库配置: {request.name}",
            details={
                "name": request.name,
                "type": request.type,
                "host": request.host,
                "port": request.port,
            },
        )

        return ok(
            data={"success": True, "message": "数据库配置添加成功"},
            message="数据库配置添加成功",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 添加数据库配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加数据库配置失败: {str(e)}",
        )


@router.put("/database/{db_name}", response_model=ConfigApiResponse)
async def update_database_config(
    db_name: str,
    request: DatabaseConfigRequest,
    current_user: dict = Depends(get_current_user),
):
    """更新数据库配置"""
    try:
        logger.info(f"🔄 更新数据库配置: {db_name}")

        # 检查名称是否匹配
        if db_name != request.name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="URL中的名称与请求体中的名称不匹配",
            )

        # 转换为 DatabaseConfig 对象
        db_config = DatabaseConfig(**request.model_dump())

        # 更新配置
        success = await config_service.update_database_config(db_config)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"数据库配置 '{db_name}' 不存在",
            )

        # 记录操作日志
        await log_operation(
            user_id=current_user["id"],
            username=current_user.get("username", "unknown"),
            action_type=ActionType.CONFIG_MANAGEMENT,
            action=f"更新数据库配置: {db_name}",
            details={
                "name": request.name,
                "type": request.type,
                "host": request.host,
                "port": request.port,
            },
        )

        return ok(
            data={"success": True, "message": "数据库配置更新成功"},
            message="数据库配置更新成功",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 更新数据库配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新数据库配置失败: {str(e)}",
        )


@router.delete("/database/{db_name}", response_model=ConfigApiResponse)
async def delete_database_config(
    db_name: str, current_user: dict = Depends(get_current_user)
):
    """删除数据库配置"""
    try:
        logger.info(f"🗑️ 删除数据库配置: {db_name}")

        # 删除配置
        success = await config_service.delete_database_config(db_name)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"数据库配置 '{db_name}' 不存在",
            )

        # 记录操作日志
        await log_operation(
            user_id=current_user["id"],
            username=current_user.get("username", "unknown"),
            action_type=ActionType.CONFIG_MANAGEMENT,
            action=f"删除数据库配置: {db_name}",
            details={"name": db_name},
        )

        return ok(
            data={"success": True, "message": "数据库配置删除成功"},
            message="数据库配置删除成功",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 删除数据库配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除数据库配置失败: {str(e)}",
        )
