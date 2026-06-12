import asyncio
import importlib
import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.database import get_redis_client
from app.routers.account import get_current_user
from app.services.queue.service import QueueService, get_queue_service
from app.services.research.agent.batch.repository import BatchRepository

router = APIRouter()
logger = logging.getLogger("webapi.sse")


def _batch_progress_from_repository_document(batch: dict) -> dict:
    tasks = batch.get("tasks")
    task_list = tasks if isinstance(tasks, list) else []
    total_tasks = len(task_list) or int(batch.get("total_tasks") or 0)
    completed_count = 0
    failed_count = 0
    cancelled_count = 0
    processing_count = 0

    for task in task_list:
        if not isinstance(task, dict):
            continue
        status = str(task.get("status") or "queued")
        if status == "completed":
            completed_count += 1
        elif status == "failed":
            failed_count += 1
        elif status == "cancelled":
            cancelled_count += 1
        elif status in {"processing", "running"}:
            processing_count += 1

    if not task_list:
        completed_count = int(batch.get("completed_tasks") or 0)
        failed_count = int(batch.get("failed_tasks") or 0)
        cancelled_count = int(batch.get("cancelled_tasks") or 0)
        processing_count = int(batch.get("processing_tasks") or 0)

    finished_tasks = completed_count + failed_count + cancelled_count
    progress = round((finished_tasks / total_tasks) * 100, 1) if total_tasks else 0
    status = _repository_batch_status(
        raw_status=str(batch.get("status") or ""),
        total_tasks=total_tasks,
        completed_count=completed_count,
        failed_count=failed_count,
        cancelled_count=cancelled_count,
        processing_count=processing_count,
    )
    return {
        "batch_id": batch.get("batch_id"),
        "status": status,
        "message": _batch_progress_message(
            status=status,
            total_tasks=total_tasks,
            completed_count=completed_count,
            failed_count=failed_count,
            cancelled_count=cancelled_count,
            processing_count=processing_count,
        ),
        "progress": progress,
        "total_tasks": total_tasks,
        "completed": completed_count,
        "failed": failed_count,
        "cancelled": cancelled_count,
        "processing": processing_count,
        "timestamp": time.time(),
    }


def _repository_batch_status(
    *,
    raw_status: str,
    total_tasks: int,
    completed_count: int,
    failed_count: int,
    cancelled_count: int,
    processing_count: int,
) -> str:
    normalized = "partial" if raw_status == "partial_success" else raw_status
    finished_tasks = completed_count + failed_count + cancelled_count
    if total_tasks and finished_tasks == total_tasks:
        if completed_count == total_tasks:
            return "completed"
        if failed_count == total_tasks:
            return "failed"
        if cancelled_count == total_tasks:
            return "cancelled"
        return "partial"
    if processing_count > 0 or finished_tasks < total_tasks:
        return "processing"
    return normalized or "queued"


def _batch_progress_message(
    *,
    status: str,
    total_tasks: int,
    completed_count: int,
    failed_count: int,
    cancelled_count: int,
    processing_count: int,
) -> str:
    if status == "completed":
        return f"批次完成: {completed_count}/{total_tasks} 成功"
    if status == "failed":
        return f"批次失败: {failed_count}/{total_tasks} 失败"
    if status == "partial":
        return (
            f"批次部分成功: {completed_count} 成功, "
            f"{failed_count} 失败, {cancelled_count} 取消"
        )
    if status == "cancelled":
        return f"批次取消: {cancelled_count}/{total_tasks} 取消"
    if status == "processing":
        return (
            f"批次处理中: {completed_count + failed_count + cancelled_count}/"
            f"{total_tasks} 已完成, {processing_count} 处理中"
        )
    return f"批次排队中: {total_tasks} 任务待处理"


async def task_progress_generator(task_id: str, user_id: str):
    """Generate SSE events for task progress updates"""
    r = get_redis_client()
    pubsub = None
    channel = f"task_progress:{task_id}"

    try:
        # Load dynamic SSE settings
        try:
            config_provider = getattr(
                importlib.import_module("app.services.provider"), "provider"
            )
            eff = await config_provider.get_effective_system_settings()
            poll_timeout = float(eff.get("sse_poll_timeout_seconds", 1.0))
            heartbeat_every = int(eff.get("sse_heartbeat_interval_seconds", 10))
            max_idle_seconds = int(eff.get("sse_task_max_idle_seconds", 300))
        except Exception:
            poll_timeout = float(getattr(settings, "SSE_POLL_TIMEOUT_SECONDS", 1.0))
            heartbeat_every = int(
                getattr(settings, "SSE_HEARTBEAT_INTERVAL_SECONDS", 10)
            )
            max_idle_seconds = int(getattr(settings, "SSE_TASK_MAX_IDLE_SECONDS", 300))

        # 🔥 修复：创建 PubSub 连接
        pubsub = r.pubsub()
        logger.info(f"📡 [SSE-Task] 创建 PubSub 连接: task={task_id}, user={user_id}")

        # 🔥 修复：订阅频道（可能失败，需要确保 pubsub 被清理）
        try:
            await pubsub.subscribe(channel)
            logger.info(f"✅ [SSE-Task] 订阅频道成功: {channel}")
            # Send initial connection confirmation
            yield f'event: connected\ndata: {{"task_id": "{task_id}", "message": "已连接进度流"}}\n\n'
        except Exception as subscribe_error:
            # 🔥 订阅失败时立即清理 pubsub 连接
            logger.error(f"❌ [SSE-Task] 订阅频道失败: {subscribe_error}")
            try:
                await pubsub.close()
                logger.info("🧹 [SSE-Task] 订阅失败后已关闭 PubSub 连接")
            except Exception as close_error:
                logger.error(f"❌ [SSE-Task] 关闭 PubSub 连接失败: {close_error}")
            # 重新抛出异常，让外层 except 处理
            raise

        # Listen for progress updates
        idle_elapsed = 0.0
        last_hb = time.monotonic()

        while idle_elapsed < max_idle_seconds:
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=poll_timeout,
                )
                if message and message["type"] == "message":
                    # Reset idle timer on valid message
                    idle_elapsed = 0.0
                    try:
                        progress_data = json.loads(message["data"])
                        yield f"event: progress\ndata: {json.dumps(progress_data, ensure_ascii=False)}\n\n"
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Invalid JSON in progress message: {message['data']}"
                        )
                else:
                    # No update: accumulate idle time and send heartbeat if due
                    idle_elapsed += poll_timeout
                    now = time.monotonic()
                    if now - last_hb >= heartbeat_every:
                        yield f'event: heartbeat\ndata: {{"timestamp": "{asyncio.get_event_loop().time()}"}}\n\n'
                        last_hb = now

            except asyncio.TimeoutError:
                idle_elapsed += poll_timeout
                continue

    except Exception as e:
        logger.exception(f"SSE error for task {task_id}: {e}")
        yield f'event: error\ndata: {{"error": "连接异常: {str(e)}"}}\n\n'
    finally:
        # 🔥 修复：确保在所有情况下都释放连接
        if pubsub:
            logger.info(f"🧹 [SSE-Task] 清理 PubSub 连接: task={task_id}")

            # 分步骤关闭，确保即使 unsubscribe 失败也能关闭连接
            try:
                await pubsub.unsubscribe(channel)
                logger.debug(f"✅ [SSE-Task] 已取消订阅频道: {channel}")
            except Exception as e:
                logger.warning(f"⚠️ [SSE-Task] 取消订阅失败（将继续关闭连接）: {e}")

            try:
                await pubsub.close()
                logger.info(f"✅ [SSE-Task] PubSub 连接已关闭: task={task_id}")
            except Exception as e:
                logger.error(f"❌ [SSE-Task] 关闭 PubSub 连接失败: {e}", exc_info=True)
                # 即使关闭失败，也尝试重置连接
                try:
                    await pubsub.reset()
                    logger.info(f"🔄 [SSE-Task] PubSub 连接已重置: task={task_id}")
                except Exception as reset_error:
                    logger.error(f"❌ [SSE-Task] 重置 PubSub 连接也失败: {reset_error}")


async def batch_progress_generator(batch_id: str, user_id: str):
    """Generate SSE events for batch progress updates"""
    svc = get_queue_service()

    try:
        # Load dynamic SSE settings for batch stream
        try:
            config_provider = getattr(
                importlib.import_module("app.services.provider"), "provider"
            )
            eff = await config_provider.get_effective_system_settings()
            batch_poll_interval = float(eff.get("sse_batch_poll_interval_seconds", 2))
            batch_max_idle_seconds = int(eff.get("sse_batch_max_idle_seconds", 600))
        except Exception:
            batch_poll_interval = float(
                getattr(settings, "SSE_BATCH_POLL_INTERVAL_SECONDS", 2.0)
            )
            batch_max_idle_seconds = int(
                getattr(settings, "SSE_BATCH_MAX_IDLE_SECONDS", 600)
            )

        # Send initial connection confirmation
        yield f'event: connected\ndata: {{"batch_id": "{batch_id}", "message": "已连接批次进度流"}}\n\n'

        idle_elapsed = 0.0

        while idle_elapsed < batch_max_idle_seconds:
            try:
                repository_batch = await BatchRepository().get_batch(batch_id, user_id)
                if repository_batch is not None:
                    progress_data = _batch_progress_from_repository_document(
                        repository_batch
                    )
                    yield f"event: progress\ndata: {json.dumps(progress_data, ensure_ascii=False)}\n\n"
                    if progress_data["status"] in [
                        "completed",
                        "failed",
                        "partial",
                        "cancelled",
                    ]:
                        yield (
                            "event: finished\n"
                            f'data: {{"batch_id": "{batch_id}", '
                            f'"final_status": "{progress_data["status"]}"}}\n\n'
                        )
                        break
                    await asyncio.sleep(batch_poll_interval)
                    idle_elapsed += batch_poll_interval
                    continue

                # Get current batch status
                batch_data = await svc.get_batch(batch_id)
                if not batch_data:
                    yield 'event: error\ndata: {"error": "批次不存在"}\n\n'
                    break

                # Check if batch belongs to user
                if batch_data.get("user") != user_id:
                    yield 'event: error\ndata: {"error": "无权限访问此批次"}\n\n'
                    break

                # Calculate batch progress based on task statuses
                task_ids = batch_data.get("tasks", [])
                if not task_ids:
                    yield f'event: progress\ndata: {{"batch_id": "{batch_id}", "message": "批次无任务", "progress": 0}}\n\n'
                    await asyncio.sleep(batch_poll_interval)
                    idle_elapsed += batch_poll_interval
                    continue

                completed_count = 0
                failed_count = 0
                processing_count = 0

                for task_id in task_ids:
                    task_data = await svc.get_task(task_id)
                    if task_data:
                        status = task_data.get("status", "queued")
                        if status == "completed":
                            completed_count += 1
                        elif status == "failed":
                            failed_count += 1
                        elif status == "processing":
                            processing_count += 1

                total_tasks = len(task_ids)
                finished_tasks = completed_count + failed_count
                progress = (
                    round((finished_tasks / total_tasks) * 100, 1)
                    if total_tasks > 0
                    else 0
                )

                # Determine batch status
                if finished_tasks == total_tasks:
                    if failed_count == 0:
                        batch_status = "completed"
                        message = f"批次完成: {completed_count}/{total_tasks} 成功"
                    elif completed_count == 0:
                        batch_status = "failed"
                        message = f"批次失败: {failed_count}/{total_tasks} 失败"
                    else:
                        batch_status = "partial"
                        message = (
                            f"批次部分成功: {completed_count} 成功, {failed_count} 失败"
                        )
                elif processing_count > 0 or finished_tasks < total_tasks:
                    batch_status = "processing"
                    message = f"批次处理中: {finished_tasks}/{total_tasks} 已完成, {processing_count} 处理中"
                else:
                    batch_status = "queued"
                    message = f"批次排队中: {total_tasks} 任务待处理"

                progress_data = {
                    "batch_id": batch_id,
                    "status": batch_status,
                    "message": message,
                    "progress": progress,
                    "total_tasks": total_tasks,
                    "completed": completed_count,
                    "failed": failed_count,
                    "processing": processing_count,
                    "timestamp": asyncio.get_event_loop().time(),
                }

                yield f"event: progress\ndata: {json.dumps(progress_data, ensure_ascii=False)}\n\n"

                # Break if batch is finished
                if batch_status in ["completed", "failed", "partial"]:
                    yield f'event: finished\ndata: {{"batch_id": "{batch_id}", "final_status": "{batch_status}"}}\n\n'
                    break

                # Wait before next update
                await asyncio.sleep(batch_poll_interval)
                idle_elapsed += batch_poll_interval

            except Exception as e:
                logger.exception(f"Batch progress error: {e}")
                yield f'event: error\ndata: {{"error": "获取批次状态失败: {str(e)}"}}\n\n'
                break

    except Exception as e:
        logger.exception(f"SSE batch error for {batch_id}: {e}")
        yield f'event: error\ndata: {{"error": "连接异常: {str(e)}"}}\n\n'


@router.get("/tasks/{task_id}", response_model=None)
async def stream_task_progress(
    task_id: str,
    user: dict = Depends(get_current_user),
    svc: QueueService = Depends(get_queue_service),
):
    """Stream real-time progress updates for a specific task"""
    # Verify task exists and belongs to user
    task_data = await svc.get_task(task_id)
    if not task_data or task_data.get("user") != user["id"]:
        raise HTTPException(status_code=404, detail="Task not found")

    return StreamingResponse(
        task_progress_generator(task_id, user["id"]),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/batches/{batch_id}", response_model=None)
async def stream_batch_progress(
    batch_id: str,
    user: dict = Depends(get_current_user),
    svc: QueueService = Depends(get_queue_service),
):
    """Stream real-time progress updates for a batch"""
    # Verify against the workflow repository first; fall back to the legacy queue
    # store for batches created before the workflow migration.
    repository_batch = await BatchRepository().get_batch(batch_id, user["id"])
    if repository_batch is None:
        batch_data = await svc.get_batch(batch_id)
        if not batch_data or batch_data.get("user") != user["id"]:
            raise HTTPException(status_code=404, detail="Batch not found")

    return StreamingResponse(
        batch_progress_generator(batch_id, user["id"]),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
