from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .imports import (
        ApiResponse,
        Depends,
        HTTPException,
        datetime,
        get_current_user,
        get_simple_analysis_service,
        logger,
        router,
        time,
        timezone,
    )
    from .setup import (
        AnalysisTestRouteResponse,
        _coerce_datetime,
        _get_analysis_report_by_task_id_for_read,
        _get_analysis_task_for_read,
    )


def _status_message_from_task_result(
    task_result: dict, status: str, error_message: str | None
) -> str:
    stored_message = task_result.get("message")
    if stored_message:
        return stored_message
    if status == "failed" and error_message:
        return error_message
    if status == "completed":
        return "分析完成"
    if status == "cancelled":
        return "任务已取消"
    return f"任务{status}中..."


def _status_step_from_task_result(task_result: dict, status: str) -> str:
    return task_result.get("current_step") or status


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

        current_user_id = str(user["id"])
        result = await analysis_service.get_task_status(
            task_id, user_id=current_user_id
        )
        logger.info(f"📊 [NEW ROUTE] 查询结果: {result is not None}")

        if result:
            return {"success": True, "data": result, "message": "任务状态获取成功"}
        else:
            # 内存中没有找到，尝试从 PostgreSQL document store 中查找
            logger.info(
                f"📊 [STATUS] 内存中未找到，尝试从 PostgreSQL document store 查找: {task_id}"
            )

            # 首先从analysis_tasks集合中查找（正在进行的任务）
            task_result = await _get_analysis_task_for_read(
                task_id, user_id=current_user_id
            )

            if task_result:
                logger.info(f"✅ [STATUS] 从analysis_tasks找到任务: {task_id}")

                # 构造状态响应（正在进行的任务）
                status = task_result.get("status", "pending")
                progress = task_result.get("progress", 0)

                # 计算时间信息
                start_time = _coerce_datetime(
                    task_result.get("started_at") or task_result.get("created_at")
                )
                end_time = _coerce_datetime(
                    task_result.get("completed_at") or task_result.get("updated_at")
                )
                is_terminal_status = status in {"completed", "failed", "cancelled"}
                current_time = (
                    end_time
                    if is_terminal_status and end_time
                    else datetime.now(timezone.utc).replace(tzinfo=None)
                )
                elapsed_time = 0
                if start_time:
                    elapsed_time = (current_time - start_time).total_seconds()

                error_message = (
                    task_result.get("error_message")
                    or task_result.get("last_error")
                    or task_result.get("error")
                )
                status_message = _status_message_from_task_result(
                    task_result, status, error_message
                )
                current_step = _status_step_from_task_result(task_result, status)

                status_data = {
                    "task_id": task_id,
                    "status": status,
                    "progress": progress,
                    "message": status_message,
                    "current_step": current_step,
                    "start_time": start_time,
                    "end_time": end_time or task_result.get("completed_at"),
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
                if error_message:
                    status_data["error_message"] = error_message
                    status_data["last_error"] = error_message

                return {
                    "success": True,
                    "data": status_data,
                    "message": "任务状态获取成功（从任务记录恢复）",
                }

            # 如果analysis_tasks中没有找到，再从analysis_reports集合中查找（已完成的任务）
            postgres_result = await _get_analysis_report_by_task_id_for_read(
                task_id, user_id=current_user_id
            )

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
