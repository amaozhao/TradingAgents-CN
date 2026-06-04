# ruff: noqa: F401,F403,F405,F821
def get_china_stock_data_cached(
    symbol: str, start_date: str, end_date: str, force_refresh: bool = False
) -> str:
    """
    获取A股数据的便捷函数

    Args:
        symbol: 股票代码（6位数字）
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        force_refresh: 是否强制刷新缓存

    Returns:
        格式化的股票数据字符串
    """
    provider = get_optimized_china_data_provider()
    return provider.get_stock_data(symbol, start_date, end_date, force_refresh)
