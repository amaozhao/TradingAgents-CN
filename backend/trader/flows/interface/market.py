# ruff: noqa: F401,F403,F405,F821,F722
def get_stockstats_indicator(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[
        str, "The current trading date you are trading on, YYYY-mm-dd"
    ],
    online: Annotated[bool, "to fetch data online or offline"],
) -> str:

    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    curr_date_text = curr_dt.strftime("%Y-%m-%d")

    try:
        if StockstatsUtils is None:
            raise RuntimeError("StockstatsUtils unavailable")
        indicator_value = StockstatsUtils.get_stock_stats(
            symbol,
            indicator,
            curr_date_text,
            os.path.join(DATA_DIR, "market_data", "price_data"),
            online=online,
        )
    except Exception as e:
        print(
            f"Error getting stockstats indicator data for indicator {indicator} on {curr_date_text}: {e}"
        )
        return ""

    return str(indicator_value)


def get_yfin_data_window(
    symbol: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "how many days to look back"],
) -> str:
    # calculate past days
    date_obj = datetime.strptime(curr_date, "%Y-%m-%d")
    before = date_obj - relativedelta(days=look_back_days)
    start_date = before.strftime("%Y-%m-%d")

    # read in data
    data = pd.read_csv(
        os.path.join(
            DATA_DIR,
            f"market_data/price_data/{symbol}-YFin-data-2015-01-01-2025-03-25.csv",
        )
    )

    # Extract just the date part for comparison
    data["DateOnly"] = data["Date"].str[:10]

    # Filter data between the start and end dates (inclusive)
    filtered_data = data[
        (data["DateOnly"] >= start_date) & (data["DateOnly"] <= curr_date)
    ]

    # Drop the temporary column we created
    filtered_data = filtered_data.drop("DateOnly", axis=1)

    # Set pandas display options to show the full DataFrame
    with pd.option_context(
        "display.max_rows", None, "display.max_columns", None, "display.width", None
    ):
        df_string = filtered_data.to_string()

    return (
        f"## Raw Market Data for {symbol} from {start_date} to {curr_date}:\n\n"
        + df_string
    )


def get_yfin_data_online(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
):
    # 检查yfinance是否可用
    if not YF_AVAILABLE or yf is None:
        return "yfinance库不可用，无法获取美股数据"

    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    # Create ticker object
    ticker = yf.Ticker(symbol.upper())

    # Fetch historical data for the specified date range
    data = ticker.history(start=start_date, end=end_date)

    # Check if data is empty
    if data.empty:
        return (
            f"No data found for symbol '{symbol}' between {start_date} and {end_date}"
        )

    # Remove timezone info from index for cleaner output
    data_index = cast(Any, data.index)
    if data_index.tz is not None:
        data.index = data_index.tz_localize(None)

    # Round numerical values to 2 decimal places for cleaner display
    numeric_columns = ["Open", "High", "Low", "Close", "Adj Close"]
    for col in numeric_columns:
        if col in data.columns:
            data[col] = data[col].round(2)

    # Convert DataFrame to CSV string
    csv_string = data.to_csv()

    # Add header information
    header = f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n"
    header += f"# Total records: {len(data)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    return header + csv_string


def get_yfin_data(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> pd.DataFrame:
    # read in data
    data = pd.read_csv(
        os.path.join(
            DATA_DIR,
            f"market_data/price_data/{symbol}-YFin-data-2015-01-01-2025-03-25.csv",
        )
    )

    if end_date > "2025-03-25":
        raise Exception(
            f"Get_YFin_Data: {end_date} is outside of the data range of 2015-01-01 to 2025-03-25"
        )

    # Extract just the date part for comparison
    data["DateOnly"] = data["Date"].str[:10]

    # Filter data between the start and end dates (inclusive)
    filtered_data = data[
        (data["DateOnly"] >= start_date) & (data["DateOnly"] <= end_date)
    ]

    # Drop the temporary column we created
    filtered_data = filtered_data.drop("DateOnly", axis=1)

    # remove the index from the dataframe
    filtered_data = filtered_data.reset_index(drop=True)

    return cast(pd.DataFrame, filtered_data)


def get_stock_news_openai(ticker, curr_date):
    config = get_config()
    client = OpenAI(base_url=config["backend_url"])

    response = client.responses.create(
        model=config["quick_think_llm"],
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"Can you search Social Media for {ticker} from 7 days before {curr_date} to {curr_date}? Make sure you only get the data posted during that period.",
                    }
                ],
            }
        ],
        text={"format": {"type": "text"}},
        reasoning={},
        tools=[
            {
                "type": "web_search_preview",
                "user_location": {"type": "approximate"},
                "search_context_size": "low",
            }
        ],
        temperature=1,
        max_output_tokens=4096,
        top_p=1,
        store=True,
    )

    return _openai_response_text(response)


def get_global_news_openai(curr_date, look_back_days: int = 7, max_limit: int = 10):
    config = get_config()
    client = OpenAI(base_url=config["backend_url"])

    response = client.responses.create(
        model=config["quick_think_llm"],
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"Can you search global or macroeconomics news from {look_back_days} days before {curr_date} to {curr_date} that would be informative for trading purposes? Make sure you only get the data posted during that period. Return at most {max_limit} items.",
                    }
                ],
            }
        ],
        text={"format": {"type": "text"}},
        reasoning={},
        tools=[
            {
                "type": "web_search_preview",
                "user_location": {"type": "approximate"},
                "search_context_size": "low",
            }
        ],
        temperature=1,
        max_output_tokens=4096,
        top_p=1,
        store=True,
    )

    return _openai_response_text(response)


def get_fundamentals_finnhub(ticker, curr_date):
    """
    使用Finnhub API获取股票基本面数据作为OpenAI的备选方案
    Args:
        ticker (str): 股票代码
        curr_date (str): 当前日期，格式为yyyy-mm-dd
    Returns:
        str: 格式化的基本面数据报告
    """
    try:
        finnhub = importlib.import_module("finnhub")
        # 导入缓存管理器（统一入口）
        get_cache = getattr(importlib.import_module("trader.flows.cache"), "get_cache")
        cache = get_cache()
        cached_key = cache.find_cached_fundamentals_data(ticker, data_source="finnhub")
        if cached_key:
            cached_data = cache.load_fundamentals_data(cached_key)
            if cached_data:
                logger.debug(f"💾 [DEBUG] 从缓存加载Finnhub基本面数据: {ticker}")
                return cached_data

        # 获取Finnhub API密钥
        api_key = settings.FINNHUB_API_KEY
        if not api_key:
            return "错误：未配置FINNHUB_API_KEY"

        # 初始化Finnhub客户端
        finnhub_client = finnhub.Client(api_key=api_key)

        logger.debug(f"📊 [DEBUG] 使用Finnhub API获取 {ticker} 的基本面数据...")

        # 获取基本财务数据
        try:
            basic_financials = finnhub_client.company_basic_financials(ticker, "all")
        except Exception as e:
            logger.error(f"❌ [DEBUG] Finnhub基本财务数据获取失败: {str(e)}")
            basic_financials = None

        # 获取公司概况
        try:
            company_profile = finnhub_client.company_profile2(symbol=ticker)
        except Exception as e:
            logger.error(f"❌ [DEBUG] Finnhub公司概况获取失败: {str(e)}")
            company_profile = None

        # 获取收益数据
        try:
            earnings = finnhub_client.company_earnings(ticker, limit=4)
        except Exception as e:
            logger.error(f"❌ [DEBUG] Finnhub收益数据获取失败: {str(e)}")
            earnings = None

        # 格式化报告
        report = f"# {ticker} 基本面分析报告（Finnhub数据源）\n\n"
        report += f"**数据获取时间**: {curr_date}\n"
        report += "**数据来源**: Finnhub API\n\n"

        # 公司概况部分
        if company_profile:
            report += "## 公司概况\n"
            report += f"- **公司名称**: {company_profile.get('name', 'N/A')}\n"
            report += f"- **行业**: {company_profile.get('finnhubIndustry', 'N/A')}\n"
            report += f"- **国家**: {company_profile.get('country', 'N/A')}\n"
            report += f"- **货币**: {company_profile.get('currency', 'N/A')}\n"
            report += f"- **市值**: {company_profile.get('marketCapitalization', 'N/A')} 百万美元\n"
            report += f"- **流通股数**: {company_profile.get('shareOutstanding', 'N/A')} 百万股\n\n"

        # 基本财务指标
        if basic_financials and "metric" in basic_financials:
            metrics = basic_financials["metric"]
            report += "## 关键财务指标\n"
            report += "| 指标 | 数值 |\n"
            report += "|------|------|\n"

            # 估值指标
            if "peBasicExclExtraTTM" in metrics:
                report += f"| 市盈率 (PE) | {metrics['peBasicExclExtraTTM']:.2f} |\n"
            if "psAnnual" in metrics:
                report += f"| 市销率 (PS) | {metrics['psAnnual']:.2f} |\n"
            if "pbAnnual" in metrics:
                report += f"| 市净率 (PB) | {metrics['pbAnnual']:.2f} |\n"

            # 盈利能力指标
            if "roeTTM" in metrics:
                report += f"| 净资产收益率 (ROE) | {metrics['roeTTM']:.2f}% |\n"
            if "roaTTM" in metrics:
                report += f"| 总资产收益率 (ROA) | {metrics['roaTTM']:.2f}% |\n"
            if "netProfitMarginTTM" in metrics:
                report += f"| 净利润率 | {metrics['netProfitMarginTTM']:.2f}% |\n"

            # 财务健康指标
            if "currentRatioAnnual" in metrics:
                report += f"| 流动比率 | {metrics['currentRatioAnnual']:.2f} |\n"
            if "totalDebt/totalEquityAnnual" in metrics:
                report += (
                    f"| 负债权益比 | {metrics['totalDebt/totalEquityAnnual']:.2f} |\n"
                )

            report += "\n"

        # 收益历史
        if earnings:
            report += "## 收益历史\n"
            report += "| 季度 | 实际EPS | 预期EPS | 差异 |\n"
            report += "|------|---------|---------|------|\n"
            for earning in earnings[:4]:  # 显示最近4个季度
                actual = earning.get("actual", "N/A")
                estimate = earning.get("estimate", "N/A")
                period = earning.get("period", "N/A")
                surprise = earning.get("surprise", "N/A")
                report += f"| {period} | {actual} | {estimate} | {surprise} |\n"
            report += "\n"

        # 数据可用性说明
        report += "## 数据说明\n"
        report += "- 本报告使用Finnhub API提供的官方财务数据\n"
        report += "- 数据来源于公司财报和SEC文件\n"
        report += "- TTM表示过去12个月数据\n"
        report += "- Annual表示年度数据\n\n"

        if not basic_financials and not company_profile and not earnings:
            report += "⚠️ **警告**: 无法获取该股票的基本面数据，可能原因：\n"
            report += "- 股票代码不正确\n"
            report += "- Finnhub API限制\n"
            report += "- 该股票暂无基本面数据\n"

        # 保存到缓存
        if report and len(report) > 100:  # 只有当报告有实际内容时才缓存
            cache.save_fundamentals_data(ticker, report, data_source="finnhub")

        logger.debug(f"📊 [DEBUG] Finnhub基本面数据获取完成，报告长度: {len(report)}")
        return report

    except ImportError:
        return "错误：未安装finnhub-python库，请运行: pip install finnhub-python"
    except Exception as e:
        logger.error(f"❌ [DEBUG] Finnhub基本面数据获取失败: {str(e)}")
        return f"Finnhub基本面数据获取失败: {str(e)}"
