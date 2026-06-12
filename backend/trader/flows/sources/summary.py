from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .provider import USDataSourceManager
    from .runtime import _us_data_source_manager


def get_us_data_source_manager() -> USDataSourceManager:
    """获取全局美股数据源管理器实例"""
    global _us_data_source_manager
    if _us_data_source_manager is None:
        _us_data_source_manager = USDataSourceManager()
    return _us_data_source_manager
