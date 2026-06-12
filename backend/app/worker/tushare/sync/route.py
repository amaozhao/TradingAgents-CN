from .query import TushareSyncService

_tushare_sync_service = None


async def get_tushare_sync_service() -> TushareSyncService:
    """获取Tushare同步服务实例"""
    global _tushare_sync_service
    if _tushare_sync_service is None:
        _tushare_sync_service = TushareSyncService()
        await _tushare_sync_service.initialize()
    return _tushare_sync_service
