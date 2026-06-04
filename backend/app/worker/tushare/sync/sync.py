# ruff: noqa: F401,F403,F405,F821
async def run_tushare_historical_sync(incremental: bool = True):
    """APScheduler任务：同步历史数据"""
    logger.info(
        f"🚀 [APScheduler] 开始执行 Tushare 历史数据同步任务 (incremental={incremental})"
    )
    try:
        service = await get_tushare_sync_service()
        logger.info("✅ [APScheduler] Tushare 同步服务已初始化")
        result = await service.sync_historical_data(
            incremental=incremental, job_id="tushare_historical_sync"
        )
        logger.info(f"✅ [APScheduler] Tushare历史数据同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ [APScheduler] Tushare历史数据同步失败: {e}")
        traceback = importlib.import_module("traceback")
        logger.error(f"详细错误: {traceback.format_exc()}")
        raise
