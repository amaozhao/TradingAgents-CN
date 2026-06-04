# ruff: noqa: F401,F403,F405,F821
def get_stock_preparer(default_period_days: int = 30) -> StockDataPreparer:
    """获取股票数据准备器实例（单例模式）"""
    global _stock_preparer
    if _stock_preparer is None:
        _stock_preparer = StockDataPreparer(default_period_days)
    return _stock_preparer
