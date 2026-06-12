from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import _AKShareSyncServiceMixin2
    from .common import _AKShareSyncServiceMixin1


class AKShareSyncService(_AKShareSyncServiceMixin1, _AKShareSyncServiceMixin2):
    """
    AKShare数据同步服务

    提供完整的数据同步功能：
    - 股票基础信息同步
    - 实时行情同步
    - 历史数据同步
    - 财务数据同步
    """
