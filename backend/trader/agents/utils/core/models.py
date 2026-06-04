# ruff: noqa: F401,F403,F405,F821,F722
class _ToolkitMixin3:
    @tool
    @staticmethod
    @log_tool_call(tool_name="get_stock_news_unified", log_args=True)
    def get_stock_news_unified(
        ticker: Annotated[str, "股票代码（支持A股、港股、美股）"],
        curr_date: Annotated[str, "当前日期，格式：YYYY-MM-DD"],
    ) -> str:
        """
        统一的股票新闻工具
        自动识别股票类型（A股、港股、美股）并调用相应的新闻数据源

        Args:
            ticker: 股票代码（如：000001、0700.HK、AAPL）
            curr_date: 当前日期（格式：YYYY-MM-DD）

        Returns:
            str: 新闻分析报告
        """
        logger.info(f"📰 [统一新闻工具] 分析股票: {ticker}")

        try:
            StockUtils = getattr(
                importlib.import_module("trader.utils.stocks"), "StockUtils"
            )
            datetime = getattr(importlib.import_module("datetime"), "datetime")
            timedelta = getattr(importlib.import_module("datetime"), "timedelta")

            # 自动识别股票类型
            market_info = StockUtils.get_market_info(ticker)
            is_china = market_info["is_china"]
            is_hk = market_info["is_hk"]
            market_info["is_us"]

            logger.info(f"📰 [统一新闻工具] 股票类型: {market_info['market_name']}")

            # 计算新闻查询的日期范围
            end_date = datetime.strptime(curr_date, "%Y-%m-%d")
            start_date = end_date - timedelta(days=7)
            start_date_str = start_date.strftime("%Y-%m-%d")

            result_data = []

            if is_china or is_hk:
                # 中国A股和港股：使用AKShare东方财富新闻和Google新闻（中文搜索）
                logger.info("🇨🇳🇭🇰 [统一新闻工具] 处理中文新闻...")

                # 1. 尝试获取AKShare东方财富新闻
                try:
                    # 处理股票代码
                    clean_ticker = (
                        ticker.replace(".SH", "")
                        .replace(".SZ", "")
                        .replace(".SS", "")
                        .replace(".HK", "")
                        .replace(".XSHE", "")
                        .replace(".XSHG", "")
                    )

                    logger.info(
                        f"🇨🇳🇭🇰 [统一新闻工具] 尝试获取东方财富新闻: {clean_ticker}"
                    )

                    # 通过 AKShare Provider 获取新闻
                    AKShareProvider = getattr(
                        importlib.import_module("trader.flows.providers.china.akshare"),
                        "AKShareProvider",
                    )

                    provider = AKShareProvider()

                    # 获取东方财富新闻
                    news_df = provider.get_stock_news_sync(symbol=clean_ticker)

                    if news_df is not None and not news_df.empty:
                        # 格式化东方财富新闻
                        em_news_items = []
                        for _, row in news_df.iterrows():
                            # AKShare 返回的字段名
                            news_title = row.get("新闻标题", "") or row.get("标题", "")
                            news_time = row.get("发布时间", "") or row.get("时间", "")
                            news_url = row.get("新闻链接", "") or row.get("链接", "")

                            news_item = f"- **{news_title}** [{news_time}]({news_url})"
                            em_news_items.append(news_item)

                        # 添加到结果中
                        if em_news_items:
                            em_news_text = "\n".join(em_news_items)
                            result_data.append(f"## 东方财富新闻\n{em_news_text}")
                            logger.info(
                                f"🇨🇳🇭🇰 [统一新闻工具] 成功获取{len(em_news_items)}条东方财富新闻"
                            )
                except Exception as em_e:
                    logger.error(f"❌ [统一新闻工具] 东方财富新闻获取失败: {em_e}")
                    result_data.append(f"## 东方财富新闻\n获取失败: {em_e}")

                # 2. 获取Google新闻作为补充
                try:
                    # 获取公司中文名称用于搜索
                    if is_china:
                        # A股使用股票代码搜索，添加更多中文关键词
                        clean_ticker = (
                            ticker.replace(".SH", "")
                            .replace(".SZ", "")
                            .replace(".SS", "")
                            .replace(".XSHE", "")
                            .replace(".XSHG", "")
                        )
                        search_query = f"{clean_ticker} 股票 公司 财报 新闻"
                        logger.info(
                            f"🇨🇳 [统一新闻工具] A股Google新闻搜索关键词: {search_query}"
                        )
                    else:
                        # 港股使用代码搜索
                        search_query = f"{ticker} 港股"
                        logger.info(
                            f"🇭🇰 [统一新闻工具] 港股Google新闻搜索关键词: {search_query}"
                        )

                    get_google_news = getattr(
                        importlib.import_module("trader.flows.interface"),
                        "get_google_news",
                    )
                    news_data = get_google_news(search_query, curr_date)
                    result_data.append(f"## Google新闻\n{news_data}")
                    logger.info("🇨🇳🇭🇰 [统一新闻工具] 成功获取Google新闻")
                except Exception as google_e:
                    logger.error(f"❌ [统一新闻工具] Google新闻获取失败: {google_e}")
                    result_data.append(f"## Google新闻\n获取失败: {google_e}")

            else:
                # 美股：使用Finnhub新闻
                logger.info("🇺🇸 [统一新闻工具] 处理美股新闻...")

                try:
                    get_finnhub_news = getattr(
                        importlib.import_module("trader.flows.interface"),
                        "get_finnhub_news",
                    )
                    look_back_days = (
                        datetime.strptime(curr_date, "%Y-%m-%d")
                        - datetime.strptime(start_date_str, "%Y-%m-%d")
                    ).days
                    news_data = get_finnhub_news(ticker, curr_date, look_back_days)
                    result_data.append(f"## 美股新闻\n{news_data}")
                except Exception as e:
                    result_data.append(f"## 美股新闻\n获取失败: {e}")

            # 组合所有数据
            combined_result = f"""# {ticker} 新闻分析

**股票类型**: {market_info["market_name"]}
**分析日期**: {curr_date}
**新闻时间范围**: {start_date_str} 至 {curr_date}

{chr(10).join(result_data)}

---
*数据来源: 根据股票类型自动选择最适合的新闻源*
"""

            logger.info(
                f"📰 [统一新闻工具] 数据获取完成，总长度: {len(combined_result)}"
            )
            return combined_result

        except Exception as e:
            error_msg = f"统一新闻工具执行失败: {str(e)}"
            logger.error(f"❌ [统一新闻工具] {error_msg}")
            return error_msg

    @tool
    @staticmethod
    @log_tool_call(tool_name="get_stock_sentiment_unified", log_args=True)
    def get_stock_sentiment_unified(
        ticker: Annotated[str, "股票代码（支持A股、港股、美股）"],
        curr_date: Annotated[str, "当前日期，格式：YYYY-MM-DD"],
    ) -> str:
        """
        统一的股票情绪分析工具
        自动识别股票类型（A股、港股、美股）并调用相应的情绪数据源

        Args:
            ticker: 股票代码（如：000001、0700.HK、AAPL）
            curr_date: 当前日期（格式：YYYY-MM-DD）

        Returns:
            str: 情绪分析报告
        """
        logger.info(f"😊 [统一情绪工具] 分析股票: {ticker}")

        try:
            StockUtils = getattr(
                importlib.import_module("trader.utils.stocks"), "StockUtils"
            )

            # 自动识别股票类型
            market_info = StockUtils.get_market_info(ticker)
            is_china = market_info["is_china"]
            is_hk = market_info["is_hk"]
            market_info["is_us"]

            logger.info(f"😊 [统一情绪工具] 股票类型: {market_info['market_name']}")

            result_data = []

            if is_china or is_hk:
                # 中国A股和港股：使用社交媒体情绪分析
                logger.info("🇨🇳🇭🇰 [统一情绪工具] 处理中文市场情绪...")

                try:
                    # 可以集成微博、雪球、东方财富等中文社交媒体情绪
                    # 目前使用基础的情绪分析
                    sentiment_summary = f"""
## 中文市场情绪分析

**股票**: {ticker} ({market_info["market_name"]})
**分析日期**: {curr_date}

### 市场情绪概况
- 由于中文社交媒体情绪数据源暂未完全集成，当前提供基础分析
- 建议关注雪球、东方财富、同花顺等平台的讨论热度
- 港股市场还需关注香港本地财经媒体情绪

### 情绪指标
- 整体情绪: 中性
- 讨论热度: 待分析
- 投资者信心: 待评估

*注：完整的中文社交媒体情绪分析功能正在开发中*
"""
                    result_data.append(sentiment_summary)
                except Exception as e:
                    result_data.append(f"## 中文市场情绪\n获取失败: {e}")

            else:
                # 美股：使用Reddit情绪分析
                logger.info("🇺🇸 [统一情绪工具] 处理美股情绪...")

                try:
                    sentiment_data = interface.get_reddit_company_news(
                        ticker, curr_date, 7, 5
                    )
                    result_data.append(f"## 美股Reddit情绪\n{sentiment_data}")
                except Exception as e:
                    result_data.append(f"## 美股Reddit情绪\n获取失败: {e}")

            # 组合所有数据
            combined_result = f"""# {ticker} 情绪分析

**股票类型**: {market_info["market_name"]}
**分析日期**: {curr_date}

{chr(10).join(result_data)}

---
*数据来源: 根据股票类型自动选择最适合的情绪数据源*
"""

            logger.info(
                f"😊 [统一情绪工具] 数据获取完成，总长度: {len(combined_result)}"
            )
            return combined_result

        except Exception as e:
            error_msg = f"统一情绪分析工具执行失败: {str(e)}"
            logger.error(f"❌ [统一情绪工具] {error_msg}")
            return error_msg
