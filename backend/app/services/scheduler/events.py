from .common import (
    EVENT_JOB_ERROR,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_MISSED,
    JobExecutionEvent,
    Optional,
    UTC_8,
    asyncio,
    datetime,
    get_utc8_now,
    logger,
    timedelta,
)


class SchedulerEventsMixin:
    def _setup_event_listeners(self):
        """设置APScheduler事件监听器"""
        # 监听任务执行成功事件
        self.scheduler.add_listener(self._on_job_executed, EVENT_JOB_EXECUTED)

        # 监听任务执行失败事件
        self.scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)

        # 监听任务错过执行事件
        self.scheduler.add_listener(self._on_job_missed, EVENT_JOB_MISSED)

        logger.info("✅ APScheduler事件监听器已设置")

        # 添加定时任务，检测僵尸任务（长时间处于running状态）
        self.scheduler.add_job(
            self._check_zombie_tasks,
            "interval",
            minutes=5,
            id="check_zombie_tasks",
            name="检测僵尸任务",
            replace_existing=True,
        )
        logger.info("✅ 僵尸任务检测定时任务已添加")

    async def _check_zombie_tasks(self):
        """检测僵尸任务（长时间处于running状态的任务）"""
        try:
            db = self._get_db()

            # 查找超过30分钟仍处于running状态的任务
            threshold_time = get_utc8_now() - timedelta(minutes=30)

            zombie_tasks = await db.scheduler_executions.find(
                {"status": "running", "timestamp": {"$lt": threshold_time}}
            ).to_list(length=100)

            for task in zombie_tasks:
                # 更新为failed状态
                await db.scheduler_executions.update_one(
                    {"_id": task["_id"]},
                    {
                        "$set": {
                            "status": "failed",
                            "error_message": "任务执行超时或进程异常终止",
                            "updated_at": get_utc8_now(),
                        }
                    },
                )
                logger.warning(
                    f"⚠️ 检测到僵尸任务: {task.get('job_name', task.get('job_id'))} (开始时间: {task.get('timestamp')})"
                )

            if zombie_tasks:
                logger.info(f"✅ 已标记 {len(zombie_tasks)} 个僵尸任务为失败状态")

        except Exception as e:
            logger.error(f"❌ 检测僵尸任务失败: {e}")

    def _on_job_executed(self, event: JobExecutionEvent):
        """任务执行成功回调"""
        # 计算执行时间（处理时区问题）
        execution_time = None
        if event.scheduled_run_time:
            now = datetime.now(event.scheduled_run_time.tzinfo)
            execution_time = (now - event.scheduled_run_time).total_seconds()

        asyncio.create_task(
            self._record_job_execution(
                job_id=event.job_id,
                status="success",
                scheduled_time=event.scheduled_run_time,
                execution_time=execution_time,
                return_value=str(event.retval) if event.retval else None,
                progress=100,  # 任务完成，进度100%
            )
        )

    def _on_job_error(self, event: JobExecutionEvent):
        """任务执行失败回调"""
        # 计算执行时间（处理时区问题）
        execution_time = None
        if event.scheduled_run_time:
            now = datetime.now(event.scheduled_run_time.tzinfo)
            execution_time = (now - event.scheduled_run_time).total_seconds()

        asyncio.create_task(
            self._record_job_execution(
                job_id=event.job_id,
                status="failed",
                scheduled_time=event.scheduled_run_time,
                execution_time=execution_time,
                error_message=str(event.exception) if event.exception else None,
                traceback=event.traceback if hasattr(event, "traceback") else None,
                progress=None,  # 失败时不设置进度
            )
        )

    def _on_job_missed(self, event: JobExecutionEvent):
        """任务错过执行回调"""
        asyncio.create_task(
            self._record_job_execution(
                job_id=event.job_id,
                status="missed",
                scheduled_time=event.scheduled_run_time,
                progress=None,  # 错过时不设置进度
            )
        )

    async def _record_job_execution(
        self,
        job_id: str,
        status: str,
        scheduled_time: Optional[datetime] = None,
        execution_time: Optional[float] = None,
        return_value: Optional[str] = None,
        error_message: Optional[str] = None,
        traceback: Optional[str] = None,
        progress: Optional[int] = None,
        is_manual: bool = False,
    ):
        """
        记录任务执行历史

        Args:
            job_id: 任务ID
            status: 状态 (running/success/failed/missed)
            scheduled_time: 计划执行时间
            execution_time: 实际执行时长（秒）
            return_value: 返回值
            error_message: 错误信息
            traceback: 错误堆栈
            progress: 执行进度（0-100）
            is_manual: 是否手动触发
        """
        try:
            db = self._get_db()

            # 获取任务名称
            job = self.scheduler.get_job(job_id)
            job_name = job.name if job else job_id

            # 如果是完成状态（success/failed），先查找是否有对应的 running 记录
            if status in ["success", "failed"]:
                # 查找最近的 running 记录（5分钟内）
                five_minutes_ago = get_utc8_now() - timedelta(minutes=5)
                existing_record = await db.scheduler_executions.find_one(
                    {
                        "job_id": job_id,
                        "status": "running",
                        "timestamp": {"$gte": five_minutes_ago},
                    },
                    sort=[("timestamp", -1)],
                )

                if existing_record:
                    # 更新现有记录
                    update_data = {
                        "status": status,
                        "execution_time": execution_time,
                        "updated_at": get_utc8_now(),
                    }

                    if return_value:
                        update_data["return_value"] = return_value
                    if error_message:
                        update_data["error_message"] = error_message
                    if traceback:
                        update_data["traceback"] = traceback
                    if progress is not None:
                        update_data["progress"] = progress

                    await db.scheduler_executions.update_one(
                        {"_id": existing_record["_id"]}, {"$set": update_data}
                    )
                    await self._dual_write_scheduler_document(
                        "scheduler_executions",
                        {**existing_record, **update_data},
                    )

                    # 记录日志
                    if status == "success":
                        logger.info(
                            f"✅ [任务执行] {job_name} 执行成功，耗时: {execution_time:.2f}秒"
                        )
                    elif status == "failed":
                        logger.error(
                            f"❌ [任务执行] {job_name} 执行失败: {error_message}"
                        )

                    return

            # 如果没有找到 running 记录，或者是 running/missed 状态，插入新记录
            # scheduled_time 可能是 aware datetime（来自 APScheduler），需要转换为 naive datetime
            scheduled_time_naive = None
            if scheduled_time:
                if scheduled_time.tzinfo is not None:
                    # 转换为本地时区，然后移除时区信息
                    scheduled_time_naive = scheduled_time.astimezone(UTC_8).replace(
                        tzinfo=None
                    )
                else:
                    scheduled_time_naive = scheduled_time

            execution_record = {
                "job_id": job_id,
                "job_name": job_name,
                "status": status,
                "scheduled_time": scheduled_time_naive,
                "execution_time": execution_time,
                "timestamp": get_utc8_now(),
                "is_manual": is_manual,
            }

            if return_value:
                execution_record["return_value"] = return_value
            if error_message:
                execution_record["error_message"] = error_message
            if traceback:
                execution_record["traceback"] = traceback
            if progress is not None:
                execution_record["progress"] = progress

            result = await db.scheduler_executions.insert_one(execution_record)
            execution_record["_id"] = result.inserted_id
            await self._dual_write_scheduler_document(
                "scheduler_executions", execution_record
            )

            # 记录日志
            if status == "success":
                logger.info(
                    f"✅ [任务执行] {job_name} 执行成功，耗时: {execution_time:.2f}秒"
                )
            elif status == "failed":
                logger.error(f"❌ [任务执行] {job_name} 执行失败: {error_message}")
            elif status == "missed":
                logger.warning(f"⚠️ [任务执行] {job_name} 错过执行时间")
            elif status == "running":
                trigger_type = "手动触发" if is_manual else "自动触发"
                logger.info(
                    f"🔄 [任务执行] {job_name} 开始执行 ({trigger_type})，进度: {progress}%"
                )

        except Exception as e:
            logger.error(f"❌ 记录任务执行历史失败: {e}")
