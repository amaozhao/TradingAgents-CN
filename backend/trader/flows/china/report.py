from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .status import _china_data_provider
    from .task import OptimizedChinaDataProvider


def get_optimized_china_data_provider() -> OptimizedChinaDataProvider:
    """获取全局A股数据提供器实例"""
    global _china_data_provider
    if _china_data_provider is None:
        _china_data_provider = OptimizedChinaDataProvider()
    return _china_data_provider
