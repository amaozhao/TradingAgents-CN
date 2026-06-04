# ruff: noqa: F401,F403,F405,F821
async def run_akshare_historical_sync(incremental: bool = True):
    """APScheduler任务：同步历史数据"""
    try:
        service = await get_akshare_sync_service()
        result = await service.sync_historical_data(incremental=incremental)
        logger.info(f"✅ AKShare历史数据同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ AKShare历史数据同步失败: {e}")
        raise
