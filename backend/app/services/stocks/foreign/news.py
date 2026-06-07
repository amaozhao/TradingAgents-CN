# ruff: noqa: F403,F405
from .common import *


class ForeignStockNewsMixin:
    async def get_hk_news(self, code: str, days: int = 2, limit: int = 50) -> Dict:
        """
        获取港股新闻

        Args:
            code: 股票代码
            days: 回溯天数
            limit: 返回数量限制

        Returns:
            包含新闻列表和数据源的字典
        """
        getattr(importlib.import_module("datetime"), "datetime")
        getattr(importlib.import_module("datetime"), "timedelta")

        logger.info(f"📰 开始获取港股新闻: {code}, days={days}, limit={limit}")

        # 1. 尝试从缓存获取
        cache_key_str = f"hk_news_{days}_{limit}"
        cache_key = self.cache.find_cached_stock_data(
            symbol=code, data_source=cache_key_str
        )

        if cache_key:
            cached_data = self.cache.load_stock_data(cache_key)
            if cached_data:
                logger.info(f"⚡ 从缓存获取港股新闻: {code}")
                return json.loads(cached_data)

        # 2. 从数据库获取数据源优先级
        source_priority = await self._get_source_priority("HK")

        # 3. 按优先级尝试各个数据源
        news_data = None
        data_source = ""

        # 数据源名称映射
        source_handlers = {
            "akshare": ("akshare", self._get_hk_news_from_akshare),
            "finnhub": ("finnhub", self._get_hk_news_from_finnhub),
        }

        # 过滤有效数据源并去重
        valid_priority = []
        seen = set()
        for source_name in source_priority:
            source_key = source_name.lower()
            if source_key in source_handlers and source_key not in seen:
                seen.add(source_key)
                valid_priority.append(source_name)

        if not valid_priority:
            logger.warning("⚠️ 数据库中没有配置有效的港股新闻数据源，使用默认顺序")
            valid_priority = ["akshare", "finnhub"]

        logger.info(f"📊 [HK新闻有效数据源] {valid_priority}")

        for source_name in valid_priority:
            source_key = source_name.lower()
            handler_name, handler_func = source_handlers[source_key]
            try:
                # 🔥 使用 asyncio.to_thread 避免阻塞事件循环
                asyncio = importlib.import_module("asyncio")
                news_data = await asyncio.to_thread(handler_func, code, days, limit)
                data_source = handler_name

                if news_data:
                    logger.info(
                        f"✅ {data_source}获取港股新闻成功: {code}, 返回 {len(news_data)} 条"
                    )
                    break
            except Exception as e:
                logger.warning(f"⚠️ {source_name}获取新闻失败: {e}")
                continue

        if not news_data:
            logger.warning(f"⚠️ 无法获取港股{code}的新闻数据：所有数据源均失败")
            news_data = []
            data_source = "none"

        # 4. 构建返回数据
        result = {
            "code": code,
            "days": days,
            "limit": limit,
            "source": data_source,
            "items": news_data,
        }

        # 5. 缓存数据
        self.cache.save_stock_data(
            symbol=code,
            data=json.dumps(result, ensure_ascii=False),
            data_source=cache_key_str,
        )

        return result

    async def get_us_news(self, code: str, days: int = 2, limit: int = 50) -> Dict:
        """
        获取美股新闻

        Args:
            code: 股票代码
            days: 回溯天数
            limit: 返回数量限制

        Returns:
            包含新闻列表和数据源的字典
        """
        getattr(importlib.import_module("datetime"), "datetime")
        getattr(importlib.import_module("datetime"), "timedelta")

        logger.info(f"📰 开始获取美股新闻: {code}, days={days}, limit={limit}")

        # 1. 尝试从缓存获取
        cache_key_str = f"us_news_{days}_{limit}"
        cache_key = self.cache.find_cached_stock_data(
            symbol=code, data_source=cache_key_str
        )

        if cache_key:
            cached_data = self.cache.load_stock_data(cache_key)
            if cached_data:
                logger.info(f"⚡ 从缓存获取美股新闻: {code}")
                return json.loads(cached_data)

        # 2. 从数据库获取数据源优先级
        source_priority = await self._get_source_priority("US")

        # 3. 按优先级尝试各个数据源
        news_data = None
        data_source = ""

        # 数据源名称映射
        source_handlers = {
            "alpha_vantage": ("alpha_vantage", self._get_us_news_from_alpha_vantage),
            "finnhub": ("finnhub", self._get_us_news_from_finnhub),
        }

        # 过滤有效数据源并去重
        valid_priority = []
        seen = set()
        for source_name in source_priority:
            source_key = source_name.lower()
            if source_key in source_handlers and source_key not in seen:
                seen.add(source_key)
                valid_priority.append(source_name)

        if not valid_priority:
            logger.warning("⚠️ 数据库中没有配置有效的美股新闻数据源，使用默认顺序")
            valid_priority = ["alpha_vantage", "finnhub"]

        logger.info(f"📊 [US新闻有效数据源] {valid_priority}")

        for source_name in valid_priority:
            source_key = source_name.lower()
            handler_name, handler_func = source_handlers[source_key]
            try:
                # 🔥 使用 asyncio.to_thread 避免阻塞事件循环
                asyncio = importlib.import_module("asyncio")
                news_data = await asyncio.to_thread(handler_func, code, days, limit)
                data_source = handler_name

                if news_data:
                    logger.info(
                        f"✅ {data_source}获取美股新闻成功: {code}, 返回 {len(news_data)} 条"
                    )
                    break
            except Exception as e:
                logger.warning(f"⚠️ {source_name}获取新闻失败: {e}")
                continue

        if not news_data:
            logger.warning(f"⚠️ 无法获取美股{code}的新闻数据：所有数据源均失败")
            news_data = []
            data_source = "none"

        # 4. 构建返回数据
        result = {
            "code": code,
            "days": days,
            "limit": limit,
            "source": data_source,
            "items": news_data,
        }

        # 5. 缓存数据
        self.cache.save_stock_data(
            symbol=code,
            data=json.dumps(result, ensure_ascii=False),
            data_source=cache_key_str,
        )

        return result

    def _get_us_news_from_alpha_vantage(
        self, code: str, days: int, limit: int
    ) -> List[Dict]:
        """从Alpha Vantage获取美股新闻"""
        get_api_key = getattr(
            importlib.import_module("trader.flows.providers.us.alpha.common"),
            "get_api_key",
        )
        _make_api_request = getattr(
            importlib.import_module("trader.flows.providers.us.alpha.common"),
            "_make_api_request",
        )
        datetime = getattr(importlib.import_module("datetime"), "datetime")
        timedelta = getattr(importlib.import_module("datetime"), "timedelta")

        # 获取 API Key
        api_key = get_api_key()
        if not api_key:
            raise Exception("Alpha Vantage API Key 未配置")

        # 计算时间范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # 调用 NEWS_SENTIMENT API
        params = {
            "tickers": code.upper(),
            "time_from": start_date.strftime("%Y%m%dT%H%M"),
            "time_to": end_date.strftime("%Y%m%dT%H%M"),
            "sort": "LATEST",
            "limit": str(limit),
        }

        data = cast(Dict[str, Any], _make_api_request("NEWS_SENTIMENT", params))

        if not data or "feed" not in data:
            raise Exception("无数据")

        # 格式化新闻数据
        news_list = []
        for article in cast(List[Dict[str, Any]], data.get("feed", []))[:limit]:
            # 解析时间
            time_published = article.get("time_published", "")
            try:
                # Alpha Vantage 时间格式: 20240101T120000
                pub_time = datetime.strptime(time_published, "%Y%m%dT%H%M%S")
                pub_time_str = pub_time.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pub_time_str = time_published

            # 提取相关股票的情感分数
            sentiment_score = None
            sentiment_label = article.get("overall_sentiment_label", "Neutral")

            ticker_sentiment = article.get("ticker_sentiment", [])
            for ts in ticker_sentiment:
                if ts.get("ticker", "").upper() == code.upper():
                    sentiment_score = ts.get("ticker_sentiment_score")
                    sentiment_label = ts.get("ticker_sentiment_label", sentiment_label)
                    break

            news_list.append(
                {
                    "title": article.get("title", ""),
                    "summary": article.get("summary", ""),
                    "url": article.get("url", ""),
                    "source": article.get("source", ""),
                    "publish_time": pub_time_str,
                    "sentiment": sentiment_label,
                    "sentiment_score": sentiment_score,
                }
            )

        return news_list

    def _get_us_news_from_finnhub(self, code: str, days: int, limit: int) -> List[Dict]:
        """从Finnhub获取美股新闻"""
        finnhub = importlib.import_module("finnhub")
        datetime = getattr(importlib.import_module("datetime"), "datetime")
        timedelta = getattr(importlib.import_module("datetime"), "timedelta")

        # 获取 API Key
        api_key = settings.FINNHUB_API_KEY
        if not api_key:
            raise Exception("Finnhub API Key 未配置")

        # 创建客户端
        client = finnhub.Client(api_key=api_key)

        # 计算时间范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # 获取公司新闻
        news = client.company_news(
            code.upper(),
            _from=start_date.strftime("%Y-%m-%d"),
            to=end_date.strftime("%Y-%m-%d"),
        )

        if not news:
            raise Exception("无数据")

        # 格式化新闻数据
        news_list = []
        for article in news[:limit]:
            # 解析时间戳
            timestamp = article.get("datetime", 0)
            pub_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

            news_list.append(
                {
                    "title": article.get("headline", ""),
                    "summary": article.get("summary", ""),
                    "url": article.get("url", ""),
                    "source": article.get("source", ""),
                    "publish_time": pub_time,
                    "sentiment": None,  # Finnhub 不提供情感分析
                    "sentiment_score": None,
                }
            )

        return news_list

    def _get_hk_news_from_finnhub(self, code: str, days: int, limit: int) -> List[Dict]:
        """从Finnhub获取港股新闻"""
        finnhub = importlib.import_module("finnhub")
        datetime = getattr(importlib.import_module("datetime"), "datetime")
        timedelta = getattr(importlib.import_module("datetime"), "timedelta")

        # 获取 API Key
        api_key = settings.FINNHUB_API_KEY
        if not api_key:
            raise Exception("Finnhub API Key 未配置")

        # 创建客户端
        client = finnhub.Client(api_key=api_key)

        # 计算时间范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # 港股代码需要添加 .HK 后缀
        hk_symbol = f"{code}.HK" if not code.endswith(".HK") else code

        # 获取公司新闻
        news = client.company_news(
            hk_symbol,
            _from=start_date.strftime("%Y-%m-%d"),
            to=end_date.strftime("%Y-%m-%d"),
        )

        if not news:
            raise Exception("无数据")

        # 格式化新闻数据
        news_list = []
        for article in news[:limit]:
            # 解析时间戳
            timestamp = article.get("datetime", 0)
            pub_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

            news_list.append(
                {
                    "title": article.get("headline", ""),
                    "summary": article.get("summary", ""),
                    "url": article.get("url", ""),
                    "source": article.get("source", ""),
                    "publish_time": pub_time,
                    "sentiment": None,  # Finnhub 不提供情感分析
                    "sentiment_score": None,
                }
            )

        return news_list

    def _get_hk_news_from_akshare(self, code: str, days: int, limit: int) -> List[Dict]:
        """从AKShare获取港股新闻"""
        try:
            ak = importlib.import_module("akshare")
            datetime = getattr(importlib.import_module("datetime"), "datetime")
            getattr(importlib.import_module("datetime"), "timedelta")

            # AKShare 的港股新闻接口
            # 注意：AKShare 可能没有专门的港股新闻接口，这里使用通用新闻接口
            # 如果没有合适的接口，抛出异常让系统尝试下一个数据源

            # 尝试获取港股新闻（使用东方财富港股新闻）
            try:
                df = ak.stock_news_em(symbol=code)
                if df is None or df.empty:
                    raise Exception("无数据")

                # 格式化新闻数据
                news_list = []
                for _, row in df.head(limit).iterrows():
                    pub_time = (
                        row["发布时间"]
                        if "发布时间" in row
                        else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                    news_list.append(
                        {
                            "title": row["新闻标题"] if "新闻标题" in row else "",
                            "summary": row["新闻内容"] if "新闻内容" in row else "",
                            "url": row["新闻链接"] if "新闻链接" in row else "",
                            "source": "AKShare-东方财富",
                            "publish_time": pub_time,
                            "sentiment": None,
                            "sentiment_score": None,
                        }
                    )

                return news_list
            except Exception as e:
                logger.debug(f"AKShare 东方财富接口失败: {e}")
                raise Exception("AKShare 暂不支持港股新闻")

        except Exception as e:
            logger.warning(f"⚠️ AKShare获取港股新闻失败: {e}")
            raise
