from .imports import logger
from .task import get_akshare_sync_service

async def run_akshare_quotes_sync(force: bool = False):
    """
    APScheduler任务：同步实时行情

    Args:
        force: 是否强制执行（跳过交易时间检查），默认 False
    """
    try:
        service = await get_akshare_sync_service()
        # 注意：AKShare 没有交易时间检查逻辑，force 参数仅用于接口一致性
        result = await service.sync_realtime_quotes(force=force)
        logger.info(f"✅ AKShare行情同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ AKShare行情同步失败: {e}")
        raise
