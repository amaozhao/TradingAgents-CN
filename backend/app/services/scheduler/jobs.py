from .common import (
    Any,
    Dict,
    List,
    Optional,
    datetime,
    get_utc8_now,
    importlib,
    logger,
)


class SchedulerJobsMixin:
    async def list_jobs(self) -> List[Dict[str, Any]]:
        """
        获取所有定时任务列表

        Returns:
            任务列表
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            job_dict = self._job_to_dict(job)
            # 获取任务元数据（触发器名称和备注）
            metadata = await self._get_job_metadata(job.id)
            if metadata:
                job_dict["display_name"] = metadata.get("display_name")
                job_dict["description"] = metadata.get("description")
            jobs.append(job_dict)

        logger.info(f"📋 获取到 {len(jobs)} 个定时任务")
        return jobs

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务详情

        Args:
            job_id: 任务ID

        Returns:
            任务详情，如果不存在则返回None
        """
        job = self.scheduler.get_job(job_id)
        if job:
            job_dict = self._job_to_dict(job, include_details=True)
            # 获取任务元数据
            metadata = await self._get_job_metadata(job_id)
            if metadata:
                job_dict["display_name"] = metadata.get("display_name")
                job_dict["description"] = metadata.get("description")
            return job_dict
        return None

    async def pause_job(self, job_id: str) -> bool:
        """
        暂停任务

        Args:
            job_id: 任务ID

        Returns:
            是否成功
        """
        try:
            self.scheduler.pause_job(job_id)
            logger.info(f"⏸️ 任务 {job_id} 已暂停")

            # 记录操作历史
            await self._record_job_action(job_id, "pause", "success")
            return True
        except Exception as e:
            logger.error(f"❌ 暂停任务 {job_id} 失败: {e}")
            await self._record_job_action(job_id, "pause", "failed", str(e))
            return False

    async def resume_job(self, job_id: str) -> bool:
        """
        恢复任务

        Args:
            job_id: 任务ID

        Returns:
            是否成功
        """
        try:
            self.scheduler.resume_job(job_id)
            logger.info(f"▶️ 任务 {job_id} 已恢复")

            # 记录操作历史
            await self._record_job_action(job_id, "resume", "success")
            return True
        except Exception as e:
            logger.error(f"❌ 恢复任务 {job_id} 失败: {e}")
            await self._record_job_action(job_id, "resume", "failed", str(e))
            return False

    async def trigger_job(
        self, job_id: str, kwargs: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        手动触发任务执行

        注意：如果任务处于暂停状态，会先临时恢复任务，执行一次后不会自动暂停

        Args:
            job_id: 任务ID
            kwargs: 传递给任务函数的关键字参数（可选）

        Returns:
            是否成功
        """
        try:
            job = self.scheduler.get_job(job_id)
            if not job:
                logger.error(f"❌ 任务 {job_id} 不存在")
                return False

            # 检查任务是否被暂停（next_run_time 为 None 表示暂停）
            was_paused = job.next_run_time is None
            if was_paused:
                logger.warning(f"⚠️ 任务 {job_id} 处于暂停状态，临时恢复以执行一次")
                self.scheduler.resume_job(job_id)
                # 重新获取 job 对象（恢复后状态已改变）
                job = self.scheduler.get_job(job_id)
                if job is None:
                    logger.error(f"❌ 任务 {job_id} 临时恢复后不存在")
                    return False
                logger.info(f"✅ 任务 {job_id} 已临时恢复")

            # 如果提供了 kwargs，合并到任务的 kwargs 中
            if kwargs:
                # 获取任务原有的 kwargs
                original_kwargs = job.kwargs.copy() if job.kwargs else {}
                # 合并新的 kwargs
                merged_kwargs = {**original_kwargs, **kwargs}
                # 修改任务的 kwargs
                job.modify(kwargs=merged_kwargs)
                logger.info(f"📝 任务 {job_id} 参数已更新: {kwargs}")

            # 手动触发任务 - 使用带时区的当前时间
            timezone = getattr(importlib.import_module("datetime"), "timezone")
            now = datetime.now(timezone.utc)
            job.modify(next_run_time=now)
            logger.info(
                f"🚀 手动触发任务 {job_id} (next_run_time={now}, was_paused={was_paused}, kwargs={kwargs})"
            )

            # 记录操作历史
            action_note = f"手动触发执行 (暂停状态: {was_paused}"
            if kwargs:
                action_note += f", 参数: {kwargs}"
            action_note += ")"
            await self._record_job_action(job_id, "trigger", "success", action_note)

            # 立即创建一个"running"状态的执行记录，让用户能看到任务正在执行
            # 🔥 使用本地时间（naive datetime）
            await self._record_job_execution(
                job_id=job_id,
                status="running",
                scheduled_time=get_utc8_now(),  # 使用本地时间（naive datetime）
                progress=0,
                is_manual=True,  # 标记为手动触发
            )

            return True
        except Exception as e:
            logger.error(f"❌ 触发任务 {job_id} 失败: {e}")
            traceback = importlib.import_module("traceback")
            logger.error(f"详细错误: {traceback.format_exc()}")
            await self._record_job_action(job_id, "trigger", "failed", str(e))
            return False
