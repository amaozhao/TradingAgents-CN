from .imports import Optional
from .route import prepare_stock_data

def is_stock_data_ready(
    stock_code: str,
    market_type: str = "auto",
    period_days: Optional[int] = None,
    analysis_date: Optional[str] = None,
) -> bool:
    """
    便捷函数：检查股票数据是否准备就绪

    Args:
        stock_code: 股票代码
        market_type: 市场类型 ("A股", "港股", "美股", "auto")
        period_days: 历史数据时长（天），默认30天
        analysis_date: 分析日期，默认为今天

    Returns:
        bool: 数据是否准备就绪
    """
    result = prepare_stock_data(stock_code, market_type, period_days, analysis_date)
    return result.is_valid
