from .imports import ZoneInfo, datetime, get_timezone_name, importlib, logger
from .models import RealtimeNewsAggregator

def get_realtime_stock_news(ticker: str, curr_date: str, hours_back: int = 6) -> str:
    """
    获取实时股票新闻的主要接口函数
    """
    logger.info("[新闻分析] ========== 函数入口 ==========")
    logger.info("[新闻分析] 函数: get_realtime_stock_news")
    logger.info(f"[新闻分析] 参数: ticker={ticker}, curr_date={curr_date}, hours_back={hours_back}")
    logger.info(f"[新闻分析] 开始获取 {ticker} 的实时新闻，日期: {curr_date}, 回溯时间: {hours_back}小时")
    start_total_time = datetime.now(ZoneInfo(get_timezone_name()))
    logger.info(f"[新闻分析] 开始时间: {start_total_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")

    # 判断股票类型
    logger.info("[新闻分析] ========== 步骤1: 股票类型判断 ==========")
    stock_type = "未知"
    is_china_stock = False
    logger.info(f"[新闻分析] 原始ticker: {ticker}")

    if "." in ticker:
        logger.info("[新闻分析] 检测到ticker包含点号，进行后缀匹配")
        if any(suffix in ticker for suffix in [".SH", ".SZ", ".SS", ".XSHE", ".XSHG"]):
            stock_type = "A股"
            is_china_stock = True
            logger.info(f"[新闻分析] 匹配到A股后缀，股票类型: {stock_type}")
        elif ".HK" in ticker:
            stock_type = "港股"
            logger.info(f"[新闻分析] 匹配到港股后缀，股票类型: {stock_type}")
        elif any(suffix in ticker for suffix in [".US", ".N", ".O", ".NYSE", ".NASDAQ"]):
            stock_type = "美股"
            logger.info(f"[新闻分析] 匹配到美股后缀，股票类型: {stock_type}")
        else:
            logger.info("[新闻分析] 未匹配到已知后缀")
    else:
        logger.info("[新闻分析] ticker不包含点号，尝试使用StockUtils判断")
        # 尝试使用StockUtils判断股票类型
        try:
            StockUtils = getattr(importlib.import_module("trader.utils.stocks"), "StockUtils")
            logger.info("[新闻分析] 成功导入StockUtils，开始判断股票类型")
            market_info = StockUtils.get_market_info(ticker)
            logger.info(f"[新闻分析] StockUtils返回市场信息: {market_info}")
            if market_info["is_china"]:
                stock_type = "A股"
                is_china_stock = True
                logger.info("[新闻分析] StockUtils判断为A股")
            elif market_info["is_hk"]:
                stock_type = "港股"
                logger.info("[新闻分析] StockUtils判断为港股")
            elif market_info["is_us"]:
                stock_type = "美股"
                logger.info("[新闻分析] StockUtils判断为美股")
        except Exception as e:
            logger.warning(f"[新闻分析] 使用StockUtils判断股票类型失败: {e}")

    logger.info(f"[新闻分析] 最终判断结果 - 股票 {ticker} 类型: {stock_type}, 是否A股: {is_china_stock}")

    # A股东方财富新闻源保留为最终 fallback；先走聚合器/Google，避免
    # 单一中文站点反爬或超时阻塞整个新闻链路。
    logger.info(f"[新闻分析] ========== 步骤2: 跳过东方财富优先路径，股票类型: {stock_type} ==========")

    # 如果不是A股或A股新闻获取失败，使用实时新闻聚合器
    logger.info("[新闻分析] ========== 步骤3: 实时新闻聚合器 ==========")
    aggregator = RealtimeNewsAggregator()
    logger.info("[新闻分析] 成功创建实时新闻聚合器实例")
    try:
        logger.info(f"[新闻分析] 尝试使用实时新闻聚合器获取 {ticker} 的新闻")
        start_time = datetime.now(ZoneInfo(get_timezone_name()))
        logger.info(f"[新闻分析] 聚合器调用开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")

        # 获取实时新闻
        news_items = aggregator.get_realtime_stock_news(ticker, hours_back, max_news=10)

        end_time = datetime.now(ZoneInfo(get_timezone_name()))
        time_taken = (end_time - start_time).total_seconds()
        logger.info(f"[新闻分析] 聚合器调用结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
        logger.info(f"[新闻分析] 聚合器调用耗时: {time_taken:.2f}秒")
        logger.info(f"[新闻分析] 聚合器返回数据类型: {type(news_items)}")
        logger.info(f"[新闻分析] 聚合器返回数据: {news_items}")

        # 如果成功获取到新闻
        if news_items and len(news_items) > 0:
            news_count = len(news_items)
            logger.info(f"[新闻分析] 实时新闻聚合器成功获取 {news_count} 条 {ticker} 的新闻，耗时 {time_taken:.2f} 秒")

            # 记录一些新闻标题示例
            sample_titles = [item.title for item in news_items[:3]]
            logger.info(f"[新闻分析] 新闻标题示例: {', '.join(sample_titles)}")

            # 格式化报告
            logger.info("[新闻分析] 开始格式化新闻报告")
            report = aggregator.format_news_report(news_items, ticker)
            logger.info(f"[新闻分析] 报告格式化完成，长度: {len(report)} 字符")

            total_time_taken = (datetime.now(ZoneInfo(get_timezone_name())) - start_total_time).total_seconds()
            logger.info(
                f"[新闻分析] 成功生成 {ticker} 的新闻报告，总耗时 {total_time_taken:.2f} 秒，新闻来源: 实时新闻聚合器"
            )
            logger.info("[新闻分析] ========== 实时新闻聚合器获取成功，函数即将返回 ==========")
            return report
        else:
            logger.warning(
                f"[新闻分析] 实时新闻聚合器未获取到 {ticker} 的新闻，耗时 {time_taken:.2f} 秒，尝试使用备用新闻源"
            )
            # 如果没有获取到新闻，继续尝试备用方案
    except Exception as e:
        logger.error(f"[新闻分析] 实时新闻聚合器获取失败: {e}，将尝试备用新闻源")
        logger.error(f"[新闻分析] 异常详情: {type(e).__name__}: {str(e)}")
        traceback = importlib.import_module("traceback")
        logger.error(f"[新闻分析] 异常堆栈: {traceback.format_exc()}")
        # 发生异常时，继续尝试备用方案

    # 备用方案1: 对于港股，优先尝试使用东方财富新闻（A股已在前面处理）
    if not is_china_stock and ".HK" in ticker:
        logger.info(f"[新闻分析] 检测到港股代码 {ticker}，尝试使用东方财富新闻源")
        try:
            AKShareProvider = getattr(
                importlib.import_module("trader.flows.providers.china.akshare"),
                "AKShareProvider",
            )

            provider = AKShareProvider()

            # 处理港股代码
            clean_ticker = ticker.replace(".HK", "")

            logger.info(f"[新闻分析] 开始从东方财富获取港股 {clean_ticker} 的新闻数据")
            start_time = datetime.now(ZoneInfo(get_timezone_name()))
            news_df = provider.get_stock_news_sync(symbol=clean_ticker, limit=10)
            end_time = datetime.now(ZoneInfo(get_timezone_name()))
            time_taken = (end_time - start_time).total_seconds()

            if news_df is not None and not news_df.empty:
                # 构建简单的新闻报告
                news_count = len(news_df)
                logger.info(f"[新闻分析] 成功获取 {news_count} 条东方财富港股新闻，耗时 {time_taken:.2f} 秒")

                report = f"# {ticker} 东方财富新闻报告\n\n"
                report += f"📅 生成时间: {datetime.now(ZoneInfo(get_timezone_name())).strftime('%Y-%m-%d %H:%M:%S')}\n"
                report += f"📊 新闻总数: {news_count}条\n"
                report += f"🕒 获取耗时: {time_taken:.2f}秒\n\n"

                # 记录一些新闻标题示例
                sample_titles = [
                    str(row.get("新闻标题", "无标题") or "无标题") for _, row in news_df.head(3).iterrows()
                ]
                logger.info(f"[新闻分析] 新闻标题示例: {', '.join(sample_titles)}")

                for _, row in news_df.iterrows():
                    report += f"### {row.get('新闻标题', '')}\n"
                    report += f"📅 {row.get('发布时间', '')}\n"
                    report += f"🔗 {row.get('新闻链接', '')}\n\n"
                    report += f"{row.get('新闻内容', '无内容')}\n\n"

                logger.info("[新闻分析] 成功生成东方财富新闻报告，新闻来源: 东方财富")
                return report
            else:
                logger.warning(
                    f"[新闻分析] 东方财富未获取到 {clean_ticker} 的新闻数据，耗时 {time_taken:.2f} 秒，尝试下一个备用方案"
                )
        except Exception as e:
            logger.error(f"[新闻分析] 东方财富新闻获取失败: {e}，将尝试下一个备用方案")

    # 备用方案2: 尝试使用Google新闻
    try:
        get_google_news = getattr(importlib.import_module("trader.flows.interface"), "get_google_news")

        # 根据股票类型构建搜索查询
        if stock_type == "A股":
            # A股使用中文关键词
            clean_ticker = (
                ticker
                .replace(".SH", "")
                .replace(".SZ", "")
                .replace(".SS", "")
                .replace(".XSHE", "")
                .replace(".XSHG", "")
            )
            search_query = f"{clean_ticker} 股票 公司 财报 新闻"
            logger.info(f"[新闻分析] 开始从Google获取A股 {clean_ticker} 的中文新闻数据，查询: {search_query}")
        elif stock_type == "港股":
            # 港股使用中文关键词
            clean_ticker = ticker.replace(".HK", "")
            search_query = f"{clean_ticker} 港股 公司"
            logger.info(f"[新闻分析] 开始从Google获取港股 {clean_ticker} 的新闻数据，查询: {search_query}")
        else:
            # 美股使用英文关键词
            search_query = f"{ticker} stock news"
            logger.info(f"[新闻分析] 开始从Google获取 {ticker} 的新闻数据，查询: {search_query}")

        start_time = datetime.now(ZoneInfo(get_timezone_name()))
        google_news = get_google_news(search_query, curr_date, 1)
        end_time = datetime.now(ZoneInfo(get_timezone_name()))
        time_taken = (end_time - start_time).total_seconds()

        if google_news and len(google_news.strip()) > 0:
            # 估算获取的新闻数量
            news_lines = google_news.strip().split("\n")
            news_count = sum(1 for line in news_lines if line.startswith("###"))

            logger.info(f"[新闻分析] 成功获取 Google 新闻，估计 {news_count} 条新闻，耗时 {time_taken:.2f} 秒")

            # 记录一些新闻标题示例
            sample_titles = [line.replace("### ", "") for line in news_lines if line.startswith("### ")][:3]
            if sample_titles:
                logger.info(f"[新闻分析] 新闻标题示例: {', '.join(sample_titles)}")

            logger.info("[新闻分析] 成功生成 Google 新闻报告，新闻来源: Google")
            return google_news
        else:
            logger.warning(f"[新闻分析] Google 新闻未获取到 {ticker} 的新闻数据，耗时 {time_taken:.2f} 秒")
    except Exception as e:
        logger.error(f"[新闻分析] Google 新闻获取失败: {e}，将尝试东方财富备用新闻源")

    # 备用方案3: A股最后尝试东方财富新闻，使用兼容函数以便测试和脚本 patch。
    if is_china_stock:
        try:
            get_stock_news_em = getattr(importlib.import_module("trader.flows.akshare"), "get_stock_news_em")

            clean_ticker = (
                ticker
                .replace(".SH", "")
                .replace(".SZ", "")
                .replace(".SS", "")
                .replace(".XSHE", "")
                .replace(".XSHG", "")
            )
            logger.info(f"[新闻分析] 尝试东方财富备用新闻源: {clean_ticker}")
            start_time = datetime.now(ZoneInfo(get_timezone_name()))
            news_df = get_stock_news_em(clean_ticker, limit=10)
            end_time = datetime.now(ZoneInfo(get_timezone_name()))
            time_taken = (end_time - start_time).total_seconds()

            if news_df is not None and hasattr(news_df, "empty") and not news_df.empty:
                news_count = len(news_df)
                report = f"# {ticker} 东方财富新闻报告\n\n"
                report += f"📅 生成时间: {datetime.now(ZoneInfo(get_timezone_name())).strftime('%Y-%m-%d %H:%M:%S')}\n"
                report += f"📊 新闻总数: {news_count}条\n"
                report += f"🕒 获取耗时: {time_taken:.2f}秒\n\n"

                for _, row in news_df.iterrows():
                    title = row.get("新闻标题", row.get("标题", row.get("title", "")))
                    publish_time = row.get("发布时间", row.get("时间", row.get("time", "")))
                    link = row.get("新闻链接", row.get("链接", row.get("url", "")))
                    content = row.get("新闻内容", row.get("内容", row.get("content", "无内容")))
                    report += f"### {title}\n"
                    report += f"📅 {publish_time}\n"
                    report += f"🔗 {link}\n\n"
                    report += f"{content}\n\n"

                logger.info(f"[新闻分析] 东方财富备用新闻源成功，新闻数: {news_count}")
                return report
            logger.warning("[新闻分析] 东方财富备用新闻源未获取到数据")
        except Exception as e:
            logger.error(f"[新闻分析] 东方财富备用新闻源失败: {e}")

    # 所有方法都失败，返回错误信息
    total_time_taken = (datetime.now(ZoneInfo(get_timezone_name())) - start_total_time).total_seconds()
    logger.error(f"[新闻分析] {ticker} 的所有新闻获取方法均已失败，总耗时 {total_time_taken:.2f} 秒")

    # 记录详细的失败信息
    failure_details = {
        "股票代码": ticker,
        "股票类型": stock_type,
        "分析日期": curr_date,
        "回溯时间": f"{hours_back}小时",
        "总耗时": f"{total_time_taken:.2f}秒",
    }
    logger.error(f"[新闻分析] 新闻获取失败详情: {failure_details}")

    return f"""
实时新闻获取失败 - {ticker}
分析日期: {curr_date}

❌ 错误信息: 所有可用的新闻源都未能获取到相关新闻

💡 备用建议:
1. 检查网络连接和API密钥配置
2. 使用基础新闻分析作为备选
3. 关注官方财经媒体的最新报道
4. 考虑使用专业金融终端获取实时新闻

注: 实时新闻获取依赖外部API服务的可用性。
"""
