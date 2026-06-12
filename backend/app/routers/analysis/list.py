# ruff: noqa: F401,F403,F405,F821
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
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """获取用户的任务列表"""
    try:
        logger.info(f"📋 查询用户任务列表: {user['id']}")

        tasks = await get_simple_analysis_service().list_user_tasks(
            user_id=user["id"], status=status, limit=limit, offset=offset
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
async def submit_batch_analysis(
    request: BatchAnalysisRequest, user: dict = Depends(get_current_user)
):
    """提交批量分析任务 - 只入队，不在 FastAPI 进程内执行分析"""
    try:
        logger.info(f"🎯 [批量分析] 收到批量分析请求: title={request.title}")

        simple_service = get_simple_analysis_service()
        queue_service = get_queue_service()
        batch_id = str(uuid.uuid4())
        task_ids: List[str] = []
        mapping: List[Dict[str, str]] = []

        # 获取股票代码列表 (兼容旧字段)
        stock_symbols = request.get_symbols()
        logger.info(f"📊 [批量分析] 股票代码列表: {stock_symbols}")

        # 验证股票代码列表
        if not stock_symbols:
            raise ValueError("股票代码列表不能为空")

        # 🔧 限制批量分析的股票数量（最多10个）
        MAX_BATCH_SIZE = 10
        if len(stock_symbols) > MAX_BATCH_SIZE:
            raise ValueError(
                f"批量分析最多支持 {MAX_BATCH_SIZE} 个股票，当前提交了 {len(stock_symbols)} 个"
            )

        # 为每只股票创建个股分析任务
        for i, symbol in enumerate(stock_symbols):
            logger.info(
                f"📝 [批量分析] 正在创建第 {i + 1}/{len(stock_symbols)} 个任务: {symbol}"
            )

            single_req = SingleAnalysisRequest(
                symbol=symbol,
                stock_code=symbol,  # 兼容字段
                parameters=request.parameters,
            )

            try:
                create_res = await simple_service.create_analysis_task(
                    user["id"], single_req
                )
                task_id = create_res.get("task_id")
                if not task_id:
                    raise RuntimeError(f"创建任务失败：未返回task_id (symbol={symbol})")

                await queue_service.enqueue_task(
                    user_id=user["id"],
                    symbol=symbol,
                    params=_analysis_request_queue_params(
                        single_req, task_id, user["id"]
                    ),
                    batch_id=batch_id,
                    task_id=task_id,
                )
                task_ids.append(task_id)
                mapping.append(
                    {"symbol": symbol, "stock_code": symbol, "task_id": task_id}
                )
                logger.info(f"✅ [批量分析] 已创建并入队任务: {task_id} - {symbol}")
            except Exception as create_error:
                logger.error(
                    f"❌ [批量分析] 创建任务失败: {symbol}, 错误: {create_error}",
                    exc_info=True,
                )
                raise

        logger.info(f"🚀 [批量分析] 已提交 {len(task_ids)} 个任务到队列")

        return {
            "success": True,
            "data": {
                "batch_id": batch_id,
                "total_tasks": len(task_ids),
                "task_ids": task_ids,
                "mapping": mapping,
                "status": "submitted",
            },
            "message": f"批量分析任务已提交到队列，共{len(task_ids)}个股票",
        }
    except Exception as e:
        logger.error(f"❌ [批量分析] 提交失败: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
