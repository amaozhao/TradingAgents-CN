# ruff: noqa: F401,F403,F405,F821
async def prepare_stock_data_async(
    stock_code: str,
    market_type: str = "auto",
    period_days: Optional[int] = None,
    analysis_date: Optional[str] = None,
) -> StockDataPreparationResult:
    """
    异步版本：预获取和验证股票数据

    🔥 专门用于 FastAPI 异步上下文，避免事件循环冲突

    Args:
        stock_code: 股票代码
        market_type: 市场类型 ("A股", "港股", "美股", "auto")
        period_days: 历史数据时长（天），默认30天
        analysis_date: 分析日期，默认为今天

    Returns:
        StockDataPreparationResult: 数据准备结果
    """
    preparer = get_stock_preparer()

    # 使用异步版本的内部方法
    if period_days is None:
        period_days = preparer.default_period_days

    analysis_date_value = analysis_date or datetime.now().strftime("%Y-%m-%d")

    logger.info(
        f"📊 [数据准备-异步] 开始准备股票数据: {stock_code} (市场: {market_type}, 时长: {period_days}天)"
    )

    # 1. 基本格式验证（同步操作）
    format_result = preparer._validate_format(stock_code, market_type)
    if not format_result.is_valid:
        return format_result

    # 2. 自动检测市场类型
    if market_type == "auto":
        market_type = preparer._detect_market_type(stock_code)
        logger.debug(f"📊 [数据准备-异步] 自动检测市场类型: {market_type}")

    # 3. 预获取数据并验证（使用异步版本）
    return await preparer._prepare_data_by_market_async(
        stock_code, market_type, period_days, analysis_date_value
    )
