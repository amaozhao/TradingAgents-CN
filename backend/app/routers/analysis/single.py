# ruff: noqa: F401,F403,F405,F821
@router.post("/single", response_model=ApiResponse)
async def submit_single_analysis(
    request: SingleAnalysisRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """提交单股分析任务 - 使用 BackgroundTasks 异步执行"""
    try:
        logger.info("🎯 收到单股分析请求")
        logger.info(f"👤 用户信息: {user}")
        logger.info(f"📊 请求数据: {request}")

        # 立即创建任务记录并返回，不等待执行完成
        analysis_service = get_simple_analysis_service()
        result = await analysis_service.create_analysis_task(user["id"], request)

        # 提取变量，避免闭包问题
        task_id = result["task_id"]
        user_id = user["id"]

        # 定义一个包装函数来运行异步任务
        async def run_analysis_task():
            """包装函数：在后台运行分析任务"""
            try:
                logger.info(f"🚀 [BackgroundTask] 开始执行分析任务: {task_id}")
                logger.info(f"📝 [BackgroundTask] task_id={task_id}, user_id={user_id}")
                logger.info(f"📝 [BackgroundTask] request={request}")

                # 重新获取服务实例，确保在正确的上下文中
                logger.info("🔧 [BackgroundTask] 正在获取服务实例...")
                service = get_simple_analysis_service()
                logger.info(f"✅ [BackgroundTask] 服务实例获取成功: {id(service)}")

                logger.info(
                    "🚀 [BackgroundTask] 准备调用 execute_analysis_background..."
                )
                await service.execute_analysis_background(task_id, user_id, request)
                logger.info(f"✅ [BackgroundTask] 分析任务完成: {task_id}")
            except Exception as e:
                logger.error(
                    f"❌ [BackgroundTask] 分析任务失败: {task_id}, 错误: {e}",
                    exc_info=True,
                )

        # 使用 BackgroundTasks 执行异步任务
        background_tasks.add_task(run_analysis_task)

        logger.info(f"✅ 分析任务已在后台启动: {result}")

        return {"success": True, "data": result, "message": "分析任务已在后台启动"}
    except Exception as e:
        logger.error(f"❌ 提交单股分析任务失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# 测试路由 - 验证路由是否被正确注册
@router.get("/test-route", response_model=AnalysisTestRouteResponse)
async def test_route():
    """测试路由是否工作"""
    logger.info("🧪 测试路由被调用了！")
    return {"message": "测试路由工作正常", "timestamp": time.time()}


@router.get("/tasks/{task_id}/status", response_model=ApiResponse)
async def get_task_status_new(task_id: str, user: dict = Depends(get_current_user)):
    """获取分析任务状态（新版异步实现）"""
    try:
        logger.info(f"🔍 [NEW ROUTE] 进入新版状态查询路由: {task_id}")
        logger.info(f"👤 [NEW ROUTE] 用户: {user}")

        analysis_service = get_simple_analysis_service()
        logger.info(f"🔧 [NEW ROUTE] 获取分析服务实例: {id(analysis_service)}")

        result = await analysis_service.get_task_status(task_id)
        logger.info(f"📊 [NEW ROUTE] 查询结果: {result is not None}")

        if result:
            return {"success": True, "data": result, "message": "任务状态获取成功"}
        else:
            # 内存中没有找到，尝试从 PostgreSQL document store 中查找
            logger.info(
                f"📊 [STATUS] 内存中未找到，尝试从 PostgreSQL document store 查找: {task_id}"
            )

            # 首先从analysis_tasks集合中查找（正在进行的任务）
            task_result = await _get_analysis_task_for_read(task_id)

            if task_result:
                logger.info(f"✅ [STATUS] 从analysis_tasks找到任务: {task_id}")

                # 构造状态响应（正在进行的任务）
                status = task_result.get("status", "pending")
                progress = task_result.get("progress", 0)

                # 计算时间信息
                start_time = _coerce_datetime(
                    task_result.get("started_at") or task_result.get("created_at")
                )
                current_time = datetime.utcnow()
                elapsed_time = 0
                if start_time:
                    elapsed_time = (current_time - start_time).total_seconds()

                status_data = {
                    "task_id": task_id,
                    "status": status,
                    "progress": progress,
                    "message": f"任务{status}中...",
                    "current_step": status,
                    "start_time": start_time,
                    "end_time": task_result.get("completed_at"),
                    "elapsed_time": elapsed_time,
                    "remaining_time": 0,  # 无法准确估算
                    "estimated_total_time": 0,
                    "symbol": task_result.get("symbol")
                    or task_result.get("stock_code"),
                    "stock_code": task_result.get("symbol")
                    or task_result.get("stock_code"),  # 兼容字段
                    "stock_symbol": task_result.get("symbol")
                    or task_result.get("stock_code"),
                    "source": "postgres_tasks",  # 标记数据来源
                }

                return {
                    "success": True,
                    "data": status_data,
                    "message": "任务状态获取成功（从任务记录恢复）",
                }

            # 如果analysis_tasks中没有找到，再从analysis_reports集合中查找（已完成的任务）
            postgres_result = await _get_analysis_report_by_task_id_for_read(task_id)

            if postgres_result:
                logger.info(f"✅ [STATUS] 从analysis_reports找到任务: {task_id}")

                # 构造状态响应（模拟已完成的任务）
                # 计算已完成任务的时间信息
                start_time = _coerce_datetime(postgres_result.get("created_at"))
                end_time = _coerce_datetime(postgres_result.get("updated_at"))
                elapsed_time = 0
                if start_time and end_time:
                    elapsed_time = (end_time - start_time).total_seconds()

                status_data = {
                    "task_id": task_id,
                    "status": "completed",
                    "progress": 100,
                    "message": "分析完成（从历史记录恢复）",
                    "current_step": "completed",
                    "start_time": start_time,
                    "end_time": end_time,
                    "elapsed_time": elapsed_time,
                    "remaining_time": 0,
                    "estimated_total_time": elapsed_time,  # 已完成任务的总时长就是已用时间
                    "stock_code": postgres_result.get("stock_symbol"),
                    "stock_symbol": postgres_result.get("stock_symbol"),
                    "analysts": postgres_result.get("analysts", []),
                    "research_depth": postgres_result.get("research_depth", "快速"),
                    "source": "postgres_reports",  # 标记数据来源
                }

                return {
                    "success": True,
                    "data": status_data,
                    "message": "任务状态获取成功（从历史记录恢复）",
                }
            else:
                logger.warning(
                    f"❌ [STATUS] PostgreSQL中也未找到: {task_id} trace={task_id}"
                )
                raise HTTPException(status_code=404, detail="任务不存在")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
