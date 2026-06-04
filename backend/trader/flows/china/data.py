# ruff: noqa: F401,F403,F405,F821
def get_china_fundamentals_cached(symbol: str, force_refresh: bool = False) -> str:
    """
    获取A股基本面数据的便捷函数

    Args:
        symbol: 股票代码（6位数字）
        force_refresh: 是否强制刷新缓存

    Returns:
        格式化的基本面数据字符串
    """
    provider = get_optimized_china_data_provider()
    return provider.get_fundamentals_data(symbol, force_refresh)
