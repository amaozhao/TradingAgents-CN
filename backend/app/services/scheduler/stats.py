# ruff: noqa: F403,F405
from .common import *


class SchedulerStatsMixin:
    async def get_job_execution_stats(self, job_id: str) -> Dict[str, Any]:
        """
        获取任务执行统计信息

        Args:
            job_id: 任务ID

        Returns:
            统计信息
        """
        try:
            db = self._get_db()

            # 统计各状态的执行次数
            pipeline = [
                {"$match": {"job_id": job_id}},
                {
                    "$group": {
                        "_id": "$status",
                        "count": {"$sum": 1},
                        "avg_execution_time": {"$avg": "$execution_time"},
                    }
                },
            ]

            stats: Dict[str, Any] = {
                "total": 0,
                "success": 0,
                "failed": 0,
                "missed": 0,
                "avg_execution_time": 0,
            }

            async for doc in db.scheduler_executions.aggregate(pipeline):
                status = doc["_id"]
                count = doc["count"]
                stats["total"] += count
                stats[status] = count

                if status == "success" and doc.get("avg_execution_time"):
                    stats["avg_execution_time"] = round(doc["avg_execution_time"], 2)

            # 获取最近一次执行
            last_execution = await db.scheduler_executions.find_one(
                {"job_id": job_id}, sort=[("timestamp", -1)]
            )

            if last_execution:
                stats["last_execution"] = {
                    "status": last_execution.get("status"),
                    "timestamp": cast(Any, last_execution.get("timestamp")).isoformat()
                    if last_execution.get("timestamp")
                    else None,
                    "execution_time": last_execution.get("execution_time"),
                }

            return stats
        except Exception as e:
            logger.error(f"❌ 获取任务执行统计失败: {e}")
            return {}

    async def get_stats(self) -> Dict[str, Any]:
        """
        获取调度器统计信息

        Returns:
            统计信息
        """
        jobs = self.scheduler.get_jobs()

        total = len(jobs)
        running = sum(1 for job in jobs if job.next_run_time is not None)
        paused = total - running

        return {
            "total_jobs": total,
            "running_jobs": running,
            "paused_jobs": paused,
            "scheduler_running": self.scheduler.running,
            "scheduler_state": self.scheduler.state,
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        调度器健康检查

        Returns:
            健康状态
        """
        return {
            "status": "healthy" if self.scheduler.running else "stopped",
            "running": self.scheduler.running,
            "state": self.scheduler.state,
            "timestamp": get_utc8_now().isoformat(),
        }

    def _job_to_dict(self, job: Job, include_details: bool = False) -> Dict[str, Any]:
        """
        将Job对象转换为字典

        Args:
            job: Job对象
            include_details: 是否包含详细信息

        Returns:
            字典表示
        """
        result = {
            "id": job.id,
            "name": job.name or job.id,
            "next_run_time": job.next_run_time.isoformat()
            if job.next_run_time
            else None,
            "paused": job.next_run_time is None,
            "trigger": str(job.trigger),
        }

        if include_details:
            result.update(
                {
                    "func": f"{job.func.__module__}.{job.func.__name__}",
                    "args": job.args,
                    "kwargs": job.kwargs,
                    "misfire_grace_time": job.misfire_grace_time,
                    "max_instances": job.max_instances,
                }
            )

        return result
