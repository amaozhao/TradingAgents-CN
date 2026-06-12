from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .imports import (
        ApiResponse,
        BatchAnalysisRequest,
        BatchStockWorkflow,
        Depends,
        HTTPException,
        Optional,
        Query,
        ResearchPrincipal,
        ToolExecutionContext,
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

        tasks = await get_simple_analysis_service().list_all_tasks(status=status, limit=limit, offset=offset)

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


@router.post("/batch", response_model=ApiResponse)
async def submit_batch_analysis(request: BatchAnalysisRequest, user: dict = Depends(get_current_user)):
    """提交批量分析任务 - 只提交 workflow，不在 FastAPI 进程内执行完整分析"""
    try:
        logger.info(f"🎯 [批量分析] 收到批量分析请求: title={request.title}")
        result = await _submit_batch_via_workflow(request, user)
        task_ids = result.get("task_ids") or []

        return {
            "success": True,
            "data": {
                "batch_id": result.get("batch_id"),
                "total_tasks": len(task_ids),
                "task_ids": task_ids,
                "mapping": result.get("mapping") or [],
                "status": result.get("status") or "submitted",
            },
            "message": f"批量分析任务已提交，共{len(task_ids)}个股票",
        }
    except Exception as e:
        logger.error(f"❌ [批量分析] 提交失败: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


async def _submit_batch_via_workflow(
    request: BatchAnalysisRequest,
    user: dict[str, object],
) -> dict[str, object]:
    payload = request.model_dump(exclude_none=True)
    payload["wait_for_completion"] = False
    principal = ResearchPrincipal.from_user(user, session_id=None)
    context = ToolExecutionContext(principal=principal, session_id=None)
    return await BatchStockWorkflow(tool_name="batch_stock_analysis").submit(
        context,
        payload,
    )
