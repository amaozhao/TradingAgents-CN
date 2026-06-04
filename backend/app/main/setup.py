# ruff: noqa: F401,F403,F405,F821
class TestLogResponse(BaseModel):
    message: str
    timestamp: float


class RootResponse(BaseModel):
    name: str
    version: str
    status: str
    docs_url: str | None = None


async def run_tushare_basic_info_sync(*args, **kwargs):
    _run = getattr(
        importlib.import_module("app.worker.tushare.sync"),
        "run_tushare_basic_info_sync",
    )

    return await _run(*args, **kwargs)


async def run_tushare_quotes_sync(*args, **kwargs):
    _run = getattr(
        importlib.import_module("app.worker.tushare.sync"), "run_tushare_quotes_sync"
    )

    return await _run(*args, **kwargs)


async def run_tushare_historical_sync(*args, **kwargs):
    _run = getattr(
        importlib.import_module("app.worker.tushare.sync"),
        "run_tushare_historical_sync",
    )

    return await _run(*args, **kwargs)


async def run_tushare_financial_sync(*args, **kwargs):
    _run = getattr(
        importlib.import_module("app.worker.tushare.sync"), "run_tushare_financial_sync"
    )

    return await _run(*args, **kwargs)


async def run_tushare_status_check(*args, **kwargs):
    _run = getattr(
        importlib.import_module("app.worker.tushare.sync"), "run_tushare_status_check"
    )

    return await _run(*args, **kwargs)


async def run_akshare_basic_info_sync(*args, **kwargs):
    _run = getattr(
        importlib.import_module("app.worker.akshare.sync"),
        "run_akshare_basic_info_sync",
    )

    return await _run(*args, **kwargs)


async def run_akshare_quotes_sync(*args, **kwargs):
    _run = getattr(
        importlib.import_module("app.worker.akshare.sync"), "run_akshare_quotes_sync"
    )

    return await _run(*args, **kwargs)


async def run_akshare_historical_sync(*args, **kwargs):
    _run = getattr(
        importlib.import_module("app.worker.akshare.sync"),
        "run_akshare_historical_sync",
    )

    return await _run(*args, **kwargs)


async def run_akshare_financial_sync(*args, **kwargs):
    _run = getattr(
        importlib.import_module("app.worker.akshare.sync"), "run_akshare_financial_sync"
    )

    return await _run(*args, **kwargs)


async def run_akshare_status_check(*args, **kwargs):
    _run = getattr(
        importlib.import_module("app.worker.akshare.sync"), "run_akshare_status_check"
    )

    return await _run(*args, **kwargs)


async def run_baostock_basic_info_sync(*args, **kwargs):
    _run = getattr(
        importlib.import_module("app.worker.baostock.sync"),
        "run_baostock_basic_info_sync",
    )

    return await _run(*args, **kwargs)


async def run_baostock_daily_quotes_sync(*args, **kwargs):
    _run = getattr(
        importlib.import_module("app.worker.baostock.sync"),
        "run_baostock_daily_quotes_sync",
    )

    return await _run(*args, **kwargs)


async def run_baostock_historical_sync(*args, **kwargs):
    _run = getattr(
        importlib.import_module("app.worker.baostock.sync"),
        "run_baostock_historical_sync",
    )

    return await _run(*args, **kwargs)


async def run_baostock_status_check(*args, **kwargs):
    _run = getattr(
        importlib.import_module("app.worker.baostock.sync"), "run_baostock_status_check"
    )

    return await _run(*args, **kwargs)


def get_version() -> str:
    """从 VERSION 文件读取版本号"""
    try:
        for root in (
            Path(__file__).resolve().parents[2],
            Path(__file__).resolve().parent.parent,
        ):
            version_file = root / "VERSION"
            if version_file.exists():
                return version_file.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return "1.0.0"  # 默认版本号


async def _print_config_summary(logger):
    """显示配置摘要"""
    try:
        logger.info("=" * 70)
        logger.info("📋 TradingAgents-CN Configuration Summary")
        logger.info("=" * 70)

        # .env 文件路径信息
        os = importlib.import_module("os")
        Path = getattr(importlib.import_module("pathlib"), "Path")

        current_dir = Path.cwd()
        logger.info(f"📁 Current working directory: {current_dir}")

        # 检查可能的 .env 文件位置
        env_files_to_check = [
            current_dir / ".env",
            current_dir / "backend" / ".env",
            Path(__file__).resolve().parents[2] / ".env",  # 项目根目录
            Path(__file__).resolve().parent.parent / ".env",  # backend 目录
        ]

        logger.info("🔍 Checking .env file locations:")
        env_file_found = False
        for env_file in env_files_to_check:
            if env_file.exists():
                logger.info(
                    f"  ✅ Found: {env_file} (size: {env_file.stat().st_size} bytes)"
                )
                env_file_found = True
                # 显示文件的前几行（隐藏敏感信息）
                try:
                    with open(env_file, "r", encoding="utf-8") as f:
                        lines = f.readlines()[:5]  # 只读前5行
                        logger.info("     Preview (first 5 lines):")
                        for i, line in enumerate(lines, 1):
                            # 隐藏包含密码、密钥等敏感信息的行
                            if any(
                                keyword in line.upper()
                                for keyword in ["PASSWORD", "SECRET", "KEY", "TOKEN"]
                            ):
                                logger.info(f"       {i}: {line.split('=')[0]}=***")
                            else:
                                logger.info(f"       {i}: {line.strip()}")
                except Exception as e:
                    logger.warning(f"     Could not preview file: {e}")
            else:
                logger.info(f"  ❌ Not found: {env_file}")

        if not env_file_found:
            logger.warning("⚠️  No .env file found in checked locations")

        # Pydantic Settings 配置加载状态
        logger.info("⚙️  Pydantic Settings Configuration:")
        logger.info(f"  • Settings class: {settings.__class__.__name__}")
        logger.info(
            f"  • Config source: {getattr(settings.model_config, 'env_file', 'Not specified')}"
        )
        logger.info(
            f"  • Encoding: {getattr(settings.model_config, 'env_file_encoding', 'Not specified')}"
        )

        # 显示一些关键配置值的来源（环境变量 vs 默认值）
        key_settings = ["HOST", "PORT", "DEBUG", "POSTGRES_HOST", "REDIS_HOST"]
        logger.info("  • Key settings sources:")
        for setting_name in key_settings:
            env_var_name = setting_name
            env_value = os.getenv(env_var_name)
            config_value = getattr(settings, setting_name, None)
            if env_value is not None:
                logger.info(
                    f"    - {setting_name}: from environment variable ({config_value})"
                )
            else:
                logger.info(
                    f"    - {setting_name}: using default value ({config_value})"
                )

        # 环境信息
        env = "Production" if settings.is_production else "Development"
        logger.info(f"Environment: {env}")

        # 数据库连接
        logger.info(
            f"PostgreSQL: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
        )
        logger.info(
            f"Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
        )

        # 代理配置
        os = importlib.import_module("os")
        if settings.HTTP_PROXY or settings.HTTPS_PROXY:
            logger.info("Proxy Configuration:")
            if settings.HTTP_PROXY:
                logger.info(f"  HTTP_PROXY: {settings.HTTP_PROXY}")
            if settings.HTTPS_PROXY:
                logger.info(f"  HTTPS_PROXY: {settings.HTTPS_PROXY}")
            if settings.NO_PROXY:
                # 只显示前3个域名
                no_proxy_list = settings.NO_PROXY.split(",")
                if len(no_proxy_list) <= 3:
                    logger.info(f"  NO_PROXY: {settings.NO_PROXY}")
                else:
                    logger.info(
                        f"  NO_PROXY: {','.join(no_proxy_list[:3])}... ({len(no_proxy_list)} domains)"
                    )
            logger.info("  ✅ Proxy environment variables set successfully")
        else:
            logger.info("Proxy: Not configured (direct connection)")

        # 检查大模型配置
        try:
            config_service = getattr(
                importlib.import_module("app.services.config"), "config_service"
            )
            config = await config_service.get_system_config()
            if config and config.llm_configs:
                enabled_llms = [llm for llm in config.llm_configs if llm.enabled]
                logger.info(f"Enabled LLMs: {len(enabled_llms)}")
                if enabled_llms:
                    for llm in enabled_llms[:3]:  # 只显示前3个
                        logger.info(f"  • {llm.provider}: {llm.model_name}")
                    if len(enabled_llms) > 3:
                        logger.info(f"  • ... and {len(enabled_llms) - 3} more")
                else:
                    logger.warning(
                        "⚠️  No LLM enabled. Please configure at least one LLM in Web UI."
                    )
            else:
                logger.warning(
                    "⚠️  No LLM configured. Please configure at least one LLM in Web UI."
                )
        except Exception as e:
            logger.warning(f"⚠️  Failed to check LLM configs: {e}")

        # 检查数据源配置
        try:
            if config and config.data_source_configs:
                enabled_sources = [
                    ds for ds in config.data_source_configs if ds.enabled
                ]
                logger.info(f"Enabled Data Sources: {len(enabled_sources)}")
                if enabled_sources:
                    for ds in enabled_sources[:3]:  # 只显示前3个
                        logger.info(f"  • {ds.type.value}: {ds.name}")
                    if len(enabled_sources) > 3:
                        logger.info(f"  • ... and {len(enabled_sources) - 3} more")
            else:
                logger.info("Data Sources: Using default (AKShare)")
        except Exception as e:
            logger.warning(f"⚠️  Failed to check data source configs: {e}")

        logger.info("=" * 70)
    except Exception as e:
        logger.error(f"Failed to print config summary: {e}")
