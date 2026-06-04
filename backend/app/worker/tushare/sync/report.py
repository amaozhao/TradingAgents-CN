# ruff: noqa: F401,F403,F405,F821
async def run_tushare_basic_info_sync(force_update: bool = False):
    """APScheduler任务：同步股票基础信息"""
    try:
        service = await get_tushare_sync_service()
        result = await service.sync_stock_basic_info(
            force_update, job_id="tushare_basic_info_sync"
        )
        logger.info(f"✅ Tushare基础信息同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Tushare基础信息同步失败: {e}")
        raise
