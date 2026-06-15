from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .provider import USDataSourceManager
    from .runtime import _us_data_source_manager


def get_us_data_source_manager() -> USDataSourceManager:
    """获取全局美股数据源管理器实例"""
    global _us_data_source_manager
    if _us_data_source_manager is None:
        manager_class = globals().get("USDataSourceManager")
        if manager_class is None:
            manager_class = USDataSourceManager
        _us_data_source_manager = manager_class()
    return _us_data_source_manager


async def get_us_data_source_manager_async() -> USDataSourceManager:
    """获取已加载异步数据库配置的全局美股数据源管理器实例。"""
    manager = get_us_data_source_manager()
    if not getattr(manager, "_async_database_config_loaded", False):
        loader = getattr(manager, "load_available_sources_async", None)
        if callable(loader):
            await loader()
        setattr(manager, "_async_database_config_loaded", True)
    return manager
