from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .imports import (
        ActionType,
        DataSourceGrouping,
        DataSourceGroupingRequest,
        DataSourceOrderRequest,
        Depends,
        HTTPException,
        MarketCategory,
        MarketCategoryRequest,
        User,
        config_service,
        get_current_user,
        log_operation,
        ok,
        router,
        status,
    )
    from .setup import (
        ConfigApiResponse,
        DataSourceGroupingUpdateRequest,
        MarketCategoryUpdateRequest,
    )


@router.get("/market-categories", response_model=ConfigApiResponse)
async def get_market_categories(current_user: User = Depends(get_current_user)):
    """获取所有市场分类"""
    try:
        categories = await config_service.get_market_categories()
        return ok(data=categories, message="获取市场分类成功")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取市场分类失败",
        )


@router.post("/market-categories", response_model=ConfigApiResponse)
async def add_market_category(
    request: MarketCategoryRequest, current_user: User = Depends(get_current_user)
):
    """添加市场分类"""
    try:
        category = MarketCategory(**request.model_dump())
        success = await config_service.add_market_category(category)

        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="add_market_category",
                    details={"id": str(getattr(category, "id", ""))},
                    success=True,
                )
            except Exception:
                pass
            return ok(
                data={"message": "市场分类添加成功", "id": category.id},
                message="市场分类添加成功",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="市场分类ID已存在"
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="添加市场分类失败",
        )


@router.put("/market-categories/{category_id}", response_model=ConfigApiResponse)
async def update_market_category(
    category_id: str,
    request: MarketCategoryUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    """更新市场分类"""
    try:
        request_data = request.model_dump(exclude_unset=True)
        success = await config_service.update_market_category(category_id, request_data)

        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="update_market_category",
                    details={
                        "category_id": category_id,
                        "changed_keys": list(request_data.keys()),
                    },
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "市场分类更新成功"}, message="市场分类更新成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="市场分类不存在"
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新市场分类失败",
        )


@router.delete("/market-categories/{category_id}", response_model=ConfigApiResponse)
async def delete_market_category(
    category_id: str, current_user: User = Depends(get_current_user)
):
    """删除市场分类"""
    try:
        success = await config_service.delete_market_category(category_id)

        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="delete_market_category",
                    details={"category_id": category_id},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "市场分类删除成功"}, message="市场分类删除成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法删除分类，可能还有数据源使用此分类",
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除市场分类失败",
        )


# ==================== 数据源分组管理 ====================


@router.get("/datasource-groupings", response_model=ConfigApiResponse)
async def get_datasource_groupings(current_user: User = Depends(get_current_user)):
    """获取所有数据源分组关系"""
    try:
        groupings = await config_service.get_datasource_groupings()
        return ok(data=groupings, message="获取数据源分组关系成功")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取数据源分组关系失败",
        )


@router.post("/datasource-groupings", response_model=ConfigApiResponse)
async def add_datasource_to_category(
    request: DataSourceGroupingRequest, current_user: User = Depends(get_current_user)
):
    """将数据源添加到分类"""
    try:
        grouping = DataSourceGrouping(**request.model_dump())
        success = await config_service.add_datasource_to_category(grouping)

        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="add_datasource_to_category",
                    details={
                        "data_source_name": request.data_source_name,
                        "category_id": request.market_category_id,
                    },
                    success=True,
                )
            except Exception:
                pass
            return ok(
                data={"message": "数据源添加到分类成功"}, message="数据源添加到分类成功"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="数据源已在该分类中"
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="添加数据源到分类失败",
        )


@router.delete(
    "/datasource-groupings/{data_source_name}/{category_id}",
    response_model=ConfigApiResponse,
)
async def remove_datasource_from_category(
    data_source_name: str,
    category_id: str,
    current_user: User = Depends(get_current_user),
):
    """从分类中移除数据源"""
    try:
        success = await config_service.remove_datasource_from_category(
            data_source_name, category_id
        )

        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="remove_datasource_from_category",
                    details={
                        "data_source_name": data_source_name,
                        "category_id": category_id,
                    },
                    success=True,
                )
            except Exception:
                pass
            return ok(
                data={"message": "数据源从分类中移除成功"},
                message="数据源从分类中移除成功",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="数据源分组关系不存在"
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="从分类中移除数据源失败",
        )


@router.put(
    "/datasource-groupings/{data_source_name}/{category_id}",
    response_model=ConfigApiResponse,
)
async def update_datasource_grouping(
    data_source_name: str,
    category_id: str,
    request: DataSourceGroupingUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    """更新数据源分组关系"""
    try:
        request_data = request.model_dump(exclude_unset=True)
        success = await config_service.update_datasource_grouping(
            data_source_name, category_id, request_data
        )

        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="update_datasource_grouping",
                    details={
                        "data_source_name": data_source_name,
                        "category_id": category_id,
                        "changed_keys": list(request_data.keys()),
                    },
                    success=True,
                )
            except Exception:
                pass
            return ok(
                data={"message": "数据源分组关系更新成功"},
                message="数据源分组关系更新成功",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="数据源分组关系不存在"
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新数据源分组关系失败",
        )


@router.put(
    "/market-categories/{category_id}/datasource-order",
    response_model=ConfigApiResponse,
)
async def update_category_datasource_order(
    category_id: str,
    request: DataSourceOrderRequest,
    current_user: User = Depends(get_current_user),
):
    """更新分类中数据源的排序"""
    try:
        success = await config_service.update_category_datasource_order(
            category_id, request.data_sources
        )

        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="update_category_datasource_order",
                    details={
                        "category_id": category_id,
                        "data_sources": request.data_sources,
                    },
                    success=True,
                )
            except Exception:
                pass
            return ok(
                data={"message": "数据源排序更新成功"}, message="数据源排序更新成功"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="数据源排序更新失败",
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新数据源排序失败",
        )
