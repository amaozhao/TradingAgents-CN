from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .imports import logger
    from .query import TushareProvider

def get_tushare_provider() -> TushareProvider:
    """获取全局Tushare提供器实例"""
    global _tushare_provider, _tushare_provider_initialized
    if _tushare_provider is None:
        _tushare_provider = TushareProvider()
        # 使用同步连接方法，避免异步上下文问题
        if not _tushare_provider_initialized:
            try:
                # 直接使用同步连接方法
                _tushare_provider.connect_sync()
                _tushare_provider_initialized = True
            except Exception as e:
                logger.warning(f"⚠️ Tushare自动连接失败: {e}")
    return _tushare_provider
