"""
AGENTrader WebAPI Worker

Consumes tasks from Redis queue and processes them using actual stock analysis.
"""

import asyncio
import importlib
import json
import logging
import signal
import time
from datetime import datetime
from typing import Any, Optional

# Add project root to path for importing analysis runner
from app.core.database import close_db, get_postgres_db, get_redis_client, init_db
from app.core.logs import setup_logging
from app.schemas.analysis import AnalysisParameters, SingleAnalysisRequest
from app.services.analysis.simple import get_simple_analysis_service

# Redis keys (must match queue_service)
READY_LIST = "qa:ready"
TASK_PREFIX = "qa:task:"
SET_PROCESSING = "qa:processing"
SET_COMPLETED = "qa:completed"
SET_FAILED = "qa:failed"

logger = logging.getLogger("worker")


async def publish_progress(
    task_id: str,
    message: str,
    step: Optional[int] = None,
    total_steps: Optional[int] = None,
):
    """Publish progress updates to Redis pubsub for SSE streaming"""
    r = get_redis_client()
    progress_data: dict[str, Any] = {
        "task_id": task_id,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }
    if step is not None and total_steps is not None:
        progress_data["step"] = step
        progress_data["total_steps"] = total_steps
        progress_data["progress"] = round((step / total_steps) * 100, 1)

    try:
        await r.publish(
            f"task_progress:{task_id}", json.dumps(progress_data, ensure_ascii=False)
        )
    except Exception as e:
        logger.warning(f"Failed to publish progress for task {task_id}: {e}")


async def process_task(task_id: str) -> None:
    r = get_redis_client()
    key = TASK_PREFIX + task_id

    # Load task
    data = await r.hgetall(key)
    if not data:
        logger.warning(f"Task not found: {task_id}")
        return

    # Mark processing
    now = int(time.time())
    await r.hset(key, mapping={"status": "processing", "started_at": str(now)})
    await r.sadd(SET_PROCESSING, task_id)
    logger.info(
        f"Processing task {task_id} | user={data.get('user')} symbol={data.get('symbol')}"
    )

    try:
        # Parse params
        params = {}
        if "params" in data:
            try:
                params = (
                    json.loads(data["params"])
                    if isinstance(data["params"], str)
                    else {}
                )
            except Exception:
                params = {}

        symbol = data.get("symbol", "")
        user_id = str(data.get("user", ""))

        # Progress callback function
        async def progress_callback(
            message: str, step: Optional[int] = None, total_steps: Optional[int] = None
        ):
            await publish_progress(task_id, message, step, total_steps)

        await progress_callback("🚀 开始执行股票分析...")

        try:
            service = get_simple_analysis_service()
            analysis_params = AnalysisParameters.model_validate(params or {})
            request = SingleAnalysisRequest(
                symbol=symbol,
                stock_code=symbol,
                parameters=analysis_params,
            )

            await service.execute_analysis_background(task_id, user_id, request)

            await progress_callback("✅ 分析完成，正在保存结果...")
            task_document = await get_postgres_db().analysis_tasks.find_one(
                {"task_id": task_id}
            )
            status = (
                str(task_document.get("status", "completed"))
                if task_document
                else "completed"
            )
            success = status == "completed"
            result = (
                task_document.get("result")
                if task_document and task_document.get("result") is not None
                else {
                    "symbol": symbol,
                    "completed_at": datetime.now().isoformat(),
                    "success": success,
                }
            )
            if success:
                await progress_callback("🎉 任务成功完成")
            else:
                error_msg = str(
                    (task_document or {}).get("error_message")
                    or (task_document or {}).get("last_error")
                    or "分析失败"
                )
                await progress_callback(f"❌ 任务失败: {error_msg}")

        except Exception as analysis_error:
            logger.exception(
                f"Analysis execution failed for task {task_id}: {analysis_error}"
            )
            result = {
                "symbol": symbol,
                "error": f"分析执行异常: {str(analysis_error)}",
                "completed_at": datetime.now().isoformat(),
                "success": False,
            }
            status = "failed"
            await progress_callback(f"❌ 分析执行异常: {str(analysis_error)}")

        # Mark completed/failed
        finished = int(time.time())
        await r.hset(
            key,
            mapping={
                "status": status,
                "completed_at": str(finished),
                "result": json.dumps(result, ensure_ascii=False),
            },
        )
        await r.srem(SET_PROCESSING, task_id)
        if status == "completed":
            await r.sadd(SET_COMPLETED, task_id)
        else:
            await r.sadd(SET_FAILED, task_id)

        logger.info(f"Task {task_id} {status}")

    except Exception as e:
        logger.exception(f"Task {task_id} processing failed: {e}")
        finished = int(time.time())
        await r.hset(
            key,
            mapping={
                "status": "failed",
                "completed_at": str(finished),
                "error": str(e),
            },
        )
        await r.srem(SET_PROCESSING, task_id)
        await r.sadd(SET_FAILED, task_id)
        await publish_progress(task_id, f"❌ 处理失败: {str(e)}")


async def worker_loop(stop_event: asyncio.Event):
    r = get_redis_client()
    logger.info("Worker loop started")
    while not stop_event.is_set():
        try:
            # BLPOP returns (list, task_id) when an item is available
            item = await r.blpop(READY_LIST, timeout=5)
            if not item:
                continue
            _, task_id = item
            await process_task(
                task_id.decode() if isinstance(task_id, bytes) else str(task_id)
            )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception(f"Worker loop error: {e}")
            await asyncio.sleep(1)
    logger.info("Worker loop stopped")


async def main():
    setup_logging("INFO")
    await init_db()
    # Apply dynamic log level from system settings
    try:
        config_provider = getattr(
            importlib.import_module("app.services.provider"), "provider"
        )
        eff = await config_provider.get_effective_system_settings()
        desired_level = str(eff.get("log_level", "INFO")).upper()
        setup_logging(desired_level)
        for name in ("worker", "webapi", "uvicorn", "fastapi"):
            logging.getLogger(name).setLevel(desired_level)
    except Exception as e:
        logging.getLogger("worker").warning(f"Failed to apply dynamic log level: {e}")

    stop_event = asyncio.Event()

    def _handle_signal(*_):
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            # Windows may not support signal handlers in event loop
            pass

    try:
        await worker_loop(stop_event)
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
