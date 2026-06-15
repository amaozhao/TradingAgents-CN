from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .service import DataSourceManager

_data_source_manager: DataSourceManager | None = None


def get_data_source_manager() -> DataSourceManager:
    """获取全局数据源管理器实例"""
    global _data_source_manager
    if _data_source_manager is None:
        manager_class = globals().get("DataSourceManager")
        if manager_class is None:
            manager_class = getattr(
                importlib.import_module("trader.flows.sources"), "DataSourceManager"
            )
        _data_source_manager = manager_class()
    return _data_source_manager


async def get_data_source_manager_async() -> DataSourceManager:
    """获取已加载异步数据库配置的全局数据源管理器实例。"""
    manager = get_data_source_manager()
    if not getattr(manager, "_async_database_config_loaded", False):
        loader = getattr(manager, "load_available_sources_async", None)
        if callable(loader):
            await loader()
        setattr(manager, "_async_database_config_loaded", True)
    return manager
