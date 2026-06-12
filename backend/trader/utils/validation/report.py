from .imports import Optional
from .route import prepare_stock_data

def get_stock_preparation_message(
    stock_code: str,
    market_type: str = "auto",
    period_days: Optional[int] = None,
    analysis_date: Optional[str] = None,
) -> str:
    """
    便捷函数：获取股票数据准备消息

    Args:
        stock_code: 股票代码
        market_type: 市场类型 ("A股", "港股", "美股", "auto")
        period_days: 历史数据时长（天），默认30天
        analysis_date: 分析日期，默认为今天

    Returns:
        str: 数据准备消息
    """
    result = prepare_stock_data(stock_code, market_type, period_days, analysis_date)

    if result.is_valid:
        return f"✅ 数据准备成功: {result.stock_code} ({result.market_type}) - {result.stock_name}\n📊 {result.cache_status}"
    else:
        return f"❌ 数据准备失败: {result.error_message}\n💡 建议: {result.suggestion}"
