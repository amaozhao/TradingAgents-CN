from trader.agents.analysts import fundamentals


def test_fundamentals_company_name_helper_is_available_for_node_globals():
    assert hasattr(fundamentals, "_get_company_name_for_fundamentals")


def test_fundamentals_company_name_helper_handles_us_stocks_without_io():
    market_info = {"is_china": False, "is_hk": False, "is_us": True}

    assert (
        fundamentals._get_company_name_for_fundamentals("AAPL", market_info)
        == "苹果公司"
    )
    assert (
        fundamentals._get_company_name_for_fundamentals("UNKNOWN", market_info)
        == "美股UNKNOWN"
    )
