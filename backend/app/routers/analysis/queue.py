from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .imports import (
        BatchRepository,
        Depends,
        HTTPException,
        Optional,
        Query,
        QueueService,
        get_current_user,
        get_queue_service,
        get_simple_analysis_service,
        importlib,
        router,
    )
    from .setup import (
        AnalysisDataResponse,
        AnalysisLooseObjectResponse,
        AnalysisOperationResponse,
        AnalysisQueueBatchResponse,
        AnalysisQueueTaskResponse,
        BatchAnalyzeRequest,
        SingleAnalyzeRequest,
    )

@router.post("/analyze", response_model=AnalysisQueueTaskResponse)
async def analyze_single(
    req: SingleAnalyzeRequest,
    user: dict = Depends(get_current_user),
    svc: QueueService = Depends(get_queue_service),
):
    """个股分析（兼容性端点）"""
    try:
        task_id = await svc.enqueue_task(user_id=user["id"], symbol=req.symbol, params=req.parameters)
        return {"task_id": task_id, "status": "queued"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/analyze/batch", response_model=AnalysisQueueBatchResponse)
async def analyze_batch(
    req: BatchAnalyzeRequest,
    user: dict = Depends(get_current_user),
    svc: QueueService = Depends(get_queue_service),
):
    """批量分析（兼容性端点）"""
    try:
        batch_id, submitted = await svc.create_batch(user_id=user["id"], symbols=req.symbols, params=req.parameters)
        return {"batch_id": batch_id, "submitted": submitted}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/batches/{batch_id}", response_model=AnalysisLooseObjectResponse)
async def get_batch(
    batch_id: str,
    user: dict = Depends(get_current_user),
    svc: QueueService = Depends(get_queue_service),
):
    batch = await BatchRepository().get_batch(batch_id, user["id"])
    if batch is not None:
        return batch
    b = await svc.get_batch(batch_id)
    if not b or b.get("user") != user["id"]:
        raise HTTPException(status_code=404, detail="batch not found")
    return b


# 任务和批次查询端点
# 注意：这个路由被移到了 /tasks/{task_id}/status 之后，避免路由冲突
# @router.get("/tasks/{task_id}")
# async def get_task(
#     task_id: str,
#     user: dict = Depends(get_current_user),
#     svc: QueueService = Depends(get_queue_service)
# ):
#     """获取任务详情"""
#     t = await svc.get_task(task_id)
#     if not t or t.get("user") != user["id"]:
#         raise HTTPException(status_code=404, detail="任务不存在")
#     return t

# 原有的路由已被新的异步实现替代
# @router.get("/tasks/{task_id}/status")
# async def get_task_status_old(
#     task_id: str,
#     user: dict = Depends(get_current_user)
# ):
#     """获取任务状态和进度（旧版实现）"""
#     try:
#         status = await get_analysis_service().get_task_status(task_id)
#         if not status:
#             raise HTTPException(status_code=404, detail="任务不存在")
#         return {
#             "success": True,
#             "data": status
#         }
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/cancel", response_model=AnalysisOperationResponse)
async def cancel_task(
    task_id: str,
    user: dict = Depends(get_current_user),
    svc: QueueService = Depends(get_queue_service),
):
    """取消任务"""
    try:
        # 验证任务所有权
        task = await svc.get_task(task_id)
        if not task or task.get("user") != user["id"]:
            raise HTTPException(status_code=404, detail="任务不存在")

        success = await svc.cancel_task(task_id)
        if success:
            return {"success": True, "message": "任务已取消"}
        else:
            raise HTTPException(status_code=400, detail="取消任务失败")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/user/queue-status", response_model=AnalysisDataResponse)
async def get_user_queue_status(
    user: dict = Depends(get_current_user),
    svc: QueueService = Depends(get_queue_service),
):
    """获取用户队列状态"""
    try:
        status = await svc.get_user_queue_status(user["id"])
        return {"success": True, "data": status}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/user/history", response_model=AnalysisDataResponse)
async def get_user_analysis_history(
    user: dict = Depends(get_current_user),
    status: Optional[str] = Query(None, description="任务状态过滤"),
    start_date: Optional[str] = Query(None, description="开始日期，YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，YYYY-MM-DD"),
    symbol: Optional[str] = Query(None, description="股票代码"),
    stock_code: Optional[str] = Query(None, description="股票代码(已废弃,使用symbol)"),
    batch_id: Optional[str] = Query(None, description="批次ID"),
    market_type: Optional[str] = Query(None, description="市场类型"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
):
    """获取用户分析历史（支持基础筛选与分页）"""
    try:
        # 先获取用户任务列表（内存优先，PostgreSQL兜底）
        raw_tasks = await get_simple_analysis_service().list_user_tasks(
            user_id=user["id"],
            status=status,
            limit=page_size,
            offset=(page - 1) * page_size,
            batch_id=batch_id,
        )

        # 进行基础筛选
        datetime = getattr(importlib.import_module("datetime"), "datetime")

        def in_date_range(t: Optional[str]) -> bool:
            if not t:
                return True
            try:
                dt = datetime.fromisoformat(t.replace("Z", "+00:00")) if "Z" in t else datetime.fromisoformat(t)
            except Exception:
                return True
            ok = True
            if start_date:
                try:
                    ok = ok and (dt.date() >= datetime.fromisoformat(start_date).date())
                except Exception:
                    pass
            if end_date:
                try:
                    ok = ok and (dt.date() <= datetime.fromisoformat(end_date).date())
                except Exception:
                    pass
            return ok

        # 获取查询的股票代码 (兼容旧字段)
        query_symbol = symbol or stock_code

        filtered = []
        for x in raw_tasks:
            if query_symbol:
                task_symbol = x.get("symbol") or x.get("stock_code") or x.get("stock_symbol")
                if task_symbol not in [query_symbol]:
                    continue
            # 市场类型暂时从参数内判断（如有）
            if market_type:
                params = x.get("parameters") or {}
                if params.get("market_type") != market_type:
                    continue
            # 时间范围（使用 start_time 或 created_at）
            t = x.get("start_time") or x.get("created_at")
            if not in_date_range(t):
                continue
            filtered.append(x)

        return {
            "success": True,
            "data": {
                "tasks": filtered,
                "total": len(filtered),
                "page": page,
                "page_size": page_size,
            },
            "message": "历史查询成功",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
