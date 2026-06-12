from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .imports import (
        Any,
        Dict,
        ZoneInfo,
        config_manager,
        datetime,
        get_cache,
        get_float,
        get_postgres_cache_adapter,
        get_timezone_name,
        importlib,
        logger,
        time,
    )

class _OptimizedChinaDataProviderMixin1:
    def __init__(self):
        self.cache = get_cache()
        self.config = config_manager.load_settings()
        self.last_api_call = 0
        self.min_api_interval = get_float(
            "TA_CHINA_MIN_API_INTERVAL_SECONDS",
            "ta_china_min_api_interval_seconds",
            0.5,
        )

        logger.info("📊 优化A股数据提供器初始化完成")

    def _wait_for_rate_limit(self):
        """等待API限制"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_api_call

        if time_since_last_call < self.min_api_interval:
            wait_time = self.min_api_interval - time_since_last_call
            time.sleep(wait_time)

        self.last_api_call = time.time()

    def _format_financial_data_to_fundamentals(self, financial_data: Dict[str, Any], symbol: str) -> str:
        """将PostgreSQL财务数据转换为基本面分析格式"""
        try:
            # 提取关键财务指标
            revenue = financial_data.get("total_revenue", "N/A")
            net_profit = financial_data.get("net_profit", "N/A")
            total_assets = financial_data.get("total_assets", "N/A")
            total_equity = financial_data.get("total_equity", "N/A")
            report_period = financial_data.get("report_period", "N/A")

            # 格式化数值（如果是数字则添加千分位，否则显示原值）
            def format_number(value):
                if isinstance(value, (int, float)):
                    return f"{value:,.2f}"
                return str(value)

            revenue_str = format_number(revenue)
            net_profit_str = format_number(net_profit)
            total_assets_str = format_number(total_assets)
            total_equity_str = format_number(total_equity)

            # 计算财务比率
            roe = "N/A"
            if isinstance(net_profit, (int, float)) and isinstance(total_equity, (int, float)) and total_equity != 0:
                roe = f"{(net_profit / total_equity * 100):.2f}%"

            roa = "N/A"
            if isinstance(net_profit, (int, float)) and isinstance(total_assets, (int, float)) and total_assets != 0:
                roa = f"{(net_profit / total_assets * 100):.2f}%"

            # 格式化输出
            fundamentals_report = f"""
# {symbol} 基本面数据分析

## 📊 财务概况
- **报告期**: {report_period}
- **营业收入**: {revenue_str} 元
- **净利润**: {net_profit_str} 元
- **总资产**: {total_assets_str} 元
- **股东权益**: {total_equity_str} 元

## 📈 财务比率
- **净资产收益率(ROE)**: {roe}
- **总资产收益率(ROA)**: {roa}

## 📝 数据说明
- 数据来源: PostgreSQL财务数据库
- 更新时间: {datetime.now(ZoneInfo(get_timezone_name())).strftime("%Y-%m-%d %H:%M:%S")}
- 数据类型: 同步财务数据
"""
            return fundamentals_report.strip()

        except Exception as e:
            logger.warning(f"⚠️ 格式化财务数据失败: {e}")
            return f"# {symbol} 基本面数据\n\n❌ 数据格式化失败: {str(e)}"

    def get_stock_data(self, symbol: str, start_date: str, end_date: str, force_refresh: bool = False) -> str:
        """
        获取A股数据 - 优先使用缓存

        Args:
            symbol: 股票代码（6位数字）
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            force_refresh: 是否强制刷新缓存

        Returns:
            格式化的股票数据字符串
        """
        logger.info(f"📈 获取A股数据: {symbol} ({start_date} 到 {end_date})")

        # 1. 优先尝试从PostgreSQL获取（如果启用了TA_USE_APP_CACHE）
        if not force_refresh:
            adapter = get_postgres_cache_adapter()
            if adapter.use_app_cache:
                df = adapter.get_historical_data(symbol, start_date, end_date)
                if df is not None and not df.empty:
                    logger.info(f"📊 [数据来源: PostgreSQL] 使用PostgreSQL历史数据: {symbol} ({len(df)}条记录)")
                    return df.to_string()

        # 2. 检查文件缓存（除非强制刷新）
        if not force_refresh:
            cache_key = self.cache.find_cached_stock_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                data_source="unified",  # 统一数据源（Tushare/AKShare/BaoStock）
            )

            if cache_key:
                cached_data = self.cache.load_stock_data(cache_key)
                if cached_data:
                    logger.info(f"⚡ [数据来源: 文件缓存] 从缓存加载A股数据: {symbol}")
                    return cached_data

        # 缓存未命中，从统一数据源接口获取
        logger.info(f"🌐 [数据来源: API调用] 从统一数据源接口获取数据: {symbol}")

        try:
            # API限制处理
            self._wait_for_rate_limit()

            # 调用统一数据源接口（默认Tushare，支持备用数据源）
            get_china_stock_data_unified = getattr(
                importlib.import_module("trader.flows.sources"),
                "get_china_stock_data_unified",
            )

            formatted_data = get_china_stock_data_unified(symbol=symbol, start_date=start_date, end_date=end_date)

            # 检查是否获取成功
            if "❌" in formatted_data or "错误" in formatted_data:
                logger.error(f"❌ [数据来源: API失败] 数据源API调用失败: {symbol}")
                # 尝试从旧缓存获取数据
                old_cache = self._try_get_old_cache(symbol, start_date, end_date)
                if old_cache:
                    logger.info(f"📁 [数据来源: 过期缓存] 使用过期缓存数据: {symbol}")
                    return old_cache

                # 生成备用数据
                logger.warning(f"⚠️ [数据来源: 备用数据] 生成备用数据: {symbol}")
                return self._generate_fallback_data(symbol, start_date, end_date, "数据源API调用失败")

            # 保存到缓存
            self.cache.save_stock_data(
                symbol=symbol,
                data=formatted_data,
                start_date=start_date,
                end_date=end_date,
                data_source="unified",  # 使用统一数据源标识
            )

            logger.info(f"✅ [数据来源: API调用成功] A股数据获取成功: {symbol}")
            return formatted_data

        except Exception as e:
            error_msg = f"Tushare数据接口调用异常: {str(e)}"
            logger.error(f"❌ {error_msg}")

            # 尝试从旧缓存获取数据
            old_cache = self._try_get_old_cache(symbol, start_date, end_date)
            if old_cache:
                logger.info(f"📁 使用过期缓存数据: {symbol}")
                return old_cache

            # 生成备用数据
            return self._generate_fallback_data(symbol, start_date, end_date, error_msg)

    def get_fundamentals_data(self, symbol: str, force_refresh: bool = False) -> str:
        """
        获取A股基本面数据 - 优先使用缓存

        Args:
            symbol: 股票代码
            force_refresh: 是否强制刷新缓存

        Returns:
            格式化的基本面数据字符串
        """
        logger.info(f"📊 获取A股基本面数据: {symbol}")

        # 1. 优先尝试从PostgreSQL获取财务数据（如果启用了TA_USE_APP_CACHE）
        if not force_refresh:
            adapter = get_postgres_cache_adapter()
            if adapter.use_app_cache:
                financial_data = adapter.get_financial_data(symbol)
                if financial_data:
                    logger.info(f"💰 [数据来源: PostgreSQL财务数据] 使用PostgreSQL财务数据: {symbol}")
                    # 将财务数据转换为基本面分析格式
                    return self._format_financial_data_to_fundamentals(financial_data, symbol)

        # 2. 检查文件缓存（除非强制刷新）
        if not force_refresh:
            # 查找基本面数据缓存
            for metadata_file in self.cache.metadata_dir.glob("*_meta.json"):
                try:
                    json = importlib.import_module("json")
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        metadata = json.load(f)

                    if (
                        metadata.get("symbol") == symbol
                        and metadata.get("data_type") == "fundamentals"
                        and metadata.get("market_type") == "china"
                    ):
                        cache_key = metadata_file.stem.replace("_meta", "")
                        if self.cache.is_cache_valid(cache_key, symbol=symbol, data_type="fundamentals"):
                            cached_data = self.cache.load_stock_data(cache_key)
                            if cached_data:
                                logger.info(f"⚡ [数据来源: 文件缓存] 从缓存加载A股基本面数据: {symbol}")
                                return cached_data
                except Exception:
                    continue

        # 缓存未命中，生成基本面分析
        logger.debug(f"🔍 [数据来源: 生成分析] 生成A股基本面分析: {symbol}")

        try:
            # 基本面分析只需要基础信息，不需要完整的历史交易数据
            # 获取股票基础信息（公司名称、当前价格等）
            stock_basic_info = self._get_stock_basic_info_only(symbol)

            # 生成基本面分析报告
            fundamentals_data = self._generate_fundamentals_report(symbol, stock_basic_info)

            # 保存到缓存
            self.cache.save_fundamentals_data(
                symbol=symbol,
                fundamentals_data=fundamentals_data,
                data_source="unified_analysis",  # 统一数据源分析
            )

            logger.info(f"✅ [数据来源: 生成分析成功] A股基本面数据生成成功: {symbol}")
            return fundamentals_data

        except Exception as e:
            error_msg = f"基本面数据生成失败: {str(e)}"
            logger.error(f"❌ [数据来源: 生成失败] {error_msg}")
            logger.warning(f"⚠️ [数据来源: 备用数据] 生成备用基本面数据: {symbol}")
            return self._generate_fallback_fundamentals(symbol, error_msg)

    def _get_stock_basic_info_only(self, symbol: str) -> str:
        """
        获取股票基础信息（仅用于基本面分析）
        不获取历史交易数据，只获取公司名称、当前价格等基础信息
        """
        logger.debug(f"📊 [基本面优化] 获取{symbol}基础信息（不含历史数据）")

        try:
            # 从统一接口获取股票基本信息
            get_china_stock_info_unified = getattr(
                importlib.import_module("trader.flows.interface"),
                "get_china_stock_info_unified",
            )
            stock_info = get_china_stock_info_unified(symbol)

            # 如果获取成功，直接返回基础信息
            if stock_info and "股票名称:" in stock_info:
                logger.debug(f"📊 [基本面优化] 成功获取{symbol}基础信息，无需历史数据")
                return stock_info

            # 如果基础信息获取失败，尝试从缓存获取最基本的信息
            try:
                use_app_cache_enabled = getattr(
                    importlib.import_module("trader.config.runtime"),
                    "use_app_cache_enabled",
                )
                if use_app_cache_enabled(False):
                    get_market_quote_dataframe = getattr(
                        importlib.import_module("trader.flows.cache.app"),
                        "get_market_quote_dataframe",
                    )
                    df_q = get_market_quote_dataframe(symbol)
                    if df_q is not None and not df_q.empty:
                        row_q = df_q.iloc[-1]
                        current_price = str(row_q.get("close", "N/A"))
                        change_pct = (
                            f"{float(row_q.get('pct_chg', 0)):+.2f}%" if row_q.get("pct_chg") is not None else "N/A"
                        )
                        volume = str(row_q.get("volume", "N/A"))

                        # 构造基础信息格式
                        basic_info = f"""股票代码: {symbol}
股票名称: 未知公司
当前价格: {current_price}
涨跌幅: {change_pct}
成交量: {volume}"""
                        logger.debug(f"📊 [基本面优化] 从缓存构造{symbol}基础信息")
                        return basic_info
            except Exception as e:
                logger.debug(f"📊 [基本面优化] 从缓存获取基础信息失败: {e}")

            # 如果都失败了，返回最基本的信息
            return f"股票代码: {symbol}\n股票名称: 未知公司\n当前价格: N/A\n涨跌幅: N/A\n成交量: N/A"

        except Exception as e:
            logger.warning(f"⚠️ [基本面优化] 获取{symbol}基础信息失败: {e}")
            return f"股票代码: {symbol}\n股票名称: 未知公司\n当前价格: N/A\n涨跌幅: N/A\n成交量: N/A"
