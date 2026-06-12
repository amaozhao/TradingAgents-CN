from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .imports import (
        DataSourceCode,
        List,
        Optional,
        USDataSource,
        importlib,
        logger,
        settings,
    )

class USDataSourceManager:
    """
    美股数据源管理器

    支持的数据源：
    - yfinance: 股票价格和技术指标（免费）
    - alpha_vantage: 基本面和新闻数据（需要API Key）
    - finnhub: 备用数据源（需要API Key）
    - postgres: 缓存数据源（最高优先级）
    """

    def __init__(self):
        """初始化美股数据源管理器"""
        # 检查是否启用 PostgreSQL 缓存
        self.use_postgres_cache = self._check_postgres_enabled()

        # 检查可用的数据源
        self.available_sources = self._check_available_sources()

        # 设置默认数据源
        self.default_source = self._get_default_source()
        self.current_source = self.default_source

        logger.info("📊 美股数据源管理器初始化完成")
        logger.info(f"   PostgreSQL缓存: {'✅ 已启用' if self.use_postgres_cache else '❌ 未启用'}")
        logger.info(f"   默认数据源: {self.default_source.value}")
        logger.info(f"   可用数据源: {[s.value for s in self.available_sources]}")

    def _check_postgres_enabled(self) -> bool:
        """检查是否启用PostgreSQL缓存"""
        use_app_cache_enabled = getattr(importlib.import_module("trader.config.runtime"), "use_app_cache_enabled")
        return use_app_cache_enabled()

    def _get_data_source_priority_order(self, symbol: Optional[str] = None) -> List[USDataSource]:
        """
        从数据库获取美股数据源优先级顺序（用于降级）

        Args:
            symbol: 股票代码

        Returns:
            按优先级排序的数据源列表（不包含PostgreSQL）
        """
        try:
            # 从数据库读取数据源配置
            get_postgres_db_sync = getattr(importlib.import_module("app.core.database"), "get_postgres_db_sync")
            db = get_postgres_db_sync()

            # 方法1: 从 datasource_groupings 集合读取（推荐）
            groupings_collection = db.datasource_groupings
            groupings = list(
                groupings_collection.find({"market_category_id": "us_stocks", "enabled": True}).sort("priority", -1)
            )  # 降序排序，优先级高的在前

            if groupings:
                # 转换为 USDataSource 枚举
                # 🔥 数据源名称映射（数据库名称 → USDataSource 枚举）
                source_mapping = {
                    "yfinance": USDataSource.YFINANCE,
                    "yahoo_finance": USDataSource.YFINANCE,  # 别名
                    "alpha_vantage": USDataSource.ALPHA_VANTAGE,
                    "finnhub": USDataSource.FINNHUB,
                }

                result = []
                for grouping in groupings:
                    ds_name = grouping.get("data_source_name", "").lower()
                    if ds_name in source_mapping:
                        source = source_mapping[ds_name]
                        # 排除 PostgreSQL（PostgreSQL 是最高优先级，不参与降级）
                        if source != USDataSource.POSTGRES and source in self.available_sources:
                            result.append(source)

                if result:
                    logger.info(f"✅ [美股数据源优先级] 从数据库读取: {[s.value for s in result]}")
                    return result

            logger.warning("⚠️ [美股数据源优先级] 数据库中没有配置，使用默认顺序")
        except Exception as e:
            logger.warning(f"⚠️ [美股数据源优先级] 从数据库读取失败: {e}，使用默认顺序")

        # 回退到默认顺序
        # 默认顺序：yfinance > Alpha Vantage > Finnhub
        default_order = [
            USDataSource.YFINANCE,
            USDataSource.ALPHA_VANTAGE,
            USDataSource.FINNHUB,
        ]
        # 只返回可用的数据源
        return [s for s in default_order if s in self.available_sources]

    def _get_default_source(self) -> USDataSource:
        """获取默认数据源"""
        # 如果启用PostgreSQL缓存，PostgreSQL作为最高优先级数据源
        if self.use_postgres_cache:
            return USDataSource.POSTGRES

        # 从 Settings 获取，默认使用 yfinance
        env_source = settings.text_value("DEFAULT_US_DATA_SOURCE", DataSourceCode.YFINANCE.value).lower()

        # 映射到枚举
        source_mapping = {
            DataSourceCode.YFINANCE.value: USDataSource.YFINANCE,
            DataSourceCode.ALPHA_VANTAGE.value: USDataSource.ALPHA_VANTAGE,
            DataSourceCode.FINNHUB.value: USDataSource.FINNHUB,
        }

        return source_mapping.get(env_source, USDataSource.YFINANCE)

    def _check_available_sources(self) -> List[USDataSource]:
        """
        检查可用的数据源

        从数据库读取启用状态，并检查依赖是否满足
        """
        available = []

        # PostgreSQL 缓存
        if self.use_postgres_cache:
            available.append(USDataSource.POSTGRES)
            logger.info("✅ PostgreSQL缓存数据源可用")

        # 从数据库读取启用的数据源列表和配置
        enabled_sources_in_db = self._get_enabled_sources_from_db()
        datasource_configs = self._get_datasource_configs_from_db()

        # 检查 yfinance
        if "yfinance" in enabled_sources_in_db:
            try:
                importlib.import_module("yfinance")
                available.append(USDataSource.YFINANCE)
                logger.info("✅ yfinance数据源可用且已启用")
            except ImportError:
                logger.warning("⚠️ yfinance数据源不可用: 未安装 yfinance 库")
        else:
            logger.info("ℹ️ yfinance数据源已在数据库中禁用")

        # 检查 Alpha Vantage
        if "alpha_vantage" in enabled_sources_in_db:
            try:
                # 优先从数据库配置读取 API Key，其次从 Settings 读取
                api_key = datasource_configs.get("alpha_vantage", {}).get("api_key") or settings.ALPHA_VANTAGE_API_KEY
                if api_key:
                    available.append(USDataSource.ALPHA_VANTAGE)
                    source = "数据库配置" if datasource_configs.get("alpha_vantage", {}).get("api_key") else "环境变量"
                    logger.info(f"✅ Alpha Vantage数据源可用且已启用 (API Key来源: {source})")
                else:
                    logger.warning("⚠️ Alpha Vantage数据源不可用: API Key未配置（数据库和环境变量均未找到）")
            except Exception as e:
                logger.warning(f"⚠️ Alpha Vantage数据源检查失败: {e}")
        else:
            logger.info("ℹ️ Alpha Vantage数据源已在数据库中禁用")

        # 检查 Finnhub
        if "finnhub" in enabled_sources_in_db:
            try:
                # 优先从数据库配置读取 API Key，其次从 Settings 读取
                api_key = datasource_configs.get("finnhub", {}).get("api_key") or settings.FINNHUB_API_KEY
                if api_key:
                    available.append(USDataSource.FINNHUB)
                    source = "数据库配置" if datasource_configs.get("finnhub", {}).get("api_key") else "环境变量"
                    logger.info(f"✅ Finnhub数据源可用且已启用 (API Key来源: {source})")
                else:
                    logger.warning("⚠️ Finnhub数据源不可用: API Key未配置（数据库和环境变量均未找到）")
            except Exception as e:
                logger.warning(f"⚠️ Finnhub数据源检查失败: {e}")
        else:
            logger.info("ℹ️ Finnhub数据源已在数据库中禁用")

        return available

    def _get_enabled_sources_from_db(self) -> List[str]:
        """从数据库读取启用的数据源列表"""
        try:
            get_postgres_db_sync = getattr(importlib.import_module("app.core.database"), "get_postgres_db_sync")
            db = get_postgres_db_sync()

            # 从 datasource_groupings 集合读取
            groupings = list(db.datasource_groupings.find({"market_category_id": "us_stocks", "enabled": True}))

            # 🔥 数据源名称映射（数据库名称 → 代码中使用的名称）
            name_mapping = {
                "alpha vantage": "alpha_vantage",
                "yahoo finance": "yfinance",
                "finnhub": "finnhub",
            }

            result = []
            for g in groupings:
                db_name = g.get("data_source_name", "").lower()
                # 使用映射表转换名称
                code_name = name_mapping.get(db_name, db_name)
                result.append(code_name)
                logger.debug(f"🔄 数据源名称映射: '{db_name}' → '{code_name}'")

            return result
        except Exception as e:
            logger.warning(f"⚠️ 从数据库读取启用的数据源失败: {e}")
            # 默认全部启用
            return ["yfinance", "alpha_vantage", "finnhub"]

    def _get_datasource_configs_from_db(self) -> dict:
        """从数据库读取数据源配置（包括 API Key）"""
        try:
            get_postgres_db_sync = getattr(importlib.import_module("app.core.database"), "get_postgres_db_sync")
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

    def get_current_source(self) -> USDataSource:
        """获取当前数据源"""
        return self.current_source

    def set_current_source(self, source: USDataSource) -> bool:
        """设置当前数据源"""
        if source in self.available_sources:
            self.current_source = source
            logger.info(f"✅ 美股数据源已切换到: {source.value}")
            return True
        else:
            logger.error(f"❌ 美股数据源不可用: {source.value}")
            return False
