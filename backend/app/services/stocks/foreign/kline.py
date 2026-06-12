from .common import (
    Any,
    Dict,
    List,
    cast,
    importlib,
    json,
    logger,
    settings,
)


class ForeignStockKlineMixin:
    async def _get_hk_kline(
        self, code: str, period: str, limit: int, force_refresh: bool = False
    ) -> List[Dict]:
        """
        获取港股K线数据
        🔥 按照数据库配置的数据源优先级调用API
        """
        # 1. 检查缓存（除非强制刷新）
        cache_key_str = f"hk_kline_{period}_{limit}"
        if not force_refresh:
            cache_key = self.cache.find_cached_stock_data(
                symbol=code, data_source=cache_key_str
            )

            if cache_key:
                cached_data = self.cache.load_stock_data(cache_key)
                if cached_data:
                    logger.info(f"⚡ 从缓存获取港股K线: {code}")
                    return self._parse_cached_kline(cached_data)

        # 2. 从数据库获取数据源优先级
        source_priority = await self._get_source_priority("HK")

        # 3. 按优先级尝试各个数据源
        kline_data = None
        data_source = ""

        # 数据源名称映射
        source_handlers = {
            "akshare": ("akshare", self._get_hk_kline_from_akshare),
            "yahoo_finance": ("yfinance", self._get_hk_kline_from_yfinance),
            "finnhub": ("finnhub", self._get_hk_kline_from_finnhub),
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
            logger.warning("⚠️ 数据库中没有配置有效的港股K线数据源，使用默认顺序")
            valid_priority = ["akshare", "yahoo_finance", "finnhub"]

        logger.info(f"📊 [HK K线有效数据源] {valid_priority}")

        for source_name in valid_priority:
            source_key = source_name.lower()
            handler_name, handler_func = source_handlers[source_key]
            try:
                # 🔥 使用 asyncio.to_thread 避免阻塞事件循环
                asyncio = importlib.import_module("asyncio")
                kline_data = await asyncio.to_thread(handler_func, code, period, limit)
                data_source = handler_name

                if kline_data:
                    logger.info(f"✅ {data_source}获取港股K线成功: {code}")
                    break
            except Exception as e:
                logger.warning(f"⚠️ {source_name}获取K线失败: {e}")
                continue

        if not kline_data:
            raise Exception(f"无法获取港股{code}的K线数据：所有数据源均失败")

        # 4. 保存到缓存
        self.cache.save_stock_data(
            symbol=code,
            data=json.dumps(kline_data, ensure_ascii=False),
            data_source=cache_key_str,
        )
        logger.info(f"💾 港股K线已缓存: {code}")

        return kline_data

    async def _get_us_kline(
        self, code: str, period: str, limit: int, force_refresh: bool = False
    ) -> List[Dict]:
        """
        获取美股K线数据
        🔥 按照数据库配置的数据源优先级调用API
        """
        # 1. 检查缓存（除非强制刷新）
        cache_key_str = f"us_kline_{period}_{limit}"
        if not force_refresh:
            cache_key = self.cache.find_cached_stock_data(
                symbol=code, data_source=cache_key_str
            )

            if cache_key:
                cached_data = self.cache.load_stock_data(cache_key)
                if cached_data:
                    logger.info(f"⚡ 从缓存获取美股K线: {code}")
                    return self._parse_cached_kline(cached_data)

        # 2. 从数据库获取数据源优先级
        source_priority = await self._get_source_priority("US")

        # 3. 按优先级尝试各个数据源
        kline_data = None
        data_source = ""

        # 数据源名称映射
        source_handlers = {
            "alpha_vantage": ("alpha_vantage", self._get_us_kline_from_alpha_vantage),
            "yahoo_finance": ("yfinance", self._get_us_kline_from_yfinance),
            "finnhub": ("finnhub", self._get_us_kline_from_finnhub),
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
            logger.warning("⚠️ 数据库中没有配置有效的美股数据源，使用默认顺序")
            valid_priority = ["yahoo_finance", "alpha_vantage", "finnhub"]

        logger.info(f"📊 [US K线有效数据源] {valid_priority}")

        for source_name in valid_priority:
            source_key = source_name.lower()
            handler_name, handler_func = source_handlers[source_key]
            try:
                # 🔥 使用 asyncio.to_thread 避免阻塞事件循环
                asyncio = importlib.import_module("asyncio")
                kline_data = await asyncio.to_thread(handler_func, code, period, limit)
                data_source = handler_name

                if kline_data:
                    logger.info(f"✅ {data_source}获取美股K线成功: {code}")
                    break
            except Exception as e:
                logger.warning(f"⚠️ {source_name}获取K线失败: {e}")
                continue

        if not kline_data:
            raise Exception(f"无法获取美股{code}的K线数据：所有数据源均失败")

        # 4. 保存到缓存
        self.cache.save_stock_data(
            symbol=code,
            data=json.dumps(kline_data, ensure_ascii=False),
            data_source=cache_key_str,
        )
        logger.info(f"💾 美股K线已缓存: {code}")

        return kline_data

    def _get_us_kline_from_yfinance(
        self, code: str, period: str, limit: int
    ) -> List[Dict]:
        """从yfinance获取美股K线数据"""
        yf = importlib.import_module("yfinance")

        ticker = yf.Ticker(code)

        # 周期映射
        period_map = {
            "day": "1d",
            "week": "1wk",
            "month": "1mo",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "60m": "60m",
        }

        interval = period_map.get(period, "1d")
        hist = ticker.history(period=f"{limit}d", interval=interval)

        if hist.empty:
            raise Exception("无数据")

        # 格式化数据
        kline_data = []
        for date, row in hist.iterrows():
            row_data = cast(Any, row)
            date_str = cast(Any, date).strftime("%Y-%m-%d")
            kline_data.append(
                {
                    "date": date_str,
                    "trade_date": date_str,  # 前端需要这个字段
                    "open": float(row_data["Open"]),
                    "high": float(row_data["High"]),
                    "low": float(row_data["Low"]),
                    "close": float(row_data["Close"]),
                    "volume": int(row_data["Volume"]),
                }
            )

        return kline_data

    def _get_us_kline_from_alpha_vantage(
        self, code: str, period: str, limit: int
    ) -> List[Dict]:
        """从Alpha Vantage获取美股K线数据"""
        get_api_key = getattr(
            importlib.import_module("trader.flows.providers.us.alpha.common"),
            "get_api_key",
        )
        _make_api_request = getattr(
            importlib.import_module("trader.flows.providers.us.alpha.common"),
            "_make_api_request",
        )
        pd = importlib.import_module("pandas")

        # 获取 API Key
        api_key = get_api_key()
        if not api_key:
            raise Exception("Alpha Vantage API Key 未配置")

        # 根据周期选择API函数
        if period in ["5m", "15m", "30m", "60m"]:
            function = "TIME_SERIES_INTRADAY"
            params = {"symbol": code.upper(), "interval": period, "outputsize": "full"}
            time_series_key = f"Time Series ({period})"
        else:
            function = "TIME_SERIES_DAILY"
            params = {"symbol": code.upper(), "outputsize": "full"}
            time_series_key = "Time Series (Daily)"

        data = cast(Dict[str, Any], _make_api_request(function, params))

        if not data or time_series_key not in data:
            raise Exception("无数据")

        time_series = cast(Dict[str, Any], data[time_series_key])

        # 转换为 DataFrame
        df = pd.DataFrame.from_dict(time_series, orient="index")
        df.index = pd.to_datetime(df.index)
        df = df.sort_index(ascending=False)  # 最新的在前

        # 限制数量
        df = df.head(limit)

        # 格式化数据
        kline_data = []
        for date, row in df.iterrows():
            row_data = cast(Any, row)
            date_str = cast(Any, date).strftime("%Y-%m-%d")
            kline_data.append(
                {
                    "date": date_str,
                    "trade_date": date_str,  # 前端需要这个字段
                    "open": float(row_data["1. open"]),
                    "high": float(row_data["2. high"]),
                    "low": float(row_data["3. low"]),
                    "close": float(row_data["4. close"]),
                    "volume": int(row_data["5. volume"]),
                }
            )

        return kline_data

    def _get_us_kline_from_finnhub(
        self, code: str, period: str, limit: int
    ) -> List[Dict]:
        """从Finnhub获取美股K线数据"""
        finnhub = importlib.import_module("finnhub")
        datetime = getattr(importlib.import_module("datetime"), "datetime")
        timedelta = getattr(importlib.import_module("datetime"), "timedelta")

        # 获取 API Key
        api_key = settings.FINNHUB_API_KEY
        if not api_key:
            raise Exception("Finnhub API Key 未配置")

        # 创建客户端
        client = finnhub.Client(api_key=api_key)

        # 计算日期范围
        end_date = datetime.now()

        # 根据周期计算开始日期
        if period == "day":
            start_date = end_date - timedelta(days=limit)
            resolution = "D"
        elif period == "week":
            start_date = end_date - timedelta(weeks=limit)
            resolution = "W"
        elif period == "month":
            start_date = end_date - timedelta(days=limit * 30)
            resolution = "M"
        elif period == "5m":
            start_date = end_date - timedelta(days=limit)
            resolution = "5"
        elif period == "15m":
            start_date = end_date - timedelta(days=limit)
            resolution = "15"
        elif period == "30m":
            start_date = end_date - timedelta(days=limit)
            resolution = "30"
        elif period == "60m":
            start_date = end_date - timedelta(days=limit)
            resolution = "60"
        else:
            start_date = end_date - timedelta(days=limit)
            resolution = "D"

        # 获取K线数据
        candles = client.stock_candles(
            code.upper(),
            resolution,
            int(start_date.timestamp()),
            int(end_date.timestamp()),
        )

        if not candles or candles.get("s") != "ok":
            raise Exception("无数据")

        # 格式化数据
        kline_data = []
        for i in range(len(candles["t"])):
            date_str = datetime.fromtimestamp(candles["t"][i]).strftime("%Y-%m-%d")
            kline_data.append(
                {
                    "date": date_str,
                    "trade_date": date_str,  # 前端需要这个字段
                    "open": float(candles["o"][i]),
                    "high": float(candles["h"][i]),
                    "low": float(candles["l"][i]),
                    "close": float(candles["c"][i]),
                    "volume": int(candles["v"][i]),
                }
            )

        return kline_data

    def _get_hk_kline_from_akshare(
        self, code: str, period: str, limit: int
    ) -> List[Dict]:
        """从AKShare获取港股K线数据"""
        ak = importlib.import_module("akshare")
        importlib.import_module("pandas")
        getattr(importlib.import_module("datetime"), "datetime")
        getattr(importlib.import_module("datetime"), "timedelta")
        get_improved_hk_provider = getattr(
            importlib.import_module("trader.flows.providers.hk.improved"),
            "get_improved_hk_provider",
        )

        # 标准化代码
        provider = get_improved_hk_provider()
        normalized_code = provider._normalize_hk_symbol(code)

        # 直接使用 AKShare API
        df = ak.stock_hk_daily(symbol=normalized_code, adjust="qfq")

        if df is None or df.empty:
            raise Exception("无数据")

        # 过滤最近的数据
        df = df.tail(limit)

        # 格式化数据
        kline_data = []
        for _, row in df.iterrows():
            row_data = cast(Any, row)
            # AKShare 返回的列名：date, open, close, high, low, volume
            date_value = row_data["date"]
            date_str = (
                date_value.strftime("%Y-%m-%d")
                if hasattr(date_value, "strftime")
                else str(date_value)
            )
            kline_data.append(
                {
                    "date": date_str,
                    "trade_date": date_str,
                    "open": float(row_data["open"]),
                    "high": float(row_data["high"]),
                    "low": float(row_data["low"]),
                    "close": float(row_data["close"]),
                    "volume": int(row_data["volume"]) if "volume" in row_data else 0,
                }
            )

        return kline_data

    def _get_hk_kline_from_yfinance(
        self, code: str, period: str, limit: int
    ) -> List[Dict]:
        """从Yahoo Finance获取港股K线数据"""
        yf = importlib.import_module("yfinance")
        importlib.import_module("pandas")

        ticker = yf.Ticker(f"{code}.HK")

        # 周期映射
        period_map = {
            "day": "1d",
            "week": "1wk",
            "month": "1mo",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "60m": "60m",
        }

        interval = period_map.get(period, "1d")
        hist = ticker.history(period=f"{limit}d", interval=interval)

        if hist.empty:
            raise Exception("无数据")

        # 格式化数据
        kline_data = []
        for date, row in hist.iterrows():
            row_data = cast(Any, row)
            date_str = cast(Any, date).strftime("%Y-%m-%d")
            kline_data.append(
                {
                    "date": date_str,
                    "trade_date": date_str,
                    "open": float(row_data["Open"]),
                    "high": float(row_data["High"]),
                    "low": float(row_data["Low"]),
                    "close": float(row_data["Close"]),
                    "volume": int(row_data["Volume"]),
                }
            )

        return kline_data[-limit:]  # 返回最后limit条

    def _get_hk_kline_from_finnhub(
        self, code: str, period: str, limit: int
    ) -> List[Dict]:
        """从Finnhub获取港股K线数据"""
        finnhub = importlib.import_module("finnhub")
        datetime = getattr(importlib.import_module("datetime"), "datetime")
        timedelta = getattr(importlib.import_module("datetime"), "timedelta")

        # 获取 API Key
        api_key = settings.FINNHUB_API_KEY
        if not api_key:
            raise Exception("Finnhub API Key 未配置")

        # 创建客户端
        client = finnhub.Client(api_key=api_key)

        # 港股代码需要添加 .HK 后缀
        hk_symbol = f"{code}.HK" if not code.endswith(".HK") else code

        # 周期映射
        resolution_map = {
            "day": "D",
            "week": "W",
            "month": "M",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "60m": "60",
        }

        resolution = resolution_map.get(period, "D")

        # 计算时间范围
        end_time = int(datetime.now().timestamp())
        start_time = int((datetime.now() - timedelta(days=limit * 2)).timestamp())

        # 获取K线数据
        candles = client.stock_candles(hk_symbol, resolution, start_time, end_time)

        if not candles or candles.get("s") != "ok":
            raise Exception("无数据")

        # 格式化数据
        kline_data = []
        for i in range(len(candles["t"])):
            date_str = datetime.fromtimestamp(candles["t"][i]).strftime("%Y-%m-%d")
            kline_data.append(
                {
                    "date": date_str,
                    "trade_date": date_str,
                    "open": float(candles["o"][i]),
                    "high": float(candles["h"][i]),
                    "low": float(candles["l"][i]),
                    "close": float(candles["c"][i]),
                    "volume": int(candles["v"][i]),
                }
            )

        return kline_data[-limit:]  # 返回最后limit条
