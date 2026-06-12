from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .query import AKShareProvider
    from .task import _akshare_provider


def get_akshare_provider() -> AKShareProvider:
    """获取全局AKShare提供器实例"""
    global _akshare_provider
    if _akshare_provider is None:
        _akshare_provider = AKShareProvider()
    return _akshare_provider
