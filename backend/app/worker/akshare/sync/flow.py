from .imports import logger
from .task import get_akshare_sync_service

async def run_akshare_status_check():
    """APScheduler任务：状态检查"""
    try:
        service = await get_akshare_sync_service()
        result = await service.run_status_check()
        logger.info(f"✅ AKShare状态检查完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ AKShare状态检查失败: {e}")
        raise
