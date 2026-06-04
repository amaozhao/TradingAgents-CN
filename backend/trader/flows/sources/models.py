# ruff: noqa: F401,F403,F405,F821
class _DataSourceManagerMixin3:
    def _get_tushare_data(
        self, symbol: str, start_date: str, end_date: str, period: str = "daily"
    ) -> str:
        """使用Tushare获取多周期数据 - 使用provider + 统一缓存"""
        logger.debug(
            f"📊 [Tushare] 调用参数: symbol={symbol}, start_date={start_date}, end_date={end_date}, period={period}"
        )

        # 添加详细的股票代码追踪日志
        logger.info(
            f"🔍 [股票代码追踪] _get_tushare_data 接收到的股票代码: '{symbol}' (类型: {type(symbol)})"
        )
        logger.info(f"🔍 [股票代码追踪] 股票代码长度: {len(str(symbol))}")
        logger.info(f"🔍 [股票代码追踪] 股票代码字符: {list(str(symbol))}")
        logger.info("🔍 [DataSourceManager详细日志] _get_tushare_data 开始执行")
        logger.info(
            f"🔍 [DataSourceManager详细日志] 当前数据源: {self.current_source.value}"
        )

        start_time = time.time()
        try:
            # 1. 先尝试从缓存获取
            cached_data = self._get_cached_data(
                symbol, start_date, end_date, max_age_hours=24
            )
            if cached_data is not None and not cached_data.empty:
                logger.info(f"✅ [缓存命中] 从缓存获取{symbol}数据")
                # 获取股票基本信息
                provider = self._get_tushare_adapter()
                if provider:
                    asyncio = importlib.import_module("asyncio")
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_closed():
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                    except RuntimeError:
                        # 在线程池中没有事件循环，创建新的
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                    stock_info = cast(
                        Dict[str, Any],
                        loop.run_until_complete(provider.get_stock_basic_info(symbol))
                        or {},
                    )
                    stock_name = (
                        stock_info.get("name", f"股票{symbol}")
                        if stock_info
                        else f"股票{symbol}"
                    )
                else:
                    stock_name = f"股票{symbol}"

                # 格式化返回
                return self._format_stock_data_response(
                    cached_data, symbol, stock_name, start_date, end_date
                )

            # 2. 缓存未命中，从provider获取
            logger.info(
                f"🔍 [股票代码追踪] 调用 tushare_provider，传入参数: symbol='{symbol}'"
            )
            logger.info("🔍 [DataSourceManager详细日志] 开始调用tushare_provider...")

            provider = self._get_tushare_adapter()
            if not provider:
                return "❌ Tushare提供器不可用"

            # 使用异步方法获取历史数据
            asyncio = importlib.import_module("asyncio")
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                # 在线程池中没有事件循环，创建新的
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            data = loop.run_until_complete(
                provider.get_historical_data(symbol, start_date, end_date)
            )

            if data is not None and not data.empty:
                # 保存到缓存
                self._save_to_cache(symbol, data, start_date, end_date)

                # 获取股票基本信息（异步）
                stock_info = cast(
                    Dict[str, Any],
                    loop.run_until_complete(provider.get_stock_basic_info(symbol))
                    or {},
                )
                stock_name = (
                    stock_info.get("name", f"股票{symbol}")
                    if stock_info
                    else f"股票{symbol}"
                )

                # 格式化返回
                result = self._format_stock_data_response(
                    data, symbol, stock_name, start_date, end_date
                )

                duration = time.time() - start_time
                logger.info(
                    f"🔍 [DataSourceManager详细日志] 调用完成，耗时: {duration:.3f}秒"
                )
                logger.info(
                    f"🔍 [股票代码追踪] 返回结果前200字符: {result[:200] if result else 'None'}"
                )
                logger.debug(
                    f"📊 [Tushare] 调用完成: 耗时={duration:.2f}s, 结果长度={len(result) if result else 0}"
                )

                return result
            else:
                result = f"❌ 未获取到{symbol}的有效数据"
                duration = time.time() - start_time
                logger.warning(f"⚠️ [Tushare] 未获取到数据，耗时={duration:.2f}s")
                return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"❌ [Tushare] 调用失败: {e}, 耗时={duration:.2f}s", exc_info=True
            )
            logger.error(f"❌ [DataSourceManager详细日志] 异常类型: {type(e).__name__}")
            logger.error(f"❌ [DataSourceManager详细日志] 异常信息: {str(e)}")
            traceback = importlib.import_module("traceback")
            logger.error(
                f"❌ [DataSourceManager详细日志] 异常堆栈: {traceback.format_exc()}"
            )
            raise

    def _get_akshare_data(
        self, symbol: str, start_date: str, end_date: str, period: str = "daily"
    ) -> str:
        """使用AKShare获取多周期数据 - 包含技术指标计算"""
        logger.debug(
            f"📊 [AKShare] 调用参数: symbol={symbol}, start_date={start_date}, end_date={end_date}, period={period}"
        )

        start_time = time.time()
        try:
            # 使用AKShare的统一接口
            get_akshare_provider = getattr(
                importlib.import_module("trader.flows.providers.china.akshare"),
                "get_akshare_provider",
            )
            provider = get_akshare_provider()

            # 使用异步方法获取历史数据
            asyncio = importlib.import_module("asyncio")
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                # 在线程池中没有事件循环，创建新的
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            data = loop.run_until_complete(
                provider.get_historical_data(symbol, start_date, end_date, period)
            )

            duration = time.time() - start_time

            if data is not None and not data.empty:
                # 🔧 修复：使用统一的格式化方法，包含技术指标计算
                # 获取股票基本信息
                stock_info = loop.run_until_complete(
                    provider.get_stock_basic_info(symbol)
                )
                stock_name = (
                    stock_info.get("name", f"股票{symbol}")
                    if stock_info
                    else f"股票{symbol}"
                )

                # 调用统一的格式化方法（包含技术指标计算）
                result = self._format_stock_data_response(
                    data, symbol, stock_name, start_date, end_date
                )

                logger.debug(
                    f"📊 [AKShare] 调用成功: 耗时={duration:.2f}s, 数据条数={len(data)}, 结果长度={len(result)}"
                )
                logger.info(
                    "✅ [AKShare] 已计算技术指标: MA5/10/20/60, MACD, RSI, BOLL"
                )
                return result
            else:
                result = f"❌ 未能获取{symbol}的股票数据"
                logger.warning(f"⚠️ [AKShare] 数据为空: 耗时={duration:.2f}s")
                return result

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"❌ [AKShare] 调用失败: {e}, 耗时={duration:.2f}s", exc_info=True
            )
            return f"❌ AKShare获取{symbol}数据失败: {e}"

    def _get_baostock_data(
        self, symbol: str, start_date: str, end_date: str, period: str = "daily"
    ) -> str:
        """使用BaoStock获取多周期数据 - 包含技术指标计算"""
        # 使用BaoStock的统一接口
        get_baostock_provider = getattr(
            importlib.import_module("trader.flows.providers.china.baostock"),
            "get_baostock_provider",
        )
        provider = get_baostock_provider()

        # 使用异步方法获取历史数据
        asyncio = importlib.import_module("asyncio")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            # 在线程池中没有事件循环，创建新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        data = loop.run_until_complete(
            provider.get_historical_data(symbol, start_date, end_date, period)
        )

        if data is not None and not data.empty:
            # 🔧 修复：使用统一的格式化方法，包含技术指标计算
            # 获取股票基本信息
            stock_info = loop.run_until_complete(provider.get_stock_basic_info(symbol))
            stock_name = (
                stock_info.get("name", f"股票{symbol}")
                if stock_info
                else f"股票{symbol}"
            )

            # 调用统一的格式化方法（包含技术指标计算）
            result = self._format_stock_data_response(
                data, symbol, stock_name, start_date, end_date
            )

            logger.info("✅ [BaoStock] 已计算技术指标: MA5/10/20/60, MACD, RSI, BOLL")
            return result
        else:
            return f"❌ 未能获取{symbol}的股票数据"

    def _get_volume_safely(self, data) -> float:
        """安全地获取成交量数据，支持多种列名"""
        try:
            # 支持多种可能的成交量列名
            volume_columns = ["volume", "vol", "turnover", "trade_volume"]

            for col in volume_columns:
                if col in data.columns:
                    logger.info(f"✅ 找到成交量列: {col}")
                    return data[col].sum()

            # 如果都没找到，记录警告并返回0
            logger.warning(f"⚠️ 未找到成交量列，可用列: {list(data.columns)}")
            return 0

        except Exception as e:
            logger.error(f"❌ 获取成交量失败: {e}")
            return 0

    def _try_fallback_sources(
        self, symbol: str, start_date: str, end_date: str, period: str = "daily"
    ) -> tuple[str, str | None]:
        """
        尝试备用数据源 - 避免递归调用

        Returns:
            tuple[str, str | None]: (结果字符串, 实际使用的数据源名称)
        """
        logger.info(
            f"🔄 [{self.current_source.value}] 失败，尝试备用数据源获取{period}数据: {symbol}"
        )

        # 🔥 从数据库获取数据源优先级顺序（根据股票代码识别市场）
        # 注意：不包含PostgreSQL，因为PostgreSQL是最高优先级，如果失败了就不再尝试
        fallback_order = self._get_data_source_priority_order(symbol)

        for source in fallback_order:
            if source != self.current_source and source in self.available_sources:
                try:
                    logger.info(
                        f"🔄 [备用数据源] 尝试 {source.value} 获取{period}数据: {symbol}"
                    )

                    # 直接调用具体的数据源方法，避免递归
                    if source == ChinaDataSource.TUSHARE:
                        result = self._get_tushare_data(
                            symbol, start_date, end_date, period
                        )
                    elif source == ChinaDataSource.AKSHARE:
                        result = self._get_akshare_data(
                            symbol, start_date, end_date, period
                        )
                    elif source == ChinaDataSource.BAOSTOCK:
                        result = self._get_baostock_data(
                            symbol, start_date, end_date, period
                        )
                    # TDX 已移除
                    else:
                        logger.warning(f"⚠️ 未知数据源: {source.value}")
                        continue

                    if "❌" not in result:
                        logger.info(
                            f"✅ [备用数据源-{source.value}] 成功获取{period}数据: {symbol}"
                        )
                        return result, source.value  # 返回结果和实际使用的数据源
                    else:
                        logger.warning(
                            f"⚠️ [备用数据源-{source.value}] 返回错误结果: {symbol}"
                        )

                except Exception as e:
                    logger.error(
                        f"❌ [备用数据源-{source.value}] 获取失败: {symbol}, 错误: {e}"
                    )
                    continue

        logger.error(f"❌ [所有数据源失败] 无法获取{period}数据: {symbol}")
        return f"❌ 所有数据源都无法获取{symbol}的{period}数据", None

    def get_stock_info(self, symbol: str) -> Dict:
        """
        获取股票基本信息，支持多数据源和自动降级
        优先级：PostgreSQL → Tushare → AKShare → BaoStock
        """
        logger.info(
            f"📊 [数据来源: {self.current_source.value}] 开始获取股票信息: {symbol}"
        )

        # 优先使用 App PostgreSQL 文档缓存（当 ta_use_app_cache=True）
        try:
            use_app_cache_enabled = getattr(
                importlib.import_module("trader.config.runtime"),
                "use_app_cache_enabled",
            )
            use_cache = use_app_cache_enabled(False)
            logger.info(f"🔧 [配置检查] use_app_cache_enabled() 返回值: {use_cache}")
        except Exception as e:
            logger.error(
                f"❌ [配置检查] use_app_cache_enabled() 调用失败: {e}", exc_info=True
            )
            use_cache = False

        logger.info(
            f"🔧 [配置] ta_use_app_cache={use_cache}, current_source={self.current_source.value}"
        )

        if use_cache:
            try:
                get_basics_from_cache = getattr(
                    importlib.import_module("trader.flows.cache.app"),
                    "get_basics_from_cache",
                )
                get_market_quote_dataframe = getattr(
                    importlib.import_module("trader.flows.cache.app"),
                    "get_market_quote_dataframe",
                )
                doc = cast(Dict[str, Any], get_basics_from_cache(symbol) or {})
                if doc:
                    name = doc.get("name") or doc.get("stock_name") or ""
                    # 规范化行业与板块（避免把“中小板/创业板”等板块值误作行业）
                    board_labels = {"主板", "中小板", "创业板", "科创板"}
                    raw_industry = (
                        doc.get("industry") or doc.get("industry_name") or ""
                    ).strip()
                    sec_or_cat = (doc.get("sec") or doc.get("category") or "").strip()
                    market_val = (doc.get("market") or "").strip()
                    industry_val = raw_industry or sec_or_cat or "未知"
                    changed = False
                    if raw_industry in board_labels:
                        # 若industry是板块名，则将其用于market；industry改用更细分类（sec/category）
                        if not market_val:
                            market_val = raw_industry
                            changed = True
                        if sec_or_cat:
                            industry_val = sec_or_cat
                            changed = True
                    if changed:
                        try:
                            logger.debug(
                                f"🔧 [字段归一化] industry原值='{raw_industry}' → 行业='{industry_val}', 市场/板块='{market_val or doc.get('market', '未知')}'"
                            )
                        except Exception:
                            pass

                    result = {
                        "symbol": symbol,
                        "name": name or f"股票{symbol}",
                        "area": doc.get("area", "未知"),
                        "industry": industry_val or "未知",
                        "market": market_val or doc.get("market", "未知"),
                        "list_date": doc.get("list_date", "未知"),
                        "source": "app_cache",
                    }
                    # 追加快照行情（若存在）
                    try:
                        df = get_market_quote_dataframe(symbol)
                        if df is not None and not df.empty:
                            row = df.iloc[-1]
                            result["current_price"] = row.get("close")
                            result["change_pct"] = row.get("pct_chg")
                            result["volume"] = row.get("volume")
                            result["quote_date"] = row.get("date")
                            result["quote_source"] = "market_quotes"
                            logger.info(
                                f"✅ [股票信息] 附加行情 | price={result['current_price']} pct={result['change_pct']} vol={result['volume']} code={symbol}"
                            )
                    except Exception as _e:
                        logger.debug(f"附加行情失败（忽略）：{_e}")

                    if name:
                        logger.info(
                            f"✅ [数据来源: PostgreSQL-stock_basic_info] 成功获取: {symbol}"
                        )
                        return result
                    else:
                        logger.warning(
                            f"⚠️ [数据来源: PostgreSQL] 未找到有效名称: {symbol}，降级到其他数据源"
                        )
            except Exception as e:
                logger.error(
                    f"❌ [数据来源: PostgreSQL异常] 获取股票信息失败: {e}",
                    exc_info=True,
                )

        # 首先尝试当前数据源
        try:
            if self.current_source == ChinaDataSource.TUSHARE:
                get_china_stock_info_tushare = getattr(
                    importlib.import_module("trader.flows.interface"),
                    "get_china_stock_info_tushare",
                )
                info_str = get_china_stock_info_tushare(symbol)
                result = self._parse_stock_info_string(info_str, symbol)

                # 检查是否获取到有效信息
                if result.get("name") and result["name"] != f"股票{symbol}":
                    logger.info(f"✅ [数据来源: Tushare-股票信息] 成功获取: {symbol}")
                    return result
                else:
                    logger.warning(
                        f"⚠️ [数据来源: Tushare失败] 返回无效信息，尝试降级: {symbol}"
                    )
                    return self._try_fallback_stock_info(symbol)
            else:
                adapter = self.get_data_adapter()
                if adapter and hasattr(adapter, "get_stock_info"):
                    result = cast(
                        Dict[str, Any],
                        getattr(cast(Any, adapter), "get_stock_info")(symbol),
                    )
                    if result.get("name") and result["name"] != f"股票{symbol}":
                        logger.info(
                            f"✅ [数据来源: {self.current_source.value}-股票信息] 成功获取: {symbol}"
                        )
                        return result
                    else:
                        logger.warning(
                            f"⚠️ [数据来源: {self.current_source.value}失败] 返回无效信息，尝试降级: {symbol}"
                        )
                        return self._try_fallback_stock_info(symbol)
                else:
                    logger.warning(
                        f"⚠️ [数据来源: {self.current_source.value}] 不支持股票信息获取，尝试降级: {symbol}"
                    )
                    return self._try_fallback_stock_info(symbol)

        except Exception as e:
            logger.error(
                f"❌ [数据来源: {self.current_source.value}异常] 获取股票信息失败: {e}",
                exc_info=True,
            )
            return self._try_fallback_stock_info(symbol)

    def get_stock_basic_info(self, stock_code: Optional[str] = None) -> Any:
        """
        获取股票基础信息（兼容 stock_data_service 接口）

        Args:
            stock_code: 股票代码，如果为 None 则返回所有股票列表

        Returns:
            Dict: 股票信息字典，或包含 error 字段的错误字典
        """
        if stock_code is None:
            # 返回所有股票列表
            logger.info("📊 获取所有股票列表")
            try:
                # 尝试从 PostgreSQL 获取
                get_database_manager = getattr(
                    importlib.import_module("trader.config.databases"),
                    "get_database_manager",
                )
                db_manager = get_database_manager()
                if db_manager and db_manager.is_postgres_available():
                    collection = cast(Any, db_manager).postgres_db["stock_basic_info"]
                    stocks = list(collection.find({}, {"_id": 0}))
                    if stocks:
                        logger.info(f"✅ 从PostgreSQL获取所有股票: {len(stocks)}条")
                        return stocks
            except Exception as e:
                logger.warning(f"⚠️ 从PostgreSQL获取所有股票失败: {e}")

            # 降级：返回空列表
            return []

        # 获取单个股票信息
        try:
            result = self.get_stock_info(stock_code)
            if result and result.get("name"):
                return result
            else:
                return {"error": f"未找到股票 {stock_code} 的信息"}
        except Exception as e:
            logger.error(f"❌ 获取股票信息失败: {e}")
            return {"error": str(e)}

    def get_stock_data_with_fallback(
        self, stock_code: str, start_date: str, end_date: str
    ) -> str:
        """
        获取股票数据（兼容 stock_data_service 接口）

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            str: 格式化的股票数据报告
        """
        logger.info(f"📊 获取股票数据: {stock_code} ({start_date} 到 {end_date})")

        try:
            # 使用统一的数据获取接口
            return self.get_stock_data(stock_code, start_date, end_date)
        except Exception as e:
            logger.error(f"❌ 获取股票数据失败: {e}")
            return f"❌ 获取股票数据失败: {str(e)}\n\n💡 建议：\n1. 检查网络连接\n2. 确认股票代码格式正确\n3. 检查数据源配置"

    def _try_fallback_stock_info(self, symbol: str) -> Dict:
        """尝试使用备用数据源获取股票基本信息"""
        logger.error(
            f"🔄 {self.current_source.value}失败，尝试备用数据源获取股票信息..."
        )

        # 获取所有可用数据源
        available_sources = self.available_sources.copy()

        # 移除当前数据源
        if self.current_source.value in available_sources:
            available_sources.remove(self.current_source.value)

        # 尝试所有备用数据源
        for source_name in available_sources:
            try:
                source = ChinaDataSource(source_name)
                logger.info(f"🔄 尝试备用数据源获取股票信息: {source_name}")

                # 根据数据源类型获取股票信息
                if source == ChinaDataSource.TUSHARE:
                    # 🔥 直接调用 Tushare 适配器，避免循环调用
                    get_china_stock_info_tushare = getattr(
                        importlib.import_module("trader.flows.interface"),
                        "get_china_stock_info_tushare",
                    )
                    result = self._parse_stock_info_string(
                        get_china_stock_info_tushare(symbol), symbol
                    )
                elif source == ChinaDataSource.AKSHARE:
                    result = self._get_akshare_stock_info(symbol)
                elif source == ChinaDataSource.BAOSTOCK:
                    result = self._get_baostock_stock_info(symbol)
                else:
                    # 尝试通用适配器
                    original_source = self.current_source
                    self.current_source = source
                    adapter = self.get_data_adapter()
                    self.current_source = original_source

                    if adapter and hasattr(adapter, "get_stock_info"):
                        result = cast(
                            Dict[str, Any],
                            getattr(cast(Any, adapter), "get_stock_info")(symbol),
                        )
                    else:
                        logger.warning(f"⚠️ [股票信息] {source_name}不支持股票信息获取")
                        continue

                # 检查是否获取到有效信息
                if result.get("name") and result["name"] != f"股票{symbol}":
                    logger.info(
                        f"✅ [数据来源: 备用数据源] 降级成功获取股票信息: {source_name}"
                    )
                    return result
                else:
                    logger.warning(f"⚠️ [数据来源: {source_name}] 返回无效信息")

            except Exception as e:
                logger.error(f"❌ 备用数据源{source_name}失败: {e}")
                continue

        # 所有数据源都失败，返回默认值
        logger.error(f"❌ 所有数据源都无法获取{symbol}的股票信息")
        return {"symbol": symbol, "name": f"股票{symbol}", "source": "unknown"}

    def _get_akshare_stock_info(self, symbol: str) -> Dict:
        """使用AKShare获取股票基本信息

        🔥 重要：AKShare 需要区分股票和指数
        - 对于 000001，如果不加后缀，会被识别为"深圳成指"（指数）
        - 对于股票，需要使用完整代码（如 sz000001 或 sh600000）
        """
        try:
            ak = importlib.import_module("akshare")

            # 🔥 转换为 AKShare 格式的股票代码
            # AKShare 的 stock_individual_info_em 需要使用 "sz000001" 或 "sh600000" 格式
            if symbol.startswith("6"):
                # 上海股票：600000 -> sh600000
                akshare_symbol = f"sh{symbol}"
            elif symbol.startswith(("0", "3", "2")):
                # 深圳股票：000001 -> sz000001
                akshare_symbol = f"sz{symbol}"
            elif symbol.startswith(("8", "4")):
                # 北京股票：830000 -> bj830000
                akshare_symbol = f"bj{symbol}"
            else:
                # 其他情况，直接使用原始代码
                akshare_symbol = symbol

            logger.debug(
                f"📊 [AKShare股票信息] 原始代码: {symbol}, AKShare格式: {akshare_symbol}"
            )

            # 尝试获取个股信息
            stock_info = ak.stock_individual_info_em(symbol=akshare_symbol)

            if stock_info is not None and not stock_info.empty:
                # 转换为字典格式
                info = {"symbol": symbol, "source": "akshare"}

                # 提取股票名称
                name_row = stock_info[stock_info["item"] == "股票简称"]
                if not name_row.empty:
                    stock_name = cast(Any, name_row["value"]).iloc[0]
                    info["name"] = stock_name
                    logger.info(f"✅ [AKShare股票信息] {symbol} -> {stock_name}")
                else:
                    info["name"] = f"股票{symbol}"
                    logger.warning(f"⚠️ [AKShare股票信息] 未找到股票简称: {symbol}")

                # 提取其他信息
                info["area"] = "未知"  # AKShare没有地区信息
                info["industry"] = "未知"  # 可以通过其他API获取
                info["market"] = "未知"  # 可以根据股票代码推断
                info["list_date"] = "未知"  # 可以通过其他API获取

                return info
            else:
                logger.warning(f"⚠️ [AKShare股票信息] 返回空数据: {symbol}")
                return {"symbol": symbol, "name": f"股票{symbol}", "source": "akshare"}

        except Exception as e:
            logger.error(f"❌ [股票信息] AKShare获取失败: {symbol}, 错误: {e}")
            return {
                "symbol": symbol,
                "name": f"股票{symbol}",
                "source": "akshare",
                "error": str(e),
            }
