from trader.utils.validation import StockDataPreparer


def test_missing_history_with_basic_info_points_to_no_trading_data():
    preparer = StockDataPreparer()

    suggestion = preparer._missing_history_suggestion(
        has_basic_info=True,
        stock_code="601989",
        analysis_date="2026-06-11",
    )

    assert "分析日期 2026-06-11 附近没有可用交易数据" in suggestion
    assert "停牌、退市、终止上市、换股合并" in suggestion
    assert "请检查网络连接或数据源配置" not in suggestion


def test_missing_history_without_basic_info_keeps_data_source_guidance():
    preparer = StockDataPreparer()

    suggestion = preparer._missing_history_suggestion(
        has_basic_info=False,
        stock_code="601989",
        analysis_date="2026-06-11",
    )

    assert "请检查网络连接或数据源配置" in suggestion
