from .common import (
    AnalysisResult,
    AnalysisStatus,
    Any,
    Dict,
    Optional,
    RedisKeys,
    RedisProgressTracker,
    cast,
    get_postgres_db,
    get_redis_service,
    importlib,
    logger,
)


class AnalysisStatusMixin:
    async def _update_task_status(
        self,
        task_id: str,
        status: AnalysisStatus,
        progress: int,
        result: Optional[AnalysisResult] = None,
    ) -> None:
        """更新任务状态（委托至拆分的工具函数）"""
        try:
            perform_update_task_status = getattr(
                importlib.import_module("app.services.analysis.status"),
                "perform_update_task_status",
            )
            await perform_update_task_status(task_id, status, progress, result)
        except Exception as e:
            logger.error(f"更新任务状态失败: {task_id} - {e}")

    async def _update_task_status_with_tracker(
        self,
        task_id: str,
        status: AnalysisStatus,
        tracker: RedisProgressTracker,
        result: Optional[AnalysisResult] = None,
    ) -> None:
        """使用进度跟踪器更新任务状态（委托至拆分的工具函数）"""
        try:
            perform_update_task_status_with_tracker = getattr(
                importlib.import_module("app.services.analysis.status"),
                "perform_update_task_status_with_tracker",
            )
            await perform_update_task_status_with_tracker(
                task_id, status, tracker, result
            )
        except Exception as e:
            logger.error(f"更新任务状态失败: {task_id} - {e}")

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        try:
            # 先检查内存中的进度跟踪器
            if task_id in self._trackers:
                tracker = self._trackers[task_id]
                progress_data = tracker.to_dict()

                # 从数据库获取任务基本信息
                db = get_postgres_db()
                task = await db.analysis_tasks.find_one({"task_id": task_id})

                if task:
                    # 合并数据库信息和进度跟踪器信息
                    return {
                        "task_id": task_id,
                        "user_id": task.get("user_id"),
                        "symbol": task.get("stock_symbol") or task.get("symbol"),
                        "stock_code": task.get("stock_symbol")
                        or task.get("symbol"),  # 兼容字段
                        "status": progress_data["status"],
                        "progress": progress_data["progress"],
                        "current_step": progress_data["current_step"],
                        "message": progress_data["message"],
                        "elapsed_time": progress_data["elapsed_time"],
                        "remaining_time": progress_data["remaining_time"],
                        "estimated_total_time": progress_data.get(
                            "estimated_total_time", 0
                        ),
                        "steps": progress_data["steps"],
                        "start_time": progress_data["start_time"],
                        "end_time": None,
                        "last_update": progress_data["last_update"],
                        "parameters": task.get("parameters", {}),
                        "execution_time": None,
                        "tokens_used": None,
                        "result_data": task.get("result"),
                        "error_message": None,
                    }

            # 从Redis缓存获取
            redis_service = get_redis_service()
            progress_key = RedisKeys.TASK_PROGRESS.format(task_id=task_id)
            cached_status = await redis_service.get_json(progress_key)

            if cached_status:
                return cached_status

            # 从数据库获取
            db = get_postgres_db()
            task = await db.analysis_tasks.find_one({"task_id": task_id})

            if task:
                # 计算已用时间
                elapsed_time = 0
                remaining_time = 0
                estimated_total_time = 0
                start_time = None

                if task.get("started_at"):
                    datetime = getattr(importlib.import_module("datetime"), "datetime")
                    start_time = cast(Any, task.get("started_at"))
                    completed_at = cast(Any, task.get("completed_at"))
                    if completed_at:
                        # 任务已完成
                        elapsed_time = (completed_at - start_time).total_seconds()
                        estimated_total_time = (
                            elapsed_time  # 已完成任务的总时长就是已用时间
                        )
                        remaining_time = 0
                    else:
                        # 任务进行中
                        elapsed_time = (datetime.utcnow() - start_time).total_seconds()

                        # 使用任务的预估时长，如果没有则使用默认值（5分钟）
                        estimated_total_time = task.get("estimated_duration", 300)

                        # 预计剩余 = 预估总时长 - 已用时间
                        remaining_time = max(0, estimated_total_time - elapsed_time)

                return {
                    "task_id": task_id,
                    "status": task.get("status"),
                    "progress": task.get("progress", 0),
                    "current_step": task.get("current_step", ""),
                    "message": task.get("message", ""),
                    "elapsed_time": elapsed_time,
                    "remaining_time": remaining_time,
                    "estimated_total_time": estimated_total_time,
                    "start_time": cast(Any, start_time).isoformat()
                    if task.get("started_at")
                    else None,
                    "updated_at": cast(Any, task.get("updated_at")).isoformat()
                    if task.get("updated_at")
                    else None,
                    "result_data": task.get("result"),
                }

            return None

        except Exception as e:
            logger.error(f"获取任务状态失败: {task_id} - {e}")
            return None

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        try:
            # 更新任务状态
            await self._update_task_status(task_id, AnalysisStatus.CANCELLED, 0)

            # 从队列中移除（如果还在队列中）
            await self.queue_service.cancel_task(task_id)

            logger.info(f"任务已取消: {task_id}")
            return True

        except Exception as e:
            logger.error(f"取消任务失败: {task_id} - {e}")
            return False
