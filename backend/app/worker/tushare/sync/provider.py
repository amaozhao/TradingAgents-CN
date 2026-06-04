# ruff: noqa: F401,F403,F405,F821
async def run_tushare_news_sync(hours_back: int = 24, max_news_per_stock: int = 20):
    """APScheduler任务：同步新闻数据"""
    try:
        service = await get_tushare_sync_service()
        result = await service.sync_news_data(
            hours_back=hours_back,
            max_news_per_stock=max_news_per_stock,
            job_id="tushare_news_sync",
        )
        logger.info(f"✅ Tushare新闻数据同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Tushare新闻数据同步失败: {e}")
        raise
