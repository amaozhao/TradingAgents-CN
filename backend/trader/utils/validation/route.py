from .imports import Optional, StockDataPreparationResult
from .task import get_stock_preparer

def prepare_stock_data(
    stock_code: str,
    market_type: str = "auto",
    period_days: Optional[int] = None,
    analysis_date: Optional[str] = None,
) -> StockDataPreparationResult:
    """
    便捷函数：预获取和验证股票数据

    Args:
        stock_code: 股票代码
        market_type: 市场类型 ("A股", "港股", "美股", "auto")
        period_days: 历史数据时长（天），默认30天
        analysis_date: 分析日期，默认为今天

    Returns:
        StockDataPreparationResult: 数据准备结果
    """
    preparer = get_stock_preparer()
    return preparer.prepare_stock_data(stock_code, market_type, period_days, analysis_date)
