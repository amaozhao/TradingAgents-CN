from .models import AKShareSyncService

_akshare_sync_service = None


async def get_akshare_sync_service() -> AKShareSyncService:
    """获取AKShare同步服务实例"""
    global _akshare_sync_service
    if _akshare_sync_service is None:
        _akshare_sync_service = AKShareSyncService()
        await _akshare_sync_service.initialize()
    return _akshare_sync_service
