from .imports import logger
from .task import get_akshare_sync_service

async def run_akshare_news_sync(max_news_per_stock: int = 20):
    """APScheduler任务：同步新闻数据"""
    try:
        service = await get_akshare_sync_service()
        result = await service.sync_news_data(max_news_per_stock=max_news_per_stock)
        logger.info(f"✅ AKShare新闻数据同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ AKShare新闻数据同步失败: {e}")
        raise
