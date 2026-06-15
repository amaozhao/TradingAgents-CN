from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .imports import logger
    from .query import TushareProvider

def get_tushare_provider(auto_connect: bool = True) -> TushareProvider:
    """获取全局Tushare提供器实例"""
    global _tushare_provider, _tushare_provider_initialized
    if _tushare_provider is None:
        _tushare_provider = TushareProvider()
        # 同步 legacy 调用默认保持自动连接；async runtime 需显式禁用。
        if auto_connect and not _tushare_provider_initialized:
            try:
                _tushare_provider.connect_sync()
                _tushare_provider_initialized = True
            except Exception as e:
                logger.warning(f"⚠️ Tushare自动连接失败: {e}")
    return _tushare_provider
