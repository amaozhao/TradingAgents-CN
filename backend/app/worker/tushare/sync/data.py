# ruff: noqa: F401,F403,F405,F821
async def run_tushare_status_check():
    """APScheduler任务：检查同步状态"""
    try:
        service = await get_tushare_sync_service()
        result = await service.get_sync_status()
        logger.info(f"✅ Tushare状态检查完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Tushare状态检查失败: {e}")
        return {"error": str(e)}
