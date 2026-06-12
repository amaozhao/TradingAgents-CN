from .base import _TushareSyncServiceMixin2
from .common import _TushareSyncServiceMixin1
from .models import _TushareSyncServiceMixin3


class TushareSyncService(_TushareSyncServiceMixin1, _TushareSyncServiceMixin2, _TushareSyncServiceMixin3):
    """
    Tushare数据同步服务
    负责将Tushare数据同步到PostgreSQL标准化集合
    """
