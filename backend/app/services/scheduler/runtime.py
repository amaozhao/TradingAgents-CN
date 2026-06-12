from .common import (
    AsyncIOScheduler,
    Optional,
    TaskCancelledException,
    get_utc8_now,
    importlib,
    logger,
)
from .service import SchedulerService

# 全局服务实例
_scheduler_service: Optional[SchedulerService] = None
_scheduler_instance: Optional[AsyncIOScheduler] = None


def set_scheduler_instance(scheduler: AsyncIOScheduler):
    """
    设置调度器实例

    Args:
        scheduler: APScheduler调度器实例
    """
    global _scheduler_instance
    _scheduler_instance = scheduler
    logger.info("✅ 调度器实例已设置")


def get_scheduler_service() -> SchedulerService:
    """
    获取调度器服务实例

    Returns:
        调度器服务实例
    """
    global _scheduler_service, _scheduler_instance

    if _scheduler_instance is None:
        raise RuntimeError("调度器实例未设置，请先调用 set_scheduler_instance()")

    if _scheduler_service is None:
        _scheduler_service = SchedulerService(_scheduler_instance)
        logger.info("✅ 调度器服务实例已创建")

    return _scheduler_service


async def update_job_progress(
    job_id: str,
    progress: int,
    message: Optional[str] = None,
    current_item: Optional[str] = None,
    total_items: Optional[int] = None,
    processed_items: Optional[int] = None,
):
    """
    更新任务执行进度（供定时任务内部调用）

    Args:
        job_id: 任务ID
        progress: 进度百分比（0-100）
        message: 进度消息
        current_item: 当前处理项
        total_items: 总项数
        processed_items: 已处理项数
    """
    try:
        get_postgres_db_sync = getattr(
            importlib.import_module("app.core.database"), "get_postgres_db_sync"
        )
        sync_db = get_postgres_db_sync()

        # 查找最近的执行记录
        latest_execution = sync_db.scheduler_executions.find_one(
            {"job_id": job_id, "status": {"$in": ["running", "success", "failed"]}},
            sort=[("timestamp", -1)],
        )

        if latest_execution:
            # 检查是否有取消请求
            if latest_execution.get("cancel_requested"):
                logger.warning(f"⚠️ 任务 {job_id} 收到取消请求，即将停止")
                raise TaskCancelledException(f"任务 {job_id} 已被用户取消")

            # 更新现有记录
            update_data = {
                "progress": progress,
                "status": "running",
                "updated_at": get_utc8_now(),
            }

            if message:
                update_data["progress_message"] = message
            if current_item:
                update_data["current_item"] = current_item
            if total_items is not None:
                update_data["total_items"] = total_items
            if processed_items is not None:
                update_data["processed_items"] = processed_items

            sync_db.scheduler_executions.update_one(
                {"_id": latest_execution["_id"]}, {"$set": update_data}
            )
        else:
            # 创建新的执行记录（任务刚开始）
            getattr(
                importlib.import_module("apscheduler.schedulers.asyncio"),
                "AsyncIOScheduler",
            )

            # 获取任务名称
            job_name = job_id
            if _scheduler_instance:
                job = _scheduler_instance.get_job(job_id)
                if job:
                    job_name = job.name

            execution_record = {
                "job_id": job_id,
                "job_name": job_name,
                "status": "running",
                "progress": progress,
                "scheduled_time": get_utc8_now(),
                "timestamp": get_utc8_now(),
            }

            if message:
                execution_record["progress_message"] = message
            if current_item:
                execution_record["current_item"] = current_item
            if total_items is not None:
                execution_record["total_items"] = total_items
            if processed_items is not None:
                execution_record["processed_items"] = processed_items

            sync_db.scheduler_executions.insert_one(execution_record)

    except Exception as e:
        logger.error(f"❌ 更新任务进度失败: {e}")
