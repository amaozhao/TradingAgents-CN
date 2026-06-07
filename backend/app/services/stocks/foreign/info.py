# ruff: noqa: F403,F405
from .common import *


class ForeignStockInfoMixin:
    async def _get_hk_info(self, code: str, force_refresh: bool = False) -> Dict:
        """
        获取港股基础信息
        🔥 按照数据库配置的数据源优先级调用API
        """
        # 1. 检查缓存（除非强制刷新）
        if not force_refresh:
            cache_key = self.cache.find_cached_stock_data(
                symbol=code, data_source="hk_basic_info"
            )

            if cache_key:
                cached_data = self.cache.load_stock_data(cache_key)
                if cached_data:
                    logger.info(f"⚡ 从缓存获取港股基础信息: {code}")
                    parsed_data = self._parse_cached_data(cached_data, "HK", code)
                    if parsed_data:
                        return parsed_data

        # 2. 从数据库获取数据源优先级
        source_priority = await self._get_source_priority("HK")

        # 3. 按优先级尝试各个数据源
        info_data = None
        data_source = ""

        # 数据源名称映射
        source_handlers = {
            "akshare": ("akshare", self._get_hk_info_from_akshare),
            "yahoo_finance": ("yfinance", self._get_hk_info_from_yfinance),
            "finnhub": ("finnhub", self._get_hk_info_from_finnhub),
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
            logger.warning("⚠️ 数据库中没有配置有效的港股基础信息数据源，使用默认顺序")
            valid_priority = ["akshare", "yahoo_finance", "finnhub"]

        logger.info(f"📊 [HK基础信息有效数据源] {valid_priority}")

        for source_name in valid_priority:
            source_key = source_name.lower()
            handler_name, handler_func = source_handlers[source_key]
            try:
                # 🔥 使用 asyncio.to_thread 避免阻塞事件循环
                asyncio = importlib.import_module("asyncio")
                info_data = await asyncio.to_thread(handler_func, code)
                data_source = handler_name

                if info_data:
                    logger.info(f"✅ {data_source}获取港股基础信息成功: {code}")
                    break
            except Exception as e:
                logger.warning(f"⚠️ {source_name}获取基础信息失败: {e}")
                continue

        if not info_data:
            raise Exception(f"无法获取港股{code}的基础信息：所有数据源均失败")

        # 4. 格式化数据
        formatted_data = self._format_hk_info(info_data, code, data_source)

        # 5. 保存到缓存
        self.cache.save_stock_data(
            symbol=code,
            data=json.dumps(formatted_data, ensure_ascii=False),
            data_source="hk_basic_info",
        )
        logger.info(f"💾 港股基础信息已缓存: {code}")

        return formatted_data

    async def _get_us_info(self, code: str, force_refresh: bool = False) -> Dict:
        """
        获取美股基础信息
        🔥 按照数据库配置的数据源优先级调用API
        """
        # 1. 检查缓存（除非强制刷新）
        if not force_refresh:
            cache_key = self.cache.find_cached_stock_data(
                symbol=code, data_source="us_basic_info"
            )

            if cache_key:
                cached_data = self.cache.load_stock_data(cache_key)
                if cached_data:
                    logger.info(f"⚡ 从缓存获取美股基础信息: {code}")
                    parsed_data = self._parse_cached_data(cached_data, "US", code)
                    if parsed_data:
                        return parsed_data

        # 2. 从数据库获取数据源优先级
        source_priority = await self._get_source_priority("US")

        # 3. 按优先级尝试各个数据源
        info_data = None
        data_source = ""

        # 数据源名称映射
        source_handlers = {
            "alpha_vantage": ("alpha_vantage", self._get_us_info_from_alpha_vantage),
            "yahoo_finance": ("yfinance", self._get_us_info_from_yfinance),
            "finnhub": ("finnhub", self._get_us_info_from_finnhub),
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

        logger.info(f"📊 [US基础信息有效数据源] {valid_priority}")

        for source_name in valid_priority:
            source_key = source_name.lower()
            handler_name, handler_func = source_handlers[source_key]
            try:
                # 🔥 使用 asyncio.to_thread 避免阻塞事件循环
                asyncio = importlib.import_module("asyncio")
                info_data = await asyncio.to_thread(handler_func, code)
                data_source = handler_name

                if info_data:
                    logger.info(f"✅ {data_source}获取美股基础信息成功: {code}")
                    break
            except Exception as e:
                logger.warning(f"⚠️ {source_name}获取基础信息失败: {e}")
                continue

        if not info_data:
            raise Exception(f"无法获取美股{code}的基础信息：所有数据源均失败")

        # 4. 格式化数据（匹配前端期望的字段名）
        market_cap = info_data.get("market_cap")
        formatted_data = {
            "code": code,
            "name": info_data.get("name") or f"美股{code}",
            "market": "US",
            "industry": info_data.get("industry"),
            "sector": info_data.get("sector"),
            # 前端期望 total_mv（单位：亿元）
            "total_mv": market_cap / 1e8 if market_cap else None,
            # 前端期望 pe_ttm 或 pe
            "pe_ttm": info_data.get("pe_ratio"),
            "pe": info_data.get("pe_ratio"),
            # 前端期望 pb
            "pb": info_data.get("pb_ratio"),
            # 前端期望 ps（暂无数据）
            "ps": None,
            "ps_ttm": None,
            # 前端期望 roe 和 debt_ratio（暂无数据）
            "roe": None,
            "debt_ratio": None,
            "dividend_yield": info_data.get("dividend_yield"),
            "currency": info_data.get("currency", "USD"),
            "source": data_source,
            "updated_at": datetime.now().isoformat(),
        }

        # 5. 保存到缓存
        self.cache.save_stock_data(
            symbol=code,
            data=json.dumps(formatted_data, ensure_ascii=False),
            data_source="us_basic_info",
        )
        logger.info(f"💾 美股基础信息已缓存: {code}")

        return formatted_data

    def _format_hk_info(self, data: Dict, code: str, source: str) -> Dict:
        """格式化港股基础信息"""
        market_cap = data.get("market_cap")
        return {
            "code": code,
            "name": data.get("name", f"港股{code}"),
            "market": "HK",
            "industry": data.get("industry"),
            "sector": data.get("sector"),
            # 前端期望 total_mv（单位：亿元）
            "total_mv": market_cap / 1e8 if market_cap else None,
            # 前端期望 pe_ttm 或 pe
            "pe_ttm": data.get("pe_ratio"),
            "pe": data.get("pe_ratio"),
            # 前端期望 pb
            "pb": data.get("pb_ratio"),
            # 前端期望 ps
            "ps": data.get("ps_ratio"),
            "ps_ttm": data.get("ps_ratio"),
            # 🔥 从财务指标中获取 roe 和 debt_ratio
            "roe": data.get("roe"),
            "debt_ratio": data.get("debt_ratio"),
            "dividend_yield": data.get("dividend_yield"),
            "currency": data.get("currency", "HKD"),
            "source": source,
            "updated_at": datetime.now().isoformat(),
        }

    def _get_us_info_from_yfinance(self, code: str) -> Dict:
        """从yfinance获取美股基础信息"""
        yf = importlib.import_module("yfinance")

        ticker = yf.Ticker(code)
        info = ticker.info

        if not info:
            raise Exception("无数据")

        return {
            "name": info.get("longName") or info.get("shortName"),
            "industry": info.get("industry"),
            "sector": info.get("sector"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "pb_ratio": info.get("priceToBook"),
            "dividend_yield": info.get("dividendYield"),
            "currency": info.get("currency", "USD"),
        }

    def _get_us_info_from_alpha_vantage(self, code: str) -> Dict:
        """从Alpha Vantage获取美股基础信息"""
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

        # 调用 OVERVIEW API
        params = {"symbol": code.upper()}
        data = cast(Dict[str, Any], _make_api_request("OVERVIEW", params))

        if not data or not data.get("Symbol"):
            raise Exception("无数据")

        return {
            "name": data.get("Name"),
            "industry": data.get("Industry"),
            "sector": data.get("Sector"),
            "market_cap": self._safe_float(data.get("MarketCapitalization")),
            "pe_ratio": self._safe_float(data.get("TrailingPE")),
            "pb_ratio": self._safe_float(data.get("PriceToBookRatio")),
            "dividend_yield": self._safe_float(data.get("DividendYield")),
            "currency": "USD",
        }

    def _get_us_info_from_finnhub(self, code: str) -> Dict:
        """从Finnhub获取美股基础信息"""

        # 获取 API Key
        api_key = settings.FINNHUB_API_KEY
        if not api_key:
            raise Exception("Finnhub API Key 未配置")

    def _get_hk_info_from_akshare(self, code: str) -> Dict:
        """从AKShare获取港股基础信息和财务指标"""
        get_hk_stock_info_akshare = getattr(
            importlib.import_module("trader.flows.providers.hk.improved"),
            "get_hk_stock_info_akshare",
        )
        get_hk_financial_indicators = getattr(
            importlib.import_module("trader.flows.providers.hk.improved"),
            "get_hk_financial_indicators",
        )

        # 1. 获取基础信息（包含当前价格）
        info = get_hk_stock_info_akshare(code)
        if not info or "error" in info:
            raise Exception("无数据")

        # 2. 获取财务指标（EPS、BPS、ROE、负债率等）
        financial_indicators = {}
        try:
            financial_indicators = get_hk_financial_indicators(code)
            logger.info(
                f"✅ 获取港股{code}财务指标成功: {list(financial_indicators.keys())}"
            )
        except Exception as e:
            logger.warning(f"⚠️ 获取港股{code}财务指标失败: {e}")

        # 3. 计算 PE、PB、PS（参考分析模块的计算方式）
        current_price = info.get("price")  # 当前价格
        pe_ratio = None
        pb_ratio = None
        ps_ratio = None

        if current_price and financial_indicators:
            # 计算 PE = 当前价 / EPS_TTM
            eps_ttm = financial_indicators.get("eps_ttm")
            if eps_ttm and eps_ttm > 0:
                pe_ratio = current_price / eps_ttm
                logger.info(f"📊 计算 PE: {current_price} / {eps_ttm} = {pe_ratio:.2f}")

            # 计算 PB = 当前价 / BPS
            bps = financial_indicators.get("bps")
            if bps and bps > 0:
                pb_ratio = current_price / bps
                logger.info(f"📊 计算 PB: {current_price} / {bps} = {pb_ratio:.2f}")

            # 计算 PS = 市值 / 营业收入（需要市值数据，暂时无法计算）
            # ps_ratio 暂时为 None

        # 4. 合并数据
        return {
            "name": info.get("name", f"港股{code}"),
            "market_cap": None,  # AKShare 基础信息不包含市值
            "industry": None,
            "sector": None,
            # 🔥 计算得到的估值指标
            "pe_ratio": pe_ratio,
            "pb_ratio": pb_ratio,
            "ps_ratio": ps_ratio,
            "dividend_yield": None,
            "currency": "HKD",
            # 🔥 从财务指标中获取
            "roe": financial_indicators.get("roe_avg"),  # 平均净资产收益率
            "debt_ratio": financial_indicators.get("debt_asset_ratio"),  # 资产负债率
        }

    def _get_hk_info_from_yfinance(self, code: str) -> Dict:
        """从Yahoo Finance获取港股基础信息"""
        yf = importlib.import_module("yfinance")

        ticker = yf.Ticker(f"{code}.HK")
        info = ticker.info

        return {
            "name": info.get("longName") or info.get("shortName") or f"港股{code}",
            "market_cap": info.get("marketCap"),
            "industry": info.get("industry"),
            "sector": info.get("sector"),
            "pe_ratio": info.get("trailingPE"),
            "pb_ratio": info.get("priceToBook"),
            "dividend_yield": info.get("dividendYield"),
            "currency": info.get("currency", "HKD"),
        }

    def _get_hk_info_from_finnhub(self, code: str) -> Dict:
        """从Finnhub获取港股基础信息"""
        finnhub = importlib.import_module("finnhub")

        # 获取 API Key
        api_key = settings.FINNHUB_API_KEY
        if not api_key:
            raise Exception("Finnhub API Key 未配置")

        # 创建客户端
        client = finnhub.Client(api_key=api_key)

        # 港股代码需要添加 .HK 后缀
        hk_symbol = f"{code}.HK" if not code.endswith(".HK") else code

        # 获取公司基本信息
        profile = client.company_profile2(symbol=hk_symbol)

        if not profile:
            raise Exception("无数据")

        return {
            "name": profile.get("name", f"港股{code}"),
            "market_cap": profile.get("marketCapitalization") * 1e6
            if profile.get("marketCapitalization")
            else None,  # Finnhub返回的是百万单位
            "industry": profile.get("finnhubIndustry"),
            "sector": None,
            "pe_ratio": None,
            "pb_ratio": None,
            "dividend_yield": None,
            "currency": profile.get("currency", "HKD"),
        }
