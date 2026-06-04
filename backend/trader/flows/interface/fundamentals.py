# ruff: noqa: F401,F403,F405,F821,F722
def get_fundamentals_openai(ticker, curr_date):
    """
    获取美股基本面数据，使用数据源管理器自动选择和降级

    支持的数据源（按数据库配置的优先级）：
    - Alpha Vantage: 基本面和新闻数据（准确度高）
    - yfinance: 股票价格和基本信息（免费）
    - Finnhub: 备用数据源
    - OpenAI: 使用 AI 搜索基本面信息（需要配置）

    优先级从数据库 datasource_groupings 集合读取（market_category_id='us_stocks'）

    Args:
        ticker (str): 股票代码
        curr_date (str): 当前日期，格式为yyyy-mm-dd
    Returns:
        str: 基本面数据报告
    """
    try:
        # 导入缓存管理器和数据源管理器
        get_cache = getattr(importlib.import_module("trader.flows.cache"), "get_cache")
        get_us_data_source_manager = getattr(
            importlib.import_module("trader.flows.sources"),
            "get_us_data_source_manager",
        )
        USDataSource = getattr(
            importlib.import_module("trader.flows.sources"), "USDataSource"
        )

        cache = get_cache()
        us_manager = get_us_data_source_manager()

        # 检查缓存 - 按数据源优先级检查
        data_source_cache_names = {
            USDataSource.ALPHA_VANTAGE: "alpha_vantage",
            USDataSource.YFINANCE: "yfinance",
            USDataSource.FINNHUB: "finnhub",
        }

        for source in us_manager.available_sources:
            if source == USDataSource.POSTGRES:
                continue  # PostgreSQL 缓存单独处理

            cache_name = data_source_cache_names.get(source)
            if cache_name:
                cached_key = cache.find_cached_fundamentals_data(
                    ticker, data_source=cache_name
                )
                if cached_key:
                    cached_data = cache.load_fundamentals_data(cached_key)
                    if cached_data:
                        logger.info(
                            f"💾 [缓存] 从 {cache_name} 缓存加载基本面数据: {ticker}"
                        )
                        return cached_data

        # 🔥 从数据库获取数据源优先级顺序
        priority_order = us_manager._get_data_source_priority_order(ticker)
        logger.info(
            f"📊 [美股基本面] 数据源优先级: {[s.value for s in priority_order]}"
        )

        # 按优先级尝试每个数据源
        for source in priority_order:
            try:
                if source == USDataSource.ALPHA_VANTAGE:
                    result = _get_fundamentals_alpha_vantage(ticker, curr_date, cache)
                    if result:
                        return result

                elif source == USDataSource.YFINANCE:
                    result = _get_fundamentals_yfinance(ticker, curr_date, cache)
                    if result:
                        return result

                elif source == USDataSource.FINNHUB:
                    result = get_fundamentals_finnhub(ticker, curr_date)
                    if result and "❌" not in result:
                        cache.save_fundamentals_data(
                            ticker, result, data_source="finnhub"
                        )
                        return result

            except Exception as e:
                logger.warning(f"⚠️ [{source.value}] 获取失败: {e}，尝试下一个数据源")
                continue

        # 🔥 特殊处理：OpenAI（如果配置了）
        config = get_config()
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if (
            openai_api_key
            and config.get("backend_url")
            and config.get("quick_think_llm")
        ):
            backend_url = config.get("backend_url", "")
            if "openai.com" in backend_url:
                try:
                    logger.info("📊 [OpenAI] 尝试使用 OpenAI 获取基本面数据...")
                    return _get_fundamentals_openai_impl(
                        ticker, curr_date, config, cache
                    )
                except Exception as e:
                    logger.warning(f"⚠️ [OpenAI] 获取失败: {e}")

        # 所有数据源都失败
        logger.error(f"❌ [美股基本面] 所有数据源都失败: {ticker}")
        return f"❌ 获取 {ticker} 基本面数据失败：所有数据源都不可用"

    except Exception as e:
        logger.error(f"❌ [美股基本面] 获取失败: {str(e)}")
        return f"❌ 获取 {ticker} 基本面数据失败: {str(e)}"


def _get_fundamentals_alpha_vantage(ticker, curr_date, cache):
    """
    从 Alpha Vantage 获取基本面数据

    Args:
        ticker: 股票代码
        curr_date: 当前日期
        cache: 缓存对象

    Returns:
        str: 基本面数据报告，失败返回 None
    """
    try:
        logger.info(f"📊 [Alpha Vantage] 获取 {ticker} 的基本面数据...")
        get_av_fundamentals = getattr(
            importlib.import_module("trader.flows.providers.us.alpha.fundamentals"),
            "get_fundamentals",
        )

        result = get_av_fundamentals(ticker, curr_date)

        if result and "Error" not in result and len(result) > 100:
            # 保存到缓存
            cache.save_fundamentals_data(ticker, result, data_source="alpha_vantage")
            logger.info(f"✅ [Alpha Vantage] 基本面数据获取成功: {ticker}")
            return result
        else:
            logger.warning("⚠️ [Alpha Vantage] 数据质量不佳")
            return None
    except Exception as e:
        logger.warning(f"⚠️ [Alpha Vantage] 获取失败: {e}")
        return None


def _get_fundamentals_yfinance(ticker, curr_date, cache):
    """
    从 yfinance 获取基本面数据

    Args:
        ticker: 股票代码
        curr_date: 当前日期
        cache: 缓存对象

    Returns:
        str: 基本面数据报告，失败返回 None
    """
    try:
        logger.info(f"📊 [yfinance] 获取 {ticker} 的基本面数据...")
        yf = importlib.import_module("yfinance")

        ticker_obj = yf.Ticker(ticker.upper())
        info = ticker_obj.info

        if info and len(info) > 5:  # 确保有实际数据
            # 格式化 yfinance 数据
            result = f"""# {ticker} 基本面数据 (来源: Yahoo Finance)

## 公司信息
- 公司名称: {info.get("longName", "N/A")}
- 行业: {info.get("industry", "N/A")}
- 板块: {info.get("sector", "N/A")}
- 网站: {info.get("website", "N/A")}

## 估值指标
- 市值: ${info.get("marketCap", "N/A"):,}
- PE比率: {info.get("trailingPE", "N/A")}
- 前瞻PE: {info.get("forwardPE", "N/A")}
- PB比率: {info.get("priceToBook", "N/A")}
- PS比率: {info.get("priceToSalesTrailing12Months", "N/A")}

## 财务指标
- 总收入: ${info.get("totalRevenue", "N/A"):,}
- 毛利润: ${info.get("grossProfits", "N/A"):,}
- EBITDA: ${info.get("ebitda", "N/A"):,}
- 每股收益(EPS): ${info.get("trailingEps", "N/A")}
- 股息率: {info.get("dividendYield", "N/A")}

## 盈利能力
- 利润率: {info.get("profitMargins", "N/A")}
- 营业利润率: {info.get("operatingMargins", "N/A")}
- ROE: {info.get("returnOnEquity", "N/A")}
- ROA: {info.get("returnOnAssets", "N/A")}

## 股价信息
- 当前价格: ${info.get("currentPrice", "N/A")}
- 52周最高: ${info.get("fiftyTwoWeekHigh", "N/A")}
- 52周最低: ${info.get("fiftyTwoWeekLow", "N/A")}
- 50日均线: ${info.get("fiftyDayAverage", "N/A")}
- 200日均线: ${info.get("twoHundredDayAverage", "N/A")}

## 分析师评级
- 目标价: ${info.get("targetMeanPrice", "N/A")}
- 推荐评级: {info.get("recommendationKey", "N/A")}

数据获取时间: {curr_date}
"""
            # 保存到缓存
            cache.save_fundamentals_data(ticker, result, data_source="yfinance")
            logger.info(f"✅ [yfinance] 基本面数据获取成功: {ticker}")
            return result
        else:
            logger.warning("⚠️ [yfinance] 数据不完整")
            return None
    except Exception as e:
        logger.warning(f"⚠️ [yfinance] 获取失败: {e}")
        return None


def _get_fundamentals_openai_impl(ticker, curr_date, config, cache):
    """
    OpenAI 基本面数据获取实现（内部函数）

    Args:
        ticker: 股票代码
        curr_date: 当前日期
        config: 配置对象
        cache: 缓存对象

    Returns:
        str: 基本面数据报告
    """
    try:
        logger.debug(f"📊 [OpenAI] 尝试使用OpenAI获取 {ticker} 的基本面数据...")

        client = OpenAI(base_url=config["backend_url"])

        response = client.responses.create(
            model=config["quick_think_llm"],
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"Can you search Fundamental for discussions on {ticker} during of the month before {curr_date} to the month of {curr_date}. Make sure you only get the data posted during that period. List as a table, with PE/PS/Cash flow/ etc",
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

        result = _openai_response_text(response)

        # 保存到缓存
        if result and len(result) > 100:  # 只有当结果有实际内容时才缓存
            cache.save_fundamentals_data(ticker, result, data_source="openai")

        logger.info(f"✅ [OpenAI] 基本面数据获取成功: {ticker}")
        return result

    except Exception as e:
        logger.error(f"❌ [OpenAI] 基本面数据获取失败: {str(e)}")
        raise  # 抛出异常，让外层函数继续尝试其他数据源


# ==================== Tushare数据接口 ====================
