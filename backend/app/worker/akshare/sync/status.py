from .imports import logger
from .task import get_akshare_sync_service

async def run_akshare_basic_info_sync(force_update: bool = False):
    """APScheduler任务：同步股票基础信息"""
    try:
        service = await get_akshare_sync_service()
        result = await service.sync_stock_basic_info(force_update=force_update)
        logger.info(f"✅ AKShare基础信息同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ AKShare基础信息同步失败: {e}")
        raise
