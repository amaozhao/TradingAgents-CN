from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import AKShareSyncService
    from .service import _akshare_sync_service


async def get_akshare_sync_service() -> AKShareSyncService:
    """获取AKShare同步服务实例"""
    global _akshare_sync_service
    if _akshare_sync_service is None:
        _akshare_sync_service = AKShareSyncService()
        await _akshare_sync_service.initialize()
    return _akshare_sync_service
