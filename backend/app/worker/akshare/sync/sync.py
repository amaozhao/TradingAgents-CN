from .imports import logger
from .task import get_akshare_sync_service

async def run_akshare_financial_sync():
    """APScheduler任务：同步财务数据"""
    try:
        service = await get_akshare_sync_service()
        result = await service.sync_financial_data()
        logger.info(f"✅ AKShare财务数据同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ AKShare财务数据同步失败: {e}")
        raise
