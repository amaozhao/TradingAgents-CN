# ruff: noqa: F401,F403,F405,F821,F722
def _openai_response_text(response: Any) -> str:
    return str(response.output[1].content[0].text)


# 导入港股工具
try:
    _hk_stock = importlib.import_module("trader.flows.providers.hk.stock")
    get_hk_stock_data = _hk_stock.get_hk_stock_data
    get_hk_stock_info = _hk_stock.get_hk_stock_info
    HK_STOCK_AVAILABLE = True
except (ImportError, AttributeError) as e:
    logger.warning(f"⚠️ 港股工具不可用: {e}")
    HK_STOCK_AVAILABLE = False


# 导入AKShare港股工具
# 注意：港股功能在 providers/hk/ 目录中
def _hk_akshare_unavailable(*args: Any, **kwargs: Any) -> None:
    return None


get_hk_stock_data_akshare: Any = _hk_akshare_unavailable
get_hk_stock_info_akshare: Any = _hk_akshare_unavailable
try:
    _hk_improved = importlib.import_module("trader.flows.providers.hk.improved")
    get_hk_stock_data_akshare = _hk_improved.get_hk_stock_data_akshare
    get_hk_stock_info_akshare = _hk_improved.get_hk_stock_info_akshare
    AKSHARE_HK_AVAILABLE = True
except (ImportError, AttributeError) as e:
    logger.warning(f"⚠️ AKShare港股工具不可用: {e}")
    AKSHARE_HK_AVAILABLE = False


# ==================== 数据源配置读取 ====================


def _get_enabled_hk_data_sources() -> list:
    """
    从数据库读取用户启用的港股数据源配置

    Returns:
        list: 按优先级排序的数据源列表，如 ['akshare', 'yfinance']
    """
    try:
        # 尝试从数据库读取配置
        get_postgres_db_sync = getattr(
            importlib.import_module("app.core.database"), "get_postgres_db_sync"
        )
        db = get_postgres_db_sync()

        # 获取最新的激活配置
        config_data = db.system_configs.find_one(
            {"is_active": True}, sort=[("version", -1)]
        )

        if config_data and config_data.get("data_source_configs"):
            data_source_configs = config_data.get("data_source_configs", [])

            # 过滤出启用的港股数据源
            enabled_sources = []
            for ds in data_source_configs:
                if not ds.get("enabled", True):
                    continue

                # 检查是否支持港股市场（支持中英文标识）
                market_categories = ds.get("market_categories", [])
                if market_categories:
                    # 支持 '港股' 或 'hk_stocks'
                    if (
                        "港股" not in market_categories
                        and "hk_stocks" not in market_categories
                    ):
                        continue

                # 映射数据源类型
                ds_type = ds.get("type", "").lower()
                if ds_type in ["akshare", "yfinance", "finnhub"]:
                    enabled_sources.append(
                        {"type": ds_type, "priority": ds.get("priority", 0)}
                    )

            # 按优先级排序（数字越大优先级越高）
            enabled_sources.sort(key=lambda x: x["priority"], reverse=True)

            result = [s["type"] for s in enabled_sources]
            if result:
                logger.info(f"✅ [港股数据源] 从数据库读取: {result}")
                return result
            else:
                logger.warning(
                    "⚠️ [港股数据源] 数据库中没有启用的港股数据源，使用默认顺序"
                )
        else:
            logger.warning("⚠️ [港股数据源] 数据库中没有配置，使用默认顺序")
    except Exception as e:
        logger.warning(f"⚠️ [港股数据源] 从数据库读取失败: {e}，使用默认顺序")

    # 回退到默认顺序
    return ["akshare", "yfinance"]


def _get_enabled_us_data_sources() -> list:
    """
    从数据库读取用户启用的美股数据源配置

    Returns:
        list: 按优先级排序的数据源列表，如 ['yfinance', 'finnhub']
    """
    try:
        # 尝试从数据库读取配置
        get_postgres_db_sync = getattr(
            importlib.import_module("app.core.database"), "get_postgres_db_sync"
        )
        db = get_postgres_db_sync()

        # 获取最新的激活配置
        config_data = db.system_configs.find_one(
            {"is_active": True}, sort=[("version", -1)]
        )

        if config_data and config_data.get("data_source_configs"):
            data_source_configs = config_data.get("data_source_configs", [])

            # 过滤出启用的美股数据源
            enabled_sources = []
            for ds in data_source_configs:
                if not ds.get("enabled", True):
                    continue

                # 检查是否支持美股市场（支持中英文标识）
                market_categories = ds.get("market_categories", [])
                if market_categories:
                    # 支持 '美股' 或 'us_stocks'
                    if (
                        "美股" not in market_categories
                        and "us_stocks" not in market_categories
                    ):
                        continue

                # 映射数据源类型
                ds_type = ds.get("type", "").lower()
                if ds_type in ["yfinance", "finnhub"]:
                    enabled_sources.append(
                        {"type": ds_type, "priority": ds.get("priority", 0)}
                    )

            # 按优先级排序（数字越大优先级越高）
            enabled_sources.sort(key=lambda x: x["priority"], reverse=True)

            result = [s["type"] for s in enabled_sources]
            if result:
                logger.info(f"✅ [美股数据源] 从数据库读取: {result}")
                return result
            else:
                logger.warning(
                    "⚠️ [美股数据源] 数据库中没有启用的美股数据源，使用默认顺序"
                )
        else:
            logger.warning("⚠️ [美股数据源] 数据库中没有配置，使用默认顺序")
    except Exception as e:
        logger.warning(f"⚠️ [美股数据源] 从数据库读取失败: {e}，使用默认顺序")

    # 回退到默认顺序
    return ["yfinance", "finnhub"]


# 尝试导入yfinance相关模块，如果失败则跳过
try:
    importlib.import_module("trader.flows.providers.us.yfinance")

    YFIN_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ yfinance工具不可用: {e}")
    YFIN_AVAILABLE = False

try:
    StockstatsUtils = getattr(
        importlib.import_module("trader.flows.technical.stats"), "StockstatsUtils"
    )
    STOCKSTATS_AVAILABLE = True
except (ImportError, AttributeError) as e:
    logger.warning(f"⚠️ stockstats工具不可用: {e}")
    StockstatsUtils = None
    STOCKSTATS_AVAILABLE = False

# 尝试导入yfinance，如果失败则设置为None
try:
    yf = importlib.import_module("yfinance")
    YF_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ yfinance库不可用: {e}")
    yf = None
    YF_AVAILABLE = False

# 获取数据目录
DATA_DIR = config_manager.get_data_dir()


def get_config():
    """获取配置（兼容性包装）"""
    return config_manager.load_settings()


def set_config(config):
    """设置配置（兼容性包装）"""
    config_manager.save_settings(config)


try:
    AlphaVantageRateLimitError = importlib.import_module(
        "trader.flows.alpha.common"
    ).AlphaVantageRateLimitError
except Exception:

    class AlphaVantageRateLimitError(Exception):
        pass


try:
    NoMarketDataError = importlib.import_module(
        "trader.flows.symbols"
    ).NoMarketDataError
except Exception:

    class NoMarketDataError(Exception):
        symbol = ""
        canonical = ""


VENDOR_METHODS = {
    "get_stock_data": {
        "alpha_vantage": lambda *args, **kwargs: __import__(
            "trader.flows.alpha.api", fromlist=["get_stock"]
        ).get_stock(*args, **kwargs),
        "yfinance": lambda *args, **kwargs: __import__(
            "trader.flows.yfinance.legacy", fromlist=["get_yfin_data_online"]
        ).get_yfin_data_online(*args, **kwargs),
    },
    "get_indicators": {
        "alpha_vantage": lambda *args, **kwargs: __import__(
            "trader.flows.alpha.api", fromlist=["get_indicator"]
        ).get_indicator(*args, **kwargs),
        "yfinance": lambda *args, **kwargs: __import__(
            "trader.flows.yfinance.legacy",
            fromlist=["get_stock_stats_indicators_window"],
        ).get_stock_stats_indicators_window(*args, **kwargs),
    },
    "get_fundamentals": {
        "alpha_vantage": lambda *args, **kwargs: __import__(
            "trader.flows.alpha.api", fromlist=["get_fundamentals"]
        ).get_fundamentals(*args, **kwargs),
        "yfinance": lambda *args, **kwargs: __import__(
            "trader.flows.yfinance.legacy", fromlist=["get_fundamentals"]
        ).get_fundamentals(*args, **kwargs),
    },
    "get_news": {
        "alpha_vantage": lambda *args, **kwargs: __import__(
            "trader.flows.alpha.api", fromlist=["get_news"]
        ).get_news(*args, **kwargs),
        "yfinance": lambda *args, **kwargs: __import__(
            "trader.flows.yfinance.news", fromlist=["get_news_yfinance"]
        ).get_news_yfinance(*args, **kwargs),
    },
    "get_global_news": {
        "alpha_vantage": lambda *args, **kwargs: __import__(
            "trader.flows.alpha.api", fromlist=["get_global_news"]
        ).get_global_news(*args, **kwargs),
        "yfinance": lambda *args, **kwargs: __import__(
            "trader.flows.yfinance.news", fromlist=["get_global_news_yfinance"]
        ).get_global_news_yfinance(*args, **kwargs),
    },
    "get_insider_transactions": {
        "alpha_vantage": lambda *args, **kwargs: __import__(
            "trader.flows.alpha.api", fromlist=["get_insider_transactions"]
        ).get_insider_transactions(*args, **kwargs),
        "yfinance": lambda *args, **kwargs: __import__(
            "trader.flows.yfinance.legacy", fromlist=["get_insider_transactions"]
        ).get_insider_transactions(*args, **kwargs),
    },
}
