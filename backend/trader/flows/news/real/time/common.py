# ruff: noqa: F401,F403,F405,F821
class _RealtimeNewsAggregatorMixin1:
    def __init__(self):
        self.headers = {"User-Agent": "TradingAgents-CN/1.0"}

        # API密钥配置
        self.finnhub_key = os.getenv("FINNHUB_API_KEY")
        self.alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        self.newsapi_key = os.getenv("NEWSAPI_KEY")

    def get_realtime_stock_news(
        self, ticker: str, hours_back: int = 6, max_news: int = 10
    ) -> List[NewsItem]:
        """
        获取实时股票新闻
        优先级：专业API > 新闻API > 搜索引擎

        Args:
            ticker: 股票代码
            hours_back: 回溯小时数
            max_news: 最大新闻数量，默认10条
        """
        logger.info(
            f"[新闻聚合器] 开始获取 {ticker} 的实时新闻，回溯时间: {hours_back}小时"
        )
        start_time = datetime.now(ZoneInfo(get_timezone_name()))
        all_news = []

        # 1. FinnHub实时新闻 (最高优先级)
        logger.info(f"[新闻聚合器] 尝试从 FinnHub 获取 {ticker} 的新闻")
        finnhub_start = datetime.now(ZoneInfo(get_timezone_name()))
        finnhub_news = self._get_finnhub_realtime_news(ticker, hours_back)
        finnhub_time = (
            datetime.now(ZoneInfo(get_timezone_name())) - finnhub_start
        ).total_seconds()

        if finnhub_news:
            logger.info(
                f"[新闻聚合器] 成功从 FinnHub 获取 {len(finnhub_news)} 条新闻，耗时: {finnhub_time:.2f}秒"
            )
        else:
            logger.info(f"[新闻聚合器] FinnHub 未返回新闻，耗时: {finnhub_time:.2f}秒")

        all_news.extend(finnhub_news)

        # 2. Alpha Vantage新闻
        logger.info(f"[新闻聚合器] 尝试从 Alpha Vantage 获取 {ticker} 的新闻")
        av_start = datetime.now(ZoneInfo(get_timezone_name()))
        av_news = self._get_alpha_vantage_news(ticker, hours_back)
        av_time = (
            datetime.now(ZoneInfo(get_timezone_name())) - av_start
        ).total_seconds()

        if av_news:
            logger.info(
                f"[新闻聚合器] 成功从 Alpha Vantage 获取 {len(av_news)} 条新闻，耗时: {av_time:.2f}秒"
            )
        else:
            logger.info(f"[新闻聚合器] Alpha Vantage 未返回新闻，耗时: {av_time:.2f}秒")

        all_news.extend(av_news)

        # 3. NewsAPI (如果配置了)
        if self.newsapi_key:
            logger.info(f"[新闻聚合器] 尝试从 NewsAPI 获取 {ticker} 的新闻")
            newsapi_start = datetime.now(ZoneInfo(get_timezone_name()))
            newsapi_news = self._get_newsapi_news(ticker, hours_back)
            newsapi_time = (
                datetime.now(ZoneInfo(get_timezone_name())) - newsapi_start
            ).total_seconds()

            if newsapi_news:
                logger.info(
                    f"[新闻聚合器] 成功从 NewsAPI 获取 {len(newsapi_news)} 条新闻，耗时: {newsapi_time:.2f}秒"
                )
            else:
                logger.info(
                    f"[新闻聚合器] NewsAPI 未返回新闻，耗时: {newsapi_time:.2f}秒"
                )

            all_news.extend(newsapi_news)
        else:
            logger.info("[新闻聚合器] NewsAPI 密钥未配置，跳过此新闻源")

        # 4. 中文财经新闻源
        logger.info(f"[新闻聚合器] 尝试获取 {ticker} 的中文财经新闻")
        chinese_start = datetime.now(ZoneInfo(get_timezone_name()))
        chinese_news = self._get_chinese_finance_news(ticker, hours_back)
        chinese_time = (
            datetime.now(ZoneInfo(get_timezone_name())) - chinese_start
        ).total_seconds()

        if chinese_news:
            logger.info(
                f"[新闻聚合器] 成功获取 {len(chinese_news)} 条中文财经新闻，耗时: {chinese_time:.2f}秒"
            )
        else:
            logger.info(
                f"[新闻聚合器] 未获取到中文财经新闻，耗时: {chinese_time:.2f}秒"
            )

        all_news.extend(chinese_news)

        # 去重和排序
        logger.info(f"[新闻聚合器] 开始对 {len(all_news)} 条新闻进行去重和排序")
        dedup_start = datetime.now(ZoneInfo(get_timezone_name()))
        unique_news = self._deduplicate_news(all_news)
        sorted_news = sorted(unique_news, key=lambda x: x.publish_time, reverse=True)
        dedup_time = (
            datetime.now(ZoneInfo(get_timezone_name())) - dedup_start
        ).total_seconds()

        # 记录去重结果
        removed_count = len(all_news) - len(unique_news)
        logger.info(
            f"[新闻聚合器] 新闻去重完成，移除了 {removed_count} 条重复新闻，剩余 {len(sorted_news)} 条，耗时: {dedup_time:.2f}秒"
        )

        # 记录总体情况
        total_time = (
            datetime.now(ZoneInfo(get_timezone_name())) - start_time
        ).total_seconds()
        logger.info(
            f"[新闻聚合器] {ticker} 的新闻聚合完成，总共获取 {len(sorted_news)} 条新闻，总耗时: {total_time:.2f}秒"
        )

        # 限制新闻数量为最新的max_news条
        if len(sorted_news) > max_news:
            original_count = len(sorted_news)
            sorted_news = sorted_news[:max_news]
            logger.info(
                f"[新闻聚合器] 📰 新闻数量限制: 从{original_count}条限制为{max_news}条最新新闻"
            )

        # 记录一些新闻标题示例
        if sorted_news:
            sample_titles = [item.title for item in sorted_news[:3]]
            logger.info(f"[新闻聚合器] 新闻标题示例: {', '.join(sample_titles)}")

        return sorted_news

    def _get_finnhub_realtime_news(
        self, ticker: str, hours_back: int
    ) -> List[NewsItem]:
        """获取FinnHub实时新闻"""
        if not self.finnhub_key:
            return []

        try:
            # 计算时间范围
            end_time = datetime.now(ZoneInfo(get_timezone_name()))
            start_time = end_time - timedelta(hours=hours_back)

            # FinnHub API调用
            url = "https://finnhub.io/api/v1/company-news"
            params = {
                "symbol": ticker,
                "from": start_time.strftime("%Y-%m-%d"),
                "to": end_time.strftime("%Y-%m-%d"),
                "token": self.finnhub_key,
            }

            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()

            news_data = response.json()
            news_items = []

            for item in news_data:
                # 检查新闻时效性
                publish_time = datetime.fromtimestamp(
                    item.get("datetime", 0), tz=ZoneInfo(get_timezone_name())
                )
                if publish_time < start_time:
                    continue

                # 评估紧急程度
                urgency = self._assess_news_urgency(
                    item.get("headline", ""), item.get("summary", "")
                )

                news_items.append(
                    NewsItem(
                        title=item.get("headline", ""),
                        content=item.get("summary", ""),
                        source=item.get("source", "FinnHub"),
                        publish_time=publish_time,
                        url=item.get("url", ""),
                        urgency=urgency,
                        relevance_score=self._calculate_relevance(
                            item.get("headline", ""), ticker
                        ),
                    )
                )

            return news_items

        except Exception as e:
            logger.error(f"FinnHub新闻获取失败: {e}")
            return []

    def _get_alpha_vantage_news(self, ticker: str, hours_back: int) -> List[NewsItem]:
        """获取Alpha Vantage新闻"""
        if not self.alpha_vantage_key:
            return []

        try:
            url = "https://www.alphavantage.co/query"
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": ticker,
                "apikey": self.alpha_vantage_key,
                "limit": 50,
            }

            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()

            data = response.json()
            news_items = []

            if "feed" in data:
                for item in data["feed"]:
                    # 解析时间
                    time_str = item.get("time_published", "")
                    try:
                        publish_time = datetime.strptime(
                            time_str, "%Y%m%dT%H%M%S"
                        ).replace(tzinfo=ZoneInfo(get_timezone_name()))
                    except Exception:
                        continue

                    # 检查时效性
                    if publish_time < datetime.now(
                        ZoneInfo(get_timezone_name())
                    ) - timedelta(hours=hours_back):
                        continue

                    urgency = self._assess_news_urgency(
                        item.get("title", ""), item.get("summary", "")
                    )

                    news_items.append(
                        NewsItem(
                            title=item.get("title", ""),
                            content=item.get("summary", ""),
                            source=item.get("source", "Alpha Vantage"),
                            publish_time=publish_time,
                            url=item.get("url", ""),
                            urgency=urgency,
                            relevance_score=self._calculate_relevance(
                                item.get("title", ""), ticker
                            ),
                        )
                    )

            return news_items

        except Exception as e:
            logger.error(f"Alpha Vantage新闻获取失败: {e}")
            return []

    def _get_newsapi_news(self, ticker: str, hours_back: int) -> List[NewsItem]:
        """获取NewsAPI新闻"""
        try:
            # 构建搜索查询
            company_names = {
                "AAPL": "Apple",
                "TSLA": "Tesla",
                "NVDA": "NVIDIA",
                "MSFT": "Microsoft",
                "GOOGL": "Google",
            }

            query = f"{ticker} OR {company_names.get(ticker, ticker)}"

            url = "https://newsapi.org/v2/everything"
            params = {
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "from": (
                    datetime.now(ZoneInfo(get_timezone_name()))
                    - timedelta(hours=hours_back)
                ).isoformat(),
                "apiKey": self.newsapi_key,
            }

            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()

            data = response.json()
            news_items = []

            for item in data.get("articles", []):
                # 解析时间
                time_str = item.get("publishedAt", "")
                try:
                    publish_time = datetime.fromisoformat(
                        time_str.replace("Z", "+00:00")
                    )
                except Exception:
                    continue

                urgency = self._assess_news_urgency(
                    item.get("title", ""), item.get("description", "")
                )

                news_items.append(
                    NewsItem(
                        title=item.get("title", ""),
                        content=item.get("description", ""),
                        source=item.get("source", {}).get("name", "NewsAPI"),
                        publish_time=publish_time,
                        url=item.get("url", ""),
                        urgency=urgency,
                        relevance_score=self._calculate_relevance(
                            item.get("title", ""), ticker
                        ),
                    )
                )

            return news_items

        except Exception as e:
            logger.error(f"NewsAPI新闻获取失败: {e}")
            return []

    def _get_chinese_finance_news(self, ticker: str, hours_back: int) -> List[NewsItem]:
        """获取中文财经新闻"""
        # 集成中文财经新闻API：财联社、东方财富等
        logger.info(
            f"[中文财经新闻] 开始获取 {ticker} 的中文财经新闻，回溯时间: {hours_back}小时"
        )
        start_time = datetime.now(ZoneInfo(get_timezone_name()))

        try:
            news_items = []

            # 1. 尝试使用AKShare获取东方财富个股新闻
            try:
                logger.info("[中文财经新闻] 尝试通过 AKShare Provider 获取新闻")
                AKShareProvider = getattr(
                    importlib.import_module("trader.flows.providers.china.akshare"),
                    "AKShareProvider",
                )

                provider = AKShareProvider()

                # 处理股票代码格式
                # 如果是美股代码，不使用东方财富新闻
                if "." in ticker and any(
                    suffix in ticker
                    for suffix in [".US", ".N", ".O", ".NYSE", ".NASDAQ"]
                ):
                    logger.info(
                        f"[中文财经新闻] 检测到美股代码 {ticker}，跳过东方财富新闻获取"
                    )
                else:
                    # 处理A股和港股代码
                    clean_ticker = (
                        ticker.replace(".SH", "")
                        .replace(".SZ", "")
                        .replace(".SS", "")
                        .replace(".HK", "")
                        .replace(".XSHE", "")
                        .replace(".XSHG", "")
                    )

                    # 获取东方财富新闻
                    logger.info(
                        f"[中文财经新闻] 开始获取 {clean_ticker} 的东方财富新闻"
                    )
                    em_start_time = datetime.now(ZoneInfo(get_timezone_name()))
                    news_df = provider.get_stock_news_sync(symbol=clean_ticker)

                    if news_df is not None and not news_df.empty:
                        logger.info(
                            f"[中文财经新闻] 东方财富返回 {len(news_df)} 条新闻数据，开始处理"
                        )
                        processed_count = 0
                        skipped_count = 0
                        error_count = 0

                        # 转换为NewsItem格式
                        for _, row in news_df.iterrows():
                            try:
                                # 解析时间
                                time_str = str(row.get("时间", "") or "")
                                if time_str:
                                    # 尝试解析时间格式，可能是'2023-01-01 12:34:56'格式
                                    try:
                                        publish_time = datetime.strptime(
                                            time_str, "%Y-%m-%d %H:%M:%S"
                                        ).replace(tzinfo=ZoneInfo(get_timezone_name()))
                                    except Exception:
                                        # 尝试其他可能的格式
                                        try:
                                            publish_time = datetime.strptime(
                                                time_str, "%Y-%m-%d"
                                            ).replace(
                                                tzinfo=ZoneInfo(get_timezone_name())
                                            )
                                        except Exception:
                                            logger.warning(
                                                f"[中文财经新闻] 无法解析时间格式: {time_str}，使用当前时间"
                                            )
                                            publish_time = datetime.now(
                                                ZoneInfo(get_timezone_name())
                                            )
                                else:
                                    logger.warning(
                                        "[中文财经新闻] 新闻时间为空，使用当前时间"
                                    )
                                    publish_time = datetime.now(
                                        ZoneInfo(get_timezone_name())
                                    )

                                # 检查时效性
                                if publish_time < datetime.now(
                                    ZoneInfo(get_timezone_name())
                                ) - timedelta(hours=hours_back):
                                    skipped_count += 1
                                    continue

                                # 评估紧急程度
                                title = str(row.get("标题", "") or "")
                                content = str(row.get("内容", "") or "")
                                urgency = self._assess_news_urgency(title, content)

                                news_items.append(
                                    NewsItem(
                                        title=title,
                                        content=content,
                                        source="东方财富",
                                        publish_time=publish_time,
                                        url=str(row.get("链接", "") or ""),
                                        urgency=urgency,
                                        relevance_score=self._calculate_relevance(
                                            title, ticker
                                        ),
                                    )
                                )
                                processed_count += 1
                            except Exception as item_e:
                                logger.error(
                                    f"[中文财经新闻] 处理东方财富新闻项目失败: {item_e}"
                                )
                                error_count += 1
                                continue

                        em_time = (
                            datetime.now(ZoneInfo(get_timezone_name())) - em_start_time
                        ).total_seconds()
                        logger.info(
                            f"[中文财经新闻] 东方财富新闻处理完成，成功: {processed_count}条，跳过: {skipped_count}条，错误: {error_count}条，耗时: {em_time:.2f}秒"
                        )
            except Exception as ak_e:
                logger.error(f"[中文财经新闻] 获取东方财富新闻失败: {ak_e}")

            # 2. 财联社RSS (如果可用)
            logger.info("[中文财经新闻] 开始获取财联社RSS新闻")
            rss_start_time = datetime.now(ZoneInfo(get_timezone_name()))
            rss_sources = [
                "https://www.cls.cn/api/sw?app=CailianpressWeb&os=web&sv=7.7.5",
                # 可以添加更多RSS源
            ]

            rss_success_count = 0
            rss_error_count = 0
            total_rss_items = 0

            for rss_url in rss_sources:
                try:
                    logger.info(f"[中文财经新闻] 尝试解析RSS源: {rss_url}")
                    rss_item_start = datetime.now(ZoneInfo(get_timezone_name()))
                    items = self._parse_rss_feed(rss_url, ticker, hours_back)
                    rss_item_time = (
                        datetime.now(ZoneInfo(get_timezone_name())) - rss_item_start
                    ).total_seconds()

                    if items:
                        logger.info(
                            f"[中文财经新闻] 成功从RSS源获取 {len(items)} 条新闻，耗时: {rss_item_time:.2f}秒"
                        )
                        news_items.extend(items)
                        total_rss_items += len(items)
                        rss_success_count += 1
                    else:
                        logger.info(
                            f"[中文财经新闻] RSS源未返回相关新闻，耗时: {rss_item_time:.2f}秒"
                        )
                except Exception as rss_e:
                    logger.error(f"[中文财经新闻] 解析RSS源失败: {rss_e}")
                    rss_error_count += 1
                    continue

            # 记录RSS获取总结
            rss_total_time = (
                datetime.now(ZoneInfo(get_timezone_name())) - rss_start_time
            ).total_seconds()
            logger.info(
                f"[中文财经新闻] RSS新闻获取完成，成功源: {rss_success_count}个，失败源: {rss_error_count}个，获取新闻: {total_rss_items}条，总耗时: {rss_total_time:.2f}秒"
            )

            # 记录中文财经新闻获取总结
            total_time = (
                datetime.now(ZoneInfo(get_timezone_name())) - start_time
            ).total_seconds()
            logger.info(
                f"[中文财经新闻] {ticker} 的中文财经新闻获取完成，总共获取 {len(news_items)} 条新闻，总耗时: {total_time:.2f}秒"
            )

            return news_items

        except Exception as e:
            logger.error(f"[中文财经新闻] 中文财经新闻获取失败: {e}")
            return []

    def _parse_rss_feed(
        self, rss_url: str, ticker: str, hours_back: int
    ) -> List[NewsItem]:
        """解析RSS源"""
        logger.info(
            f"[RSS解析] 开始解析RSS源: {rss_url}，股票: {ticker}，回溯时间: {hours_back}小时"
        )
        start_time = datetime.now(ZoneInfo(get_timezone_name()))

        try:
            # 实际实现需要使用feedparser库
            # 这里是简化实现，实际项目中应该替换为真实的RSS解析逻辑
            feedparser = importlib.import_module("feedparser")

            logger.info("[RSS解析] 尝试获取RSS源内容")
            feed = feedparser.parse(rss_url)

            if not feed or not feed.entries:
                logger.warning("[RSS解析] RSS源未返回有效内容")
                return []

            logger.info(f"[RSS解析] 成功获取RSS源，包含 {len(feed.entries)} 条条目")
            news_items = []
            processed_count = 0
            skipped_count = 0

            for entry in feed.entries:
                try:
                    entry_any = cast(Any, entry)
                    # 解析时间
                    if (
                        hasattr(entry_any, "published_parsed")
                        and entry_any.published_parsed
                    ):
                        publish_time = datetime.fromtimestamp(
                            time.mktime(entry_any.published_parsed),
                            tz=ZoneInfo(get_timezone_name()),
                        )
                    else:
                        logger.warning("[RSS解析] 条目缺少发布时间，使用当前时间")
                        publish_time = datetime.now(ZoneInfo(get_timezone_name()))

                    # 检查时效性
                    if publish_time < datetime.now(
                        ZoneInfo(get_timezone_name())
                    ) - timedelta(hours=hours_back):
                        skipped_count += 1
                        continue

                    title = str(entry_any.title if hasattr(entry_any, "title") else "")
                    content = str(
                        entry_any.description
                        if hasattr(entry_any, "description")
                        else ""
                    )

                    # 检查相关性
                    if (
                        ticker.lower() not in title.lower()
                        and ticker.lower() not in content.lower()
                    ):
                        skipped_count += 1
                        continue

                    # 评估紧急程度
                    urgency = self._assess_news_urgency(title, content)

                    news_items.append(
                        NewsItem(
                            title=title,
                            content=content,
                            source="财联社",
                            publish_time=publish_time,
                            url=str(
                                entry_any.link if hasattr(entry_any, "link") else ""
                            ),
                            urgency=urgency,
                            relevance_score=self._calculate_relevance(title, ticker),
                        )
                    )
                    processed_count += 1
                except Exception as e:
                    logger.error(f"[RSS解析] 处理RSS条目失败: {e}")
                    continue

            total_time = (
                datetime.now(ZoneInfo(get_timezone_name())) - start_time
            ).total_seconds()
            logger.info(
                f"[RSS解析] RSS源解析完成，成功: {processed_count}条，跳过: {skipped_count}条，耗时: {total_time:.2f}秒"
            )
            return news_items
        except ImportError:
            logger.error("[RSS解析] feedparser库未安装，无法解析RSS源")
            return []
        except Exception as e:
            logger.error(f"[RSS解析] 解析RSS源失败: {e}")
            return []

    def _assess_news_urgency(self, title: str, content: str) -> str:
        """评估新闻紧急程度"""
        text = (title + " " + content).lower()

        # 高紧急度关键词
        high_urgency_keywords = [
            "breaking",
            "urgent",
            "alert",
            "emergency",
            "halt",
            "suspend",
            "突发",
            "紧急",
            "暂停",
            "停牌",
            "重大",
        ]

        # 中等紧急度关键词
        medium_urgency_keywords = [
            "earnings",
            "report",
            "announce",
            "launch",
            "merger",
            "acquisition",
            "财报",
            "发布",
            "宣布",
            "并购",
            "收购",
        ]

        # 检查高紧急度关键词
        for keyword in high_urgency_keywords:
            if keyword in text:
                logger.debug(
                    f"[紧急度评估] 检测到高紧急度关键词 '{keyword}' 在新闻中: {title[:50]}..."
                )
                return "high"

        # 检查中等紧急度关键词
        for keyword in medium_urgency_keywords:
            if keyword in text:
                logger.debug(
                    f"[紧急度评估] 检测到中等紧急度关键词 '{keyword}' 在新闻中: {title[:50]}..."
                )
                return "medium"

        logger.debug(
            f"[紧急度评估] 未检测到紧急关键词，评估为低紧急度: {title[:50]}..."
        )
        return "low"

    def _calculate_relevance(self, title: str, ticker: str) -> float:
        """计算新闻相关性分数"""
        text = title.lower()
        ticker_lower = ticker.lower()

        # 基础相关性 - 股票代码直接出现在标题中
        if ticker_lower in text:
            logger.debug(
                f"[相关性计算] 股票代码 {ticker} 直接出现在标题中，相关性评分: 1.0，标题: {title[:50]}..."
            )
            return 1.0

        # 公司名称匹配
        company_names = {
            "aapl": ["apple", "iphone", "ipad", "mac"],
            "tsla": ["tesla", "elon musk", "electric vehicle"],
            "nvda": ["nvidia", "gpu", "ai chip"],
            "msft": ["microsoft", "windows", "azure"],
            "googl": ["google", "alphabet", "search"],
        }

        # 检查公司相关关键词
        if ticker_lower in company_names:
            for name in company_names[ticker_lower]:
                if name in text:
                    logger.debug(
                        f"[相关性计算] 检测到公司相关关键词 '{name}' 在标题中，相关性评分: 0.8，标题: {title[:50]}..."
                    )
                    return 0.8

        # 提取股票代码的纯数字部分（适用于中国股票）
        pure_code = "".join(filter(str.isdigit, ticker))
        if pure_code and pure_code in text:
            logger.debug(
                f"[相关性计算] 股票代码数字部分 {pure_code} 出现在标题中，相关性评分: 0.9，标题: {title[:50]}..."
            )
            return 0.9

        logger.debug(
            f"[相关性计算] 未检测到明确相关性，使用默认评分: 0.3，标题: {title[:50]}..."
        )
        return 0.3  # 默认相关性
