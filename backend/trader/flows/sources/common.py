# ruff: noqa: F401,F403,F405,F821
class _DataSourceManagerMixin1:
    def __init__(self):
        """初始化数据源管理器"""
        # 检查是否启用PostgreSQL缓存
        self.use_postgres_cache = self._check_postgres_enabled()

        self.default_source = self._get_default_source()
        self.available_sources = self._check_available_sources()
        self.current_source = self.default_source

        # 初始化统一缓存管理器
        self.cache_manager = None
        self.cache_enabled = False
        try:
            get_cache = getattr(
                importlib.import_module("trader.flows.cache"), "get_cache"
            )
            self.cache_manager = get_cache()
            self.cache_enabled = True
            logger.info("✅ 统一缓存管理器已启用")
        except Exception as e:
            logger.warning(f"⚠️ 统一缓存管理器初始化失败: {e}")

        logger.info("📊 数据源管理器初始化完成")
        logger.info(
            f"   PostgreSQL缓存: {'✅ 已启用' if self.use_postgres_cache else '❌ 未启用'}"
        )
        logger.info(
            f"   统一缓存: {'✅ 已启用' if self.cache_enabled else '❌ 未启用'}"
        )
        logger.info(f"   默认数据源: {self.default_source.value}")
        logger.info(f"   可用数据源: {[s.value for s in self.available_sources]}")

    def _check_postgres_enabled(self) -> bool:
        """检查是否启用PostgreSQL缓存"""
        use_app_cache_enabled = getattr(
            importlib.import_module("trader.config.runtime"), "use_app_cache_enabled"
        )
        return use_app_cache_enabled()

    def _get_data_source_priority_order(
        self, symbol: Optional[str] = None
    ) -> List[ChinaDataSource]:
        """
        从数据库获取数据源优先级顺序（用于降级）

        Args:
            symbol: 股票代码，用于识别市场类型（A股/美股/港股）

        Returns:
            按优先级排序的数据源列表（不包含PostgreSQL，因为PostgreSQL是最高优先级）
        """
        # 🔥 识别市场类型
        market_category = self._identify_market_category(symbol)

        try:
            # 🔥 从数据库读取数据源配置（使用同步客户端）
            get_postgres_db_sync = getattr(
                importlib.import_module("app.core.database"), "get_postgres_db_sync"
            )
            db = get_postgres_db_sync()
            config_collection = db.system_configs

            # 获取最新的激活配置
            config_data = config_collection.find_one(
                {"is_active": True}, sort=[("version", -1)]
            )

            if config_data and config_data.get("data_source_configs"):
                data_source_configs = config_data.get("data_source_configs", [])

                # 🔥 过滤出启用的数据源，并按市场分类过滤
                enabled_sources = []
                for ds in data_source_configs:
                    if not ds.get("enabled", True):
                        continue

                    # 检查数据源是否属于当前市场分类
                    market_categories = ds.get("market_categories", [])
                    if market_categories and market_category:
                        # 如果数据源配置了市场分类，只选择匹配的数据源
                        if market_category not in market_categories:
                            continue

                    enabled_sources.append(ds)

                # 按优先级排序（数字越大优先级越高）
                enabled_sources.sort(key=lambda x: x.get("priority", 0), reverse=True)

                # 转换为 ChinaDataSource 枚举（使用统一编码）
                source_mapping = {
                    DataSourceCode.TUSHARE: ChinaDataSource.TUSHARE,
                    DataSourceCode.AKSHARE: ChinaDataSource.AKSHARE,
                    DataSourceCode.BAOSTOCK: ChinaDataSource.BAOSTOCK,
                }

                result = []
                for ds in enabled_sources:
                    ds_type = ds.get("type", "").lower()
                    if ds_type in source_mapping:
                        source = source_mapping[ds_type]
                        # 排除 PostgreSQL（PostgreSQL 是最高优先级，不参与降级）
                        if (
                            source != ChinaDataSource.POSTGRES
                            and source in self.available_sources
                        ):
                            result.append(source)

                if result:
                    logger.info(
                        f"✅ [数据源优先级] 市场={market_category or '全部'}, 从数据库读取: {[s.value for s in result]}"
                    )
                    return result
                else:
                    logger.warning(
                        f"⚠️ [数据源优先级] 市场={market_category or '全部'}, 数据库配置中没有可用的数据源，使用默认顺序"
                    )
            else:
                logger.warning("⚠️ [数据源优先级] 数据库中没有数据源配置，使用默认顺序")
        except Exception as e:
            logger.warning(f"⚠️ [数据源优先级] 从数据库读取失败: {e}，使用默认顺序")

        # 🔥 回退到默认顺序（兼容性）
        # 默认顺序：AKShare > Tushare > BaoStock
        default_order = [
            ChinaDataSource.AKSHARE,
            ChinaDataSource.TUSHARE,
            ChinaDataSource.BAOSTOCK,
        ]
        # 只返回可用的数据源
        return [s for s in default_order if s in self.available_sources]

    def _identify_market_category(self, symbol: Optional[str]) -> Optional[str]:
        """
        识别股票代码所属的市场分类

        Args:
            symbol: 股票代码

        Returns:
            市场分类ID（a_shares/us_stocks/hk_stocks），如果无法识别则返回None
        """
        if not symbol:
            return None

        try:
            StockUtils = getattr(
                importlib.import_module("trader.utils.stocks"), "StockUtils"
            )
            StockMarket = getattr(
                importlib.import_module("trader.utils.stocks"), "StockMarket"
            )

            market = StockUtils.identify_stock_market(symbol)

            # 映射到市场分类ID
            market_mapping = {
                StockMarket.CHINA_A: "a_shares",
                StockMarket.US: "us_stocks",
                StockMarket.HONG_KONG: "hk_stocks",
            }

            category = market_mapping.get(market)
            if category:
                logger.debug(f"🔍 [市场识别] {symbol} → {category}")
            return category
        except Exception as e:
            logger.warning(f"⚠️ [市场识别] 识别失败: {e}")
            return None

    def _get_default_source(self) -> ChinaDataSource:
        """获取默认数据源"""
        # 如果启用PostgreSQL缓存，PostgreSQL作为最高优先级数据源
        if self.use_postgres_cache:
            return ChinaDataSource.POSTGRES

        # 从 Settings 获取，默认使用AKShare作为第一优先级数据源
        env_source = settings.text_value(
            "DEFAULT_CHINA_DATA_SOURCE", DataSourceCode.AKSHARE.value
        ).lower()

        # 映射到枚举（使用统一编码）
        source_mapping = {
            DataSourceCode.TUSHARE.value: ChinaDataSource.TUSHARE,
            DataSourceCode.AKSHARE.value: ChinaDataSource.AKSHARE,
            DataSourceCode.BAOSTOCK.value: ChinaDataSource.BAOSTOCK,
        }

        return source_mapping.get(env_source, ChinaDataSource.AKSHARE)

    def get_china_stock_data_tushare(
        self, symbol: str, start_date: str, end_date: str
    ) -> str:
        """
        使用Tushare获取中国A股历史数据

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            str: 格式化的股票数据报告
        """
        # 临时切换到Tushare数据源
        original_source = self.current_source
        self.current_source = ChinaDataSource.TUSHARE

        try:
            result = self._get_tushare_data(symbol, start_date, end_date)
            return result
        finally:
            # 恢复原始数据源
            self.current_source = original_source

    def get_fundamentals_data(self, symbol: str) -> str:
        """
        获取基本面数据，支持多数据源和自动降级
        优先级：PostgreSQL → Tushare → AKShare → 生成分析

        Args:
            symbol: 股票代码

        Returns:
            str: 基本面分析报告
        """
        logger.info(
            f"📊 [数据来源: {self.current_source.value}] 开始获取基本面数据: {symbol}",
            extra={
                "symbol": symbol,
                "data_source": self.current_source.value,
                "event_type": "fundamentals_fetch_start",
            },
        )

        start_time = time.time()

        try:
            # 根据数据源调用相应的获取方法
            if self.current_source == ChinaDataSource.POSTGRES:
                result = self._get_postgres_fundamentals(symbol)
            elif self.current_source == ChinaDataSource.TUSHARE:
                result = self._get_tushare_fundamentals(symbol)
            elif self.current_source == ChinaDataSource.AKSHARE:
                result = self._get_akshare_fundamentals(symbol)
            else:
                # 其他数据源暂不支持基本面数据，生成基本分析
                result = self._generate_fundamentals_analysis(symbol)

            # 检查结果
            duration = time.time() - start_time
            result_length = len(result) if result else 0

            if result and "❌" not in result:
                logger.info(
                    f"✅ [数据来源: {self.current_source.value}] 成功获取基本面数据: {symbol} ({result_length}字符, 耗时{duration:.2f}秒)",
                    extra={
                        "symbol": symbol,
                        "data_source": self.current_source.value,
                        "duration": duration,
                        "result_length": result_length,
                        "event_type": "fundamentals_fetch_success",
                    },
                )
                return result
            else:
                logger.warning(
                    f"⚠️ [数据来源: {self.current_source.value}失败] 基本面数据质量异常，尝试降级: {symbol}",
                    extra={
                        "symbol": symbol,
                        "data_source": self.current_source.value,
                        "event_type": "fundamentals_fetch_fallback",
                    },
                )
                return self._try_fallback_fundamentals(symbol)

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"❌ [数据来源: {self.current_source.value}异常] 获取基本面数据失败: {symbol} - {e}",
                extra={
                    "symbol": symbol,
                    "data_source": self.current_source.value,
                    "duration": duration,
                    "error": str(e),
                    "event_type": "fundamentals_fetch_exception",
                },
                exc_info=True,
            )
            return self._try_fallback_fundamentals(symbol)

    def get_china_stock_fundamentals_tushare(self, symbol: str) -> str:
        """
        使用Tushare获取中国股票基本面数据（兼容旧接口）

        Args:
            symbol: 股票代码

        Returns:
            str: 基本面分析报告
        """
        # 重定向到统一接口
        return self._get_tushare_fundamentals(symbol)

    def get_news_data(
        self, symbol: Optional[str] = None, hours_back: int = 24, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        获取新闻数据的统一接口，支持多数据源和自动降级
        优先级：PostgreSQL → Tushare → AKShare

        Args:
            symbol: 股票代码，为空则获取市场新闻
            hours_back: 回溯小时数
            limit: 返回数量限制

        Returns:
            List[Dict]: 新闻数据列表
        """
        logger.info(
            f"📰 [数据来源: {self.current_source.value}] 开始获取新闻数据: {symbol or '市场新闻'}, 回溯{hours_back}小时",
            extra={
                "symbol": symbol,
                "hours_back": hours_back,
                "limit": limit,
                "data_source": self.current_source.value,
                "event_type": "news_fetch_start",
            },
        )

        start_time = time.time()
        symbol_text = symbol or ""

        try:
            # 根据数据源调用相应的获取方法
            if self.current_source == ChinaDataSource.POSTGRES:
                result = self._get_postgres_news(symbol_text, hours_back, limit)
            elif self.current_source == ChinaDataSource.TUSHARE:
                result = self._get_tushare_news(symbol_text, hours_back, limit)
            elif self.current_source == ChinaDataSource.AKSHARE:
                result = self._get_akshare_news(symbol_text, hours_back, limit)
            else:
                # 其他数据源暂不支持新闻数据
                logger.warning(f"⚠️ 数据源 {self.current_source.value} 不支持新闻数据")
                result = []

            # 检查结果
            duration = time.time() - start_time
            result_count = len(result) if result else 0

            if result and result_count > 0:
                logger.info(
                    f"✅ [数据来源: {self.current_source.value}] 成功获取新闻数据: {symbol or '市场新闻'} ({result_count}条, 耗时{duration:.2f}秒)",
                    extra={
                        "symbol": symbol,
                        "data_source": self.current_source.value,
                        "news_count": result_count,
                        "duration": duration,
                        "event_type": "news_fetch_success",
                    },
                )
                return result
            else:
                logger.warning(
                    f"⚠️ [数据来源: {self.current_source.value}] 未获取到新闻数据: {symbol or '市场新闻'}，尝试降级",
                    extra={
                        "symbol": symbol,
                        "data_source": self.current_source.value,
                        "duration": duration,
                        "event_type": "news_fetch_fallback",
                    },
                )
                return self._try_fallback_news(symbol_text, hours_back, limit)

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"❌ [数据来源: {self.current_source.value}异常] 获取新闻数据失败: {symbol or '市场新闻'} - {e}",
                extra={
                    "symbol": symbol,
                    "data_source": self.current_source.value,
                    "duration": duration,
                    "error": str(e),
                    "event_type": "news_fetch_exception",
                },
                exc_info=True,
            )
            return self._try_fallback_news(symbol_text, hours_back, limit)

    def _check_available_sources(self) -> List[ChinaDataSource]:
        """
        检查可用的数据源

        检查逻辑：
        1. 检查依赖包是否安装（技术可用性）
        2. 检查数据库配置中是否启用（业务可用性）

        Returns:
            可用且已启用的数据源列表
        """
        available = []

        # 🔥 从数据库读取数据源配置，获取启用状态
        enabled_sources_in_db = set()
        try:
            get_postgres_db_sync = getattr(
                importlib.import_module("app.core.database"), "get_postgres_db_sync"
            )
            db = get_postgres_db_sync()
            config_collection = db.system_configs

            # 获取最新的激活配置
            config_data = config_collection.find_one(
                {"is_active": True}, sort=[("version", -1)]
            )

            if config_data and config_data.get("data_source_configs"):
                data_source_configs = config_data.get("data_source_configs", [])

                # 提取已启用的数据源类型
                for ds in data_source_configs:
                    if ds.get("enabled", True):
                        ds_type = ds.get("type", "").lower()
                        enabled_sources_in_db.add(ds_type)

                logger.info(
                    f"✅ [数据源配置] 从数据库读取到已启用的数据源: {enabled_sources_in_db}"
                )
            else:
                logger.warning(
                    "⚠️ [数据源配置] 数据库中没有数据源配置，将检查所有已安装的数据源"
                )
                # 如果数据库中没有配置，默认所有数据源都启用
                enabled_sources_in_db = {"postgres", "tushare", "akshare", "baostock"}
        except Exception as e:
            logger.warning(
                f"⚠️ [数据源配置] 从数据库读取失败: {e}，将检查所有已安装的数据源"
            )
            # 如果读取失败，默认所有数据源都启用
            enabled_sources_in_db = {"postgres", "tushare", "akshare", "baostock"}

        # 检查PostgreSQL（最高优先级）
        if self.use_postgres_cache and "postgres" in enabled_sources_in_db:
            try:
                get_postgres_cache_adapter = getattr(
                    importlib.import_module("trader.flows.cache.postgres"),
                    "get_postgres_cache_adapter",
                )
                adapter = get_postgres_cache_adapter()
                if adapter.use_app_cache and adapter.db is not None:
                    available.append(ChinaDataSource.POSTGRES)
                    logger.info("✅ PostgreSQL数据源可用且已启用（最高优先级）")
                else:
                    logger.warning("⚠️ PostgreSQL数据源不可用: 数据库未连接")
            except Exception as e:
                logger.warning(f"⚠️ PostgreSQL数据源不可用: {e}")
        elif self.use_postgres_cache and "postgres" not in enabled_sources_in_db:
            logger.info("ℹ️ PostgreSQL数据源已在数据库中禁用")

        # 从数据库读取数据源配置
        datasource_configs = self._get_datasource_configs_from_db()

        # 检查Tushare
        if "tushare" in enabled_sources_in_db:
            try:
                importlib.import_module("tushare")
                # 优先从数据库配置读取 API Key，其次从 Settings 读取
                token = (
                    datasource_configs.get("tushare", {}).get("api_key")
                    or settings.TUSHARE_TOKEN
                )
                if token:
                    available.append(ChinaDataSource.TUSHARE)
                    source = (
                        "数据库配置"
                        if datasource_configs.get("tushare", {}).get("api_key")
                        else "环境变量"
                    )
                    logger.info(f"✅ Tushare数据源可用且已启用 (API Key来源: {source})")
                else:
                    logger.warning(
                        "⚠️ Tushare数据源不可用: API Key未配置（数据库和环境变量均未找到）"
                    )
            except ImportError:
                logger.warning("⚠️ Tushare数据源不可用: 库未安装")
        else:
            logger.info("ℹ️ Tushare数据源已在数据库中禁用")

        # 检查AKShare
        if "akshare" in enabled_sources_in_db:
            try:
                importlib.import_module("akshare")
                available.append(ChinaDataSource.AKSHARE)
                logger.info("✅ AKShare数据源可用且已启用")
            except ImportError:
                logger.warning("⚠️ AKShare数据源不可用: 库未安装")
        else:
            logger.info("ℹ️ AKShare数据源已在数据库中禁用")

        # 检查BaoStock
        if "baostock" in enabled_sources_in_db:
            try:
                importlib.import_module("baostock")
                available.append(ChinaDataSource.BAOSTOCK)
                logger.info("✅ BaoStock数据源可用且已启用")
            except ImportError:
                logger.warning("⚠️ BaoStock数据源不可用: 库未安装")
        else:
            logger.info("ℹ️ BaoStock数据源已在数据库中禁用")

        # TDX (通达信) 已移除
        # 不再检查和支持 TDX 数据源

        return available

    def _get_datasource_configs_from_db(self) -> dict:
        """从数据库读取数据源配置（包括 API Key）"""
        try:
            get_postgres_db_sync = getattr(
                importlib.import_module("app.core.database"), "get_postgres_db_sync"
            )
            db = get_postgres_db_sync()

            # 从 system_configs 集合读取激活的配置
            config = db.system_configs.find_one({"is_active": True})
            if not config:
                return {}

            # 提取数据源配置
            datasource_configs = config.get("data_source_configs", [])

            # 构建配置字典 {数据源名称: {api_key, api_secret, ...}}
            result = {}
            for ds_config in datasource_configs:
                name = ds_config.get("name", "").lower()
                result[name] = {
                    "api_key": ds_config.get("api_key", ""),
                    "api_secret": ds_config.get("api_secret", ""),
                    "config_params": ds_config.get("config_params", {}),
                }

            return result
        except Exception as e:
            logger.warning(f"⚠️ 从数据库读取数据源配置失败: {e}")
            return {}

    def get_current_source(self) -> ChinaDataSource:
        """获取当前数据源"""
        return self.current_source

    def set_current_source(self, source: ChinaDataSource) -> bool:
        """设置当前数据源"""
        if source in self.available_sources:
            self.current_source = source
            logger.info(f"✅ 数据源已切换到: {source.value}")
            return True
        else:
            logger.error(f"❌ 数据源不可用: {source.value}")
            return False

    def get_data_adapter(self):
        """获取当前数据源的适配器"""
        if self.current_source == ChinaDataSource.POSTGRES:
            return self._get_postgres_adapter()
        elif self.current_source == ChinaDataSource.TUSHARE:
            return self._get_tushare_adapter()
        elif self.current_source == ChinaDataSource.AKSHARE:
            return self._get_akshare_adapter()
        elif self.current_source == ChinaDataSource.BAOSTOCK:
            return self._get_baostock_adapter()
        # TDX 已移除
        else:
            raise ValueError(f"不支持的数据源: {self.current_source}")

    def _get_postgres_adapter(self):
        """获取PostgreSQL适配器"""
        try:
            get_postgres_cache_adapter = getattr(
                importlib.import_module("trader.flows.cache.postgres"),
                "get_postgres_cache_adapter",
            )
            return get_postgres_cache_adapter()
        except ImportError as e:
            logger.error(f"❌ PostgreSQL适配器导入失败: {e}")
            return None

    def _get_tushare_adapter(self):
        """获取Tushare提供器（原adapter已废弃，现在直接使用provider）"""
        try:
            get_tushare_provider = getattr(
                importlib.import_module("trader.flows.providers.china.tushare"),
                "get_tushare_provider",
            )
            return get_tushare_provider()
        except ImportError as e:
            logger.error(f"❌ Tushare提供器导入失败: {e}")
            return None

    def _get_akshare_adapter(self):
        """获取AKShare适配器"""
        try:
            get_akshare_provider = getattr(
                importlib.import_module("trader.flows.providers.china.akshare"),
                "get_akshare_provider",
            )
            return get_akshare_provider()
        except ImportError as e:
            logger.error(f"❌ AKShare适配器导入失败: {e}")
            return None

    def _get_baostock_adapter(self):
        """获取BaoStock适配器"""
        try:
            get_baostock_provider = getattr(
                importlib.import_module("trader.flows.providers.china.baostock"),
                "get_baostock_provider",
            )
            return get_baostock_provider()
        except ImportError as e:
            logger.error(f"❌ BaoStock适配器导入失败: {e}")
            return None

    def _get_cached_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_age_hours: int = 24,
    ) -> Optional[pd.DataFrame]:
        """
        从缓存获取数据

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            max_age_hours: 最大缓存时间（小时）

        Returns:
            DataFrame: 缓存的数据，如果没有则返回None
        """
        if not self.cache_enabled or not self.cache_manager:
            return None

        try:
            cache_key = self.cache_manager.find_cached_stock_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                max_age_hours=max_age_hours,
            )

            if cache_key:
                cached_data = self.cache_manager.load_stock_data(cache_key)
                if (
                    cached_data is not None
                    and hasattr(cached_data, "empty")
                    and not cached_data.empty
                ):
                    logger.debug(f"📦 从缓存获取{symbol}数据: {len(cached_data)}条")
                    return cached_data
        except Exception as e:
            logger.warning(f"⚠️ 从缓存读取数据失败: {e}")

        return None

    def _save_to_cache(
        self,
        symbol: str,
        data: pd.DataFrame,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ):
        """
        保存数据到缓存

        Args:
            symbol: 股票代码
            data: 数据
            start_date: 开始日期
            end_date: 结束日期
        """
        if not self.cache_enabled or not self.cache_manager:
            return

        try:
            if data is not None and hasattr(data, "empty") and not data.empty:
                self.cache_manager.save_stock_data(symbol, data, start_date, end_date)
                logger.debug(f"💾 保存{symbol}数据到缓存: {len(data)}条")
        except Exception as e:
            logger.warning(f"⚠️ 保存数据到缓存失败: {e}")
