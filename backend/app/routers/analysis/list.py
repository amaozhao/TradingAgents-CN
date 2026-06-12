from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .imports import (
        ApiResponse,
        Depends,
        HTTPException,
        Optional,
        Query,
        get_current_user,
        get_simple_analysis_service,
        logger,
        router,
    )


@router.get("/tasks/all", response_model=ApiResponse)
async def list_all_tasks(
    user: dict = Depends(get_current_user),
    status: Optional[str] = Query(None, description="任务状态过滤"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """获取所有任务列表（不限用户）"""
    try:
        logger.info("📋 查询所有任务列表")

        tasks = await get_simple_analysis_service().list_all_tasks(
            status=status, limit=limit, offset=offset
        )

        return {
            "success": True,
            "data": {
                "tasks": tasks,
                "total": len(tasks),
                "limit": limit,
                "offset": offset,
            },
            "message": "任务列表获取成功",
        }

    except Exception as e:
        logger.error(f"❌ 获取任务列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks", response_model=ApiResponse)
async def list_user_tasks(
    user: dict = Depends(get_current_user),
    status: Optional[str] = Query(None, description="任务状态过滤"),
    batch_id: Optional[str] = Query(None, description="批次ID过滤"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """获取用户的任务列表"""
    try:
        logger.info(f"📋 查询用户任务列表: {user['id']}")

        tasks = await get_simple_analysis_service().list_user_tasks(
            user_id=user["id"],
            status=status,
            limit=limit,
            offset=offset,
            batch_id=batch_id,
        )

        return {
            "success": True,
            "data": {
                "tasks": tasks,
                "total": len(tasks),
                "limit": limit,
                "offset": offset,
            },
            "message": "任务列表获取成功",
        }

    except Exception as e:
        logger.error(f"❌ 获取任务列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
