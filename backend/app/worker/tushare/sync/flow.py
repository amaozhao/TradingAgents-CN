# ruff: noqa: F401,F403,F405,F821
async def run_tushare_financial_sync():
    """APScheduler任务：同步财务数据（获取最近20期，约5年）"""
    try:
        service = await get_tushare_sync_service()
        result = await service.sync_financial_data(
            limit=20, job_id="tushare_financial_sync"
        )  # 获取最近20期（约5年数据）
        logger.info(f"✅ Tushare财务数据同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Tushare财务数据同步失败: {e}")
        raise
