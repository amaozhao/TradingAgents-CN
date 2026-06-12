from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import _DataSourceManagerMixin2
    from .common import _DataSourceManagerMixin1
    from .models import _DataSourceManagerMixin3
    from .query import _DataSourceManagerMixin4


class DataSourceManager(
    _DataSourceManagerMixin1,
    _DataSourceManagerMixin2,
    _DataSourceManagerMixin3,
    _DataSourceManagerMixin4,
):
    """数据源管理器"""
