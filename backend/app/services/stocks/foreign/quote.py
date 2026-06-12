from .common import (
    Any,
    Dict,
    List,
    asyncio,
    cast,
    datetime,
    importlib,
    json,
    logger,
    settings,
)


class ForeignStockQuoteMixin:
    async def _get_hk_quote(self, code: str, force_refresh: bool = False) -> Dict:
        """
        获取港股实时行情（带请求去重）
        🔥 按照数据库配置的数据源优先级调用API
        🔥 防止并发请求重复调用API
        """
        # 1. 检查缓存（除非强制刷新）
        if not force_refresh:
            cache_key = self.cache.find_cached_stock_data(
                symbol=code, data_source="hk_realtime_quote"
            )

            if cache_key:
                cached_data = self.cache.load_stock_data(cache_key)
                if cached_data:
                    logger.info(f"⚡ 从缓存获取港股行情: {code}")
                    parsed_data = self._parse_cached_data(cached_data, "HK", code)
                    if parsed_data:
                        return parsed_data

        # 2. 🔥 请求去重：使用锁确保同一股票同时只有一个API调用
        request_key = f"HK_quote_{code}_{force_refresh}"
        lock = self._request_locks[request_key]

        async with lock:
            # 🔥 再次检查缓存（可能在等待锁的过程中，其他请求已经完成并缓存了数据）
            # 即使 force_refresh=True，也要检查是否有其他并发请求刚刚完成
            cache_key = self.cache.find_cached_stock_data(
                symbol=code, data_source="hk_realtime_quote"
            )
            if cache_key:
                cached_data = self.cache.load_stock_data(cache_key)
                if cached_data:
                    # 检查缓存时间，如果是最近1秒内的，说明是并发请求刚刚缓存的
                    try:
                        data_dict = (
                            json.loads(cached_data)
                            if isinstance(cached_data, str)
                            else cached_data
                        )
                        updated_at = data_dict.get("updated_at", "")
                        if updated_at:
                            cache_time = datetime.fromisoformat(updated_at)
                            time_diff = (datetime.now() - cache_time).total_seconds()
                            if time_diff < 1:  # 1秒内的缓存，说明是并发请求刚刚完成的
                                logger.info(
                                    f"⚡ [去重] 使用并发请求的结果: {code} (缓存时间: {time_diff:.2f}秒前)"
                                )
                                parsed_data = self._parse_cached_data(
                                    cached_data, "HK", code
                                )
                                if parsed_data:
                                    return parsed_data
                    except Exception as e:
                        logger.debug(f"检查缓存时间失败: {e}")

                    # 如果不是强制刷新，使用缓存
                    if not force_refresh:
                        logger.info(f"⚡ [去重后] 从缓存获取港股行情: {code}")
                        parsed_data = self._parse_cached_data(cached_data, "HK", code)
                        if parsed_data:
                            return parsed_data

            logger.info(f"🔄 开始获取港股行情: {code} (force_refresh={force_refresh})")

            # 3. 从数据库获取数据源优先级（使用统一方法）
            source_priority = await self._get_source_priority("HK")

            # 4. 按优先级尝试各个数据源
            quote_data = None
            data_source = ""

            # 数据源名称映射（数据库名称 → 处理函数）
            # 🔥 只有这些是有效的数据源名称
            source_handlers = {
                "yahoo_finance": ("yfinance", self._get_hk_quote_from_yfinance),
                "akshare": ("akshare", self._get_hk_quote_from_akshare),
            }

            # 过滤有效数据源并去重
            valid_priority = []
            seen = set()
            for source_name in source_priority:
                source_key = source_name.lower()
                # 只保留有效的数据源
                if source_key in source_handlers and source_key not in seen:
                    seen.add(source_key)
                    valid_priority.append(source_name)

            if not valid_priority:
                logger.warning("⚠️ 数据库中没有配置有效的港股数据源，使用默认顺序")
                valid_priority = ["yahoo_finance", "akshare"]

            logger.info(f"📊 [HK有效数据源] {valid_priority} (股票: {code})")

            for source_name in valid_priority:
                source_key = source_name.lower()
                handler_name, handler_func = source_handlers[source_key]
                try:
                    # 🔥 使用 asyncio.to_thread 避免阻塞事件循环
                    quote_data = await asyncio.to_thread(handler_func, code)
                    data_source = handler_name

                    if quote_data:
                        logger.info(f"✅ {data_source}获取港股行情成功: {code}")
                        break
                except Exception as e:
                    logger.warning(f"⚠️ {source_name}获取失败 ({code}): {e}")
                    continue

            if not quote_data:
                raise Exception(f"无法获取港股{code}的行情数据：所有数据源均失败")

            # 5. 格式化数据
            formatted_data = self._format_hk_quote(quote_data, code, data_source)

            # 6. 保存到缓存
            self.cache.save_stock_data(
                symbol=code,
                data=json.dumps(formatted_data, ensure_ascii=False),
                data_source="hk_realtime_quote",
            )
            logger.info(f"💾 港股行情已缓存: {code}")

            return formatted_data

    async def _get_source_priority(self, market: str) -> List[str]:
        """
        从数据库获取数据源优先级（统一方法）
        🔥 复用 UnifiedStockService 的实现
        """
        market_category_map = {"CN": "a_shares", "HK": "hk_stocks", "US": "us_stocks"}

        market_category_id = market_category_map.get(market)

        try:
            # 从 datasource_groupings 集合查询
            groupings = (
                await self.db.datasource_groupings.find(
                    {"market_category_id": market_category_id, "enabled": True}
                )
                .sort("priority", -1)
                .to_list(length=None)
            )

            if groupings:
                priority_list = [g["data_source_name"] for g in groupings]
                logger.info(f"📊 [{market}数据源优先级] 从数据库读取: {priority_list}")
                return priority_list
        except Exception as e:
            logger.warning(
                f"⚠️ [{market}数据源优先级] 从数据库读取失败: {e}，使用默认顺序"
            )

        # 默认优先级
        default_priority = {
            "CN": ["tushare", "akshare", "baostock"],
            "HK": ["yfinance", "akshare"],
            "US": ["yfinance", "alpha_vantage", "finnhub"],
        }
        priority_list = default_priority.get(market, [])
        logger.info(f"📊 [{market}数据源优先级] 使用默认: {priority_list}")
        return priority_list

    def _get_hk_quote_from_yfinance(self, code: str) -> Dict:
        """从yfinance获取港股行情"""
        quote_data = self.hk_provider.get_real_time_price(code)
        if not quote_data:
            raise Exception("无数据")
        return quote_data

    def _get_hk_quote_from_akshare(self, code: str) -> Dict:
        """从AKShare获取港股行情"""
        get_hk_stock_info_akshare = getattr(
            importlib.import_module("trader.flows.providers.hk.improved"),
            "get_hk_stock_info_akshare",
        )
        info = get_hk_stock_info_akshare(code)
        if not info or "error" in info:
            raise Exception("无数据")

        # 检查是否有价格数据
        if not info.get("price"):
            raise Exception("无价格数据")

        return info

    async def _get_us_quote(self, code: str, force_refresh: bool = False) -> Dict:
        """
        获取美股实时行情（带请求去重）
        🔥 按照数据库配置的数据源优先级调用API
        🔥 防止并发请求重复调用API
        """
        # 1. 检查缓存（除非强制刷新）
        if not force_refresh:
            cache_key = self.cache.find_cached_stock_data(
                symbol=code, data_source="us_realtime_quote"
            )

            if cache_key:
                cached_data = self.cache.load_stock_data(cache_key)
                if cached_data:
                    logger.info(f"⚡ 从缓存获取美股行情: {code}")
                    parsed_data = self._parse_cached_data(cached_data, "US", code)
                    if parsed_data:
                        return parsed_data

        # 2. 🔥 请求去重：使用锁确保同一股票同时只有一个API调用
        request_key = f"US_quote_{code}_{force_refresh}"
        lock = self._request_locks[request_key]

        async with lock:
            # 🔥 再次检查缓存（可能在等待锁的过程中，其他请求已经完成并缓存了数据）
            cache_key = self.cache.find_cached_stock_data(
                symbol=code, data_source="us_realtime_quote"
            )
            if cache_key:
                cached_data = self.cache.load_stock_data(cache_key)
                if cached_data:
                    # 检查缓存时间，如果是最近1秒内的，说明是并发请求刚刚缓存的
                    try:
                        data_dict = (
                            json.loads(cached_data)
                            if isinstance(cached_data, str)
                            else cached_data
                        )
                        updated_at = data_dict.get("updated_at", "")
                        if updated_at:
                            cache_time = datetime.fromisoformat(updated_at)
                            time_diff = (datetime.now() - cache_time).total_seconds()
                            if time_diff < 1:  # 1秒内的缓存，说明是并发请求刚刚完成的
                                logger.info(
                                    f"⚡ [去重] 使用并发请求的结果: {code} (缓存时间: {time_diff:.2f}秒前)"
                                )
                                parsed_data = self._parse_cached_data(
                                    cached_data, "US", code
                                )
                                if parsed_data:
                                    return parsed_data
                    except Exception as e:
                        logger.debug(f"检查缓存时间失败: {e}")

                    # 如果不是强制刷新，使用缓存
                    if not force_refresh:
                        logger.info(f"⚡ [去重后] 从缓存获取美股行情: {code}")
                        parsed_data = self._parse_cached_data(cached_data, "US", code)
                        if parsed_data:
                            return parsed_data

            logger.info(f"🔄 开始获取美股行情: {code} (force_refresh={force_refresh})")

            # 3. 从数据库获取数据源优先级（使用统一方法）
            source_priority = await self._get_source_priority("US")

            # 4. 按优先级尝试各个数据源
            quote_data = None
            data_source = ""

            # 数据源名称映射（数据库名称 → 处理函数）
            # 🔥 只有这些是有效的数据源名称：alpha_vantage, yahoo_finance, finnhub
            source_handlers = {
                "alpha_vantage": (
                    "alpha_vantage",
                    self._get_us_quote_from_alpha_vantage,
                ),
                "yahoo_finance": ("yfinance", self._get_us_quote_from_yfinance),
                "finnhub": ("finnhub", self._get_us_quote_from_finnhub),
            }

            # 过滤有效数据源并去重
            valid_priority = []
            seen = set()
            for source_name in source_priority:
                source_key = source_name.lower()
                # 只保留有效的数据源
                if source_key in source_handlers and source_key not in seen:
                    seen.add(source_key)
                    valid_priority.append(source_name)

            if not valid_priority:
                logger.warning("⚠️ 数据库中没有配置有效的美股数据源，使用默认顺序")
                valid_priority = ["yahoo_finance", "alpha_vantage", "finnhub"]

            logger.info(f"📊 [US有效数据源] {valid_priority} (股票: {code})")

            for source_name in valid_priority:
                source_key = source_name.lower()
                handler_name, handler_func = source_handlers[source_key]
                try:
                    # 🔥 使用 asyncio.to_thread 避免阻塞事件循环
                    quote_data = await asyncio.to_thread(handler_func, code)
                    data_source = handler_name

                    if quote_data:
                        logger.info(f"✅ {data_source}获取美股行情成功: {code}")
                        break
                except Exception as e:
                    logger.warning(f"⚠️ {source_name}获取失败 ({code}): {e}")
                    continue

            if not quote_data:
                raise Exception(f"无法获取美股{code}的行情数据：所有数据源均失败")

            # 5. 格式化数据
            formatted_data = {
                "code": code,
                "name": quote_data.get("name", f"美股{code}"),
                "market": "US",
                "price": quote_data.get("price"),
                "open": quote_data.get("open"),
                "high": quote_data.get("high"),
                "low": quote_data.get("low"),
                "volume": quote_data.get("volume"),
                "change_percent": quote_data.get("change_percent"),
                "trade_date": quote_data.get("trade_date"),
                "currency": quote_data.get("currency", "USD"),
                "source": data_source,
                "updated_at": datetime.now().isoformat(),
            }

            # 6. 保存到缓存
            self.cache.save_stock_data(
                symbol=code,
                data=json.dumps(formatted_data, ensure_ascii=False),
                data_source="us_realtime_quote",
            )
            logger.info(f"💾 美股行情已缓存: {code}")

            return formatted_data

    def _get_us_quote_from_yfinance(self, code: str) -> Dict:
        """从yfinance获取美股行情"""
        yf = importlib.import_module("yfinance")

        ticker = yf.Ticker(code)
        hist = ticker.history(period="1d")

        if hist.empty:
            raise Exception("无数据")

        latest = hist.iloc[-1]
        info = ticker.info

        return {
            "name": info.get("longName") or info.get("shortName"),
            "price": float(latest["Close"]),
            "open": float(latest["Open"]),
            "high": float(latest["High"]),
            "low": float(latest["Low"]),
            "volume": int(latest["Volume"]),
            "change_percent": round(
                ((latest["Close"] - latest["Open"]) / latest["Open"] * 100), 2
            ),
            "trade_date": cast(Any, hist.index[-1]).strftime("%Y-%m-%d"),
            "currency": info.get("currency", "USD"),
        }

    def _get_us_quote_from_alpha_vantage(self, code: str) -> Dict:
        """从Alpha Vantage获取美股行情"""
        try:
            get_api_key = getattr(
                importlib.import_module("trader.flows.providers.us.alpha.common"),
                "get_api_key",
            )
            _make_api_request = getattr(
                importlib.import_module("trader.flows.providers.us.alpha.common"),
                "_make_api_request",
            )

            # 获取 API Key
            api_key = get_api_key()
            if not api_key:
                raise Exception("Alpha Vantage API Key 未配置")

            # 调用 GLOBAL_QUOTE API
            params = {
                "symbol": code.upper(),
            }

            data = cast(Dict[str, Any], _make_api_request("GLOBAL_QUOTE", params))

            if not data or "Global Quote" not in data:
                raise Exception("Alpha Vantage 返回数据为空")

            quote = cast(Dict[str, Any], data["Global Quote"])

            if not quote:
                raise Exception("无数据")

            # 解析数据
            return {
                "symbol": quote.get("01. symbol", code),
                "price": float(quote.get("05. price", 0)),
                "open": float(quote.get("02. open", 0)),
                "high": float(quote.get("03. high", 0)),
                "low": float(quote.get("04. low", 0)),
                "volume": int(quote.get("06. volume", 0)),
                "latest_trading_day": quote.get("07. latest trading day", ""),
                "previous_close": float(quote.get("08. previous close", 0)),
                "change": float(quote.get("09. change", 0)),
                "change_percent": quote.get("10. change percent", "0%").rstrip("%"),
            }

        except Exception as e:
            logger.error(f"❌ Alpha Vantage获取美股行情失败: {e}")
            raise

    def _get_us_quote_from_finnhub(self, code: str) -> Dict:
        """从Finnhub获取美股行情"""
        try:
            finnhub = importlib.import_module("finnhub")

            # 获取 API Key
            api_key = settings.FINNHUB_API_KEY
            if not api_key:
                raise Exception("Finnhub API Key 未配置")

            # 创建客户端
            client = finnhub.Client(api_key=api_key)

            # 获取实时报价
            quote = client.quote(code.upper())

            if not quote or "c" not in quote:
                raise Exception("无数据")

            # 解析数据
            return {
                "symbol": code.upper(),
                "price": quote.get("c", 0),  # current price
                "open": quote.get("o", 0),  # open price
                "high": quote.get("h", 0),  # high price
                "low": quote.get("l", 0),  # low price
                "previous_close": quote.get("pc", 0),  # previous close
                "change": quote.get("d", 0),  # change
                "change_percent": quote.get("dp", 0),  # change percent
                "timestamp": quote.get("t", 0),  # timestamp
            }

        except Exception as e:
            logger.error(f"❌ Finnhub获取美股行情失败: {e}")
            raise

    def _format_hk_quote(self, data: Dict, code: str, source: str) -> Dict:
        """格式化港股行情数据"""
        return {
            "code": code,
            "name": data.get("name", f"港股{code}"),
            "market": "HK",
            "price": data.get("price") or data.get("close"),
            "open": data.get("open"),
            "high": data.get("high"),
            "low": data.get("low"),
            "volume": data.get("volume"),
            "currency": data.get("currency", "HKD"),
            "source": source,
            "trade_date": data.get("timestamp", datetime.now().strftime("%Y-%m-%d")),
            "updated_at": datetime.now().isoformat(),
        }
