# ruff: noqa: F401,F403,F405,F821
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    setup_logging()
    logger = logging.getLogger("app.main")

    # 验证启动配置
    try:
        validate_startup_config = getattr(
            importlib.import_module("app.core.startup"), "validate_startup_config"
        )
        validate_startup_config()
    except Exception as e:
        logger.error(f"配置验证失败: {e}")
        raise

    await init_db()

    #  配置桥接：将统一配置写入环境变量，供 AGENTrader 核心库使用
    try:
        bridge_config_to_env = getattr(
            importlib.import_module("app.core.bridge"), "bridge_config_to_env"
        )
        bridge_config_to_env()
    except Exception as e:
        logger.warning(f"⚠️  配置桥接失败: {e}")
        logger.warning("⚠️  AGENTrader 将使用 .env 文件中的配置")

    # Apply dynamic settings (log_level, enable_monitoring) from ConfigProvider
    try:
        config_provider = getattr(
            importlib.import_module("app.services.provider"), "provider"
        )
        eff = await config_provider.get_effective_system_settings()
        desired_level = str(eff.get("log_level", "INFO")).upper()
        setup_logging(log_level=desired_level)
        for name in ("webapi", "worker", "uvicorn", "fastapi"):
            logging.getLogger(name).setLevel(desired_level)
        try:
            set_operation_log_enabled = getattr(
                importlib.import_module("app.middleware.operations"),
                "set_operation_log_enabled",
            )
            set_operation_log_enabled(bool(eff.get("enable_monitoring", True)))
        except Exception:
            pass
    except Exception as e:
        logging.getLogger("webapi").warning(f"Failed to apply dynamic settings: {e}")

    # 显示配置摘要
    await _print_config_summary(logger)

    logger.info("AGENTrader FastAPI backend started")

    # 启动期：若需要在休市时补充上一交易日收盘快照
    if settings.QUOTES_BACKFILL_ON_STARTUP:
        try:
            qi = QuotesIngestionService()
            await qi.ensure_indexes()
            await qi.backfill_last_close_snapshot_if_needed()
        except Exception as e:
            logger.warning(f"Startup backfill failed (ignored): {e}")

    # 启动每日定时任务：可配置
    scheduler: AsyncIOScheduler | None = None
    try:
        scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)

        # 使用多数据源同步服务（支持自动切换）
        multi_source_service = get_multi_source_sync_service()

        # 根据 TUSHARE_ENABLED 配置决定优先数据源
        # 如果 Tushare 被禁用，系统会自动使用其他可用数据源（AKShare/BaoStock）
        preferred_sources = None  # None 表示使用默认优先级顺序

        if settings.TUSHARE_ENABLED:
            # Tushare 启用时，优先使用 Tushare
            preferred_sources = ["tushare", "akshare", "baostock"]
            logger.info("📊 股票基础信息同步优先数据源: Tushare > AKShare > BaoStock")
        else:
            # Tushare 禁用时，使用 AKShare 和 BaoStock
            preferred_sources = ["akshare", "baostock"]
            logger.info(
                "📊 股票基础信息同步优先数据源: AKShare > BaoStock (Tushare已禁用)"
            )

        # 配置调度：优先使用 CRON，其次使用 HH:MM
        if settings.SYNC_STOCK_BASICS_ENABLED:
            # 立即在启动后尝试一次（不阻塞）
            async def run_sync_with_sources():
                await multi_source_service.run_full_sync(
                    force=False, preferred_sources=preferred_sources
                )

            asyncio.create_task(run_sync_with_sources())

            if settings.SYNC_STOCK_BASICS_CRON:
                # 如果提供了cron表达式
                scheduler.add_job(
                    run_sync_with_sources,
                    CronTrigger.from_crontab(
                        settings.SYNC_STOCK_BASICS_CRON, timezone=settings.TIMEZONE
                    ),
                    id="basics_sync_service",
                    name="股票基础信息同步（多数据源）",
                )
                logger.info(
                    f"📅 Stock basics sync scheduled by CRON: {settings.SYNC_STOCK_BASICS_CRON} ({settings.TIMEZONE})"
                )
            else:
                hh, mm = (settings.SYNC_STOCK_BASICS_TIME or "06:30").split(":")
                scheduler.add_job(
                    run_sync_with_sources,
                    CronTrigger(
                        hour=int(hh), minute=int(mm), timezone=settings.TIMEZONE
                    ),
                    id="basics_sync_service",
                    name="股票基础信息同步（多数据源）",
                )
                logger.info(
                    f"📅 Stock basics sync scheduled daily at {settings.SYNC_STOCK_BASICS_TIME} ({settings.TIMEZONE})"
                )
        else:
            logger.info("⏸️ 股票基础信息启动同步已禁用: SYNC_STOCK_BASICS_ENABLED=false")

        # 实时行情入库任务（每N秒），内部自判交易时段
        if settings.QUOTES_INGEST_ENABLED:
            quotes_ingestion = QuotesIngestionService()
            await quotes_ingestion.ensure_indexes()

            async def run_quotes_ingestion_tick():
                await quotes_ingestion.run_once()

            scheduler.add_job(
                run_quotes_ingestion_tick,
                IntervalTrigger(
                    seconds=settings.QUOTES_INGEST_INTERVAL_SECONDS,
                    timezone=settings.TIMEZONE,
                ),
                id="quotes_ingestion_service",
                name="实时行情入库服务",
            )
            logger.info(
                f"⏱ 实时行情入库任务已启动: 每 {settings.QUOTES_INGEST_INTERVAL_SECONDS}s"
            )

        # Tushare统一数据同步任务配置
        logger.info("🔄 配置Tushare统一数据同步任务...")

        # 基础信息同步任务
        scheduler.add_job(
            run_tushare_basic_info_sync,
            CronTrigger.from_crontab(
                settings.TUSHARE_BASIC_INFO_SYNC_CRON, timezone=settings.TIMEZONE
            ),
            id="tushare_basic_info_sync",
            name="股票基础信息同步（Tushare）",
            kwargs={"force_update": False},
        )
        if not (
            settings.TUSHARE_UNIFIED_ENABLED
            and settings.TUSHARE_BASIC_INFO_SYNC_ENABLED
        ):
            scheduler.pause_job("tushare_basic_info_sync")
            logger.info(
                f"⏸️ Tushare基础信息同步已添加但暂停: {settings.TUSHARE_BASIC_INFO_SYNC_CRON}"
            )
        else:
            logger.info(
                f"📅 Tushare基础信息同步已配置: {settings.TUSHARE_BASIC_INFO_SYNC_CRON}"
            )

        # 实时行情同步任务
        scheduler.add_job(
            run_tushare_quotes_sync,
            CronTrigger.from_crontab(
                settings.TUSHARE_QUOTES_SYNC_CRON, timezone=settings.TIMEZONE
            ),
            id="tushare_quotes_sync",
            name="实时行情同步（Tushare）",
        )
        if not (
            settings.TUSHARE_UNIFIED_ENABLED and settings.TUSHARE_QUOTES_SYNC_ENABLED
        ):
            scheduler.pause_job("tushare_quotes_sync")
            logger.info(
                f"⏸️ Tushare行情同步已添加但暂停: {settings.TUSHARE_QUOTES_SYNC_CRON}"
            )
        else:
            logger.info(
                f"📈 Tushare行情同步已配置: {settings.TUSHARE_QUOTES_SYNC_CRON}"
            )

        # 历史数据同步任务
        scheduler.add_job(
            run_tushare_historical_sync,
            CronTrigger.from_crontab(
                settings.TUSHARE_HISTORICAL_SYNC_CRON, timezone=settings.TIMEZONE
            ),
            id="tushare_historical_sync",
            name="历史数据同步（Tushare）",
            kwargs={"incremental": True},
        )
        if not (
            settings.TUSHARE_UNIFIED_ENABLED
            and settings.TUSHARE_HISTORICAL_SYNC_ENABLED
        ):
            scheduler.pause_job("tushare_historical_sync")
            logger.info(
                f"⏸️ Tushare历史数据同步已添加但暂停: {settings.TUSHARE_HISTORICAL_SYNC_CRON}"
            )
        else:
            logger.info(
                f"📊 Tushare历史数据同步已配置: {settings.TUSHARE_HISTORICAL_SYNC_CRON}"
            )

        # 财务数据同步任务
        scheduler.add_job(
            run_tushare_financial_sync,
            CronTrigger.from_crontab(
                settings.TUSHARE_FINANCIAL_SYNC_CRON, timezone=settings.TIMEZONE
            ),
            id="tushare_financial_sync",
            name="财务数据同步（Tushare）",
        )
        if not (
            settings.TUSHARE_UNIFIED_ENABLED and settings.TUSHARE_FINANCIAL_SYNC_ENABLED
        ):
            scheduler.pause_job("tushare_financial_sync")
            logger.info(
                f"⏸️ Tushare财务数据同步已添加但暂停: {settings.TUSHARE_FINANCIAL_SYNC_CRON}"
            )
        else:
            logger.info(
                f"💰 Tushare财务数据同步已配置: {settings.TUSHARE_FINANCIAL_SYNC_CRON}"
            )

        # 状态检查任务
        scheduler.add_job(
            run_tushare_status_check,
            CronTrigger.from_crontab(
                settings.TUSHARE_STATUS_CHECK_CRON, timezone=settings.TIMEZONE
            ),
            id="tushare_status_check",
            name="数据源状态检查（Tushare）",
        )
        if not (
            settings.TUSHARE_UNIFIED_ENABLED and settings.TUSHARE_STATUS_CHECK_ENABLED
        ):
            scheduler.pause_job("tushare_status_check")
            logger.info(
                f"⏸️ Tushare状态检查已添加但暂停: {settings.TUSHARE_STATUS_CHECK_CRON}"
            )
        else:
            logger.info(
                f"🔍 Tushare状态检查已配置: {settings.TUSHARE_STATUS_CHECK_CRON}"
            )

        # AKShare统一数据同步任务配置
        logger.info("🔄 配置AKShare统一数据同步任务...")

        # 基础信息同步任务
        scheduler.add_job(
            run_akshare_basic_info_sync,
            CronTrigger.from_crontab(
                settings.AKSHARE_BASIC_INFO_SYNC_CRON, timezone=settings.TIMEZONE
            ),
            id="akshare_basic_info_sync",
            name="股票基础信息同步（AKShare）",
            kwargs={"force_update": False},
        )
        if not (
            settings.AKSHARE_UNIFIED_ENABLED
            and settings.AKSHARE_BASIC_INFO_SYNC_ENABLED
        ):
            scheduler.pause_job("akshare_basic_info_sync")
            logger.info(
                f"⏸️ AKShare基础信息同步已添加但暂停: {settings.AKSHARE_BASIC_INFO_SYNC_CRON}"
            )
        else:
            logger.info(
                f"📅 AKShare基础信息同步已配置: {settings.AKSHARE_BASIC_INFO_SYNC_CRON}"
            )

        # 实时行情同步任务
        scheduler.add_job(
            run_akshare_quotes_sync,
            CronTrigger.from_crontab(
                settings.AKSHARE_QUOTES_SYNC_CRON, timezone=settings.TIMEZONE
            ),
            id="akshare_quotes_sync",
            name="实时行情同步（AKShare）",
        )
        if not (
            settings.AKSHARE_UNIFIED_ENABLED and settings.AKSHARE_QUOTES_SYNC_ENABLED
        ):
            scheduler.pause_job("akshare_quotes_sync")
            logger.info(
                f"⏸️ AKShare行情同步已添加但暂停: {settings.AKSHARE_QUOTES_SYNC_CRON}"
            )
        else:
            logger.info(
                f"📈 AKShare行情同步已配置: {settings.AKSHARE_QUOTES_SYNC_CRON}"
            )

        # 历史数据同步任务
        scheduler.add_job(
            run_akshare_historical_sync,
            CronTrigger.from_crontab(
                settings.AKSHARE_HISTORICAL_SYNC_CRON, timezone=settings.TIMEZONE
            ),
            id="akshare_historical_sync",
            name="历史数据同步（AKShare）",
            kwargs={"incremental": True},
        )
        if not (
            settings.AKSHARE_UNIFIED_ENABLED
            and settings.AKSHARE_HISTORICAL_SYNC_ENABLED
        ):
            scheduler.pause_job("akshare_historical_sync")
            logger.info(
                f"⏸️ AKShare历史数据同步已添加但暂停: {settings.AKSHARE_HISTORICAL_SYNC_CRON}"
            )
        else:
            logger.info(
                f"📊 AKShare历史数据同步已配置: {settings.AKSHARE_HISTORICAL_SYNC_CRON}"
            )

        # 财务数据同步任务
        scheduler.add_job(
            run_akshare_financial_sync,
            CronTrigger.from_crontab(
                settings.AKSHARE_FINANCIAL_SYNC_CRON, timezone=settings.TIMEZONE
            ),
            id="akshare_financial_sync",
            name="财务数据同步（AKShare）",
        )
        if not (
            settings.AKSHARE_UNIFIED_ENABLED and settings.AKSHARE_FINANCIAL_SYNC_ENABLED
        ):
            scheduler.pause_job("akshare_financial_sync")
            logger.info(
                f"⏸️ AKShare财务数据同步已添加但暂停: {settings.AKSHARE_FINANCIAL_SYNC_CRON}"
            )
        else:
            logger.info(
                f"💰 AKShare财务数据同步已配置: {settings.AKSHARE_FINANCIAL_SYNC_CRON}"
            )

        # 状态检查任务
        scheduler.add_job(
            run_akshare_status_check,
            CronTrigger.from_crontab(
                settings.AKSHARE_STATUS_CHECK_CRON, timezone=settings.TIMEZONE
            ),
            id="akshare_status_check",
            name="数据源状态检查（AKShare）",
        )
        if not (
            settings.AKSHARE_UNIFIED_ENABLED and settings.AKSHARE_STATUS_CHECK_ENABLED
        ):
            scheduler.pause_job("akshare_status_check")
            logger.info(
                f"⏸️ AKShare状态检查已添加但暂停: {settings.AKSHARE_STATUS_CHECK_CRON}"
            )
        else:
            logger.info(
                f"🔍 AKShare状态检查已配置: {settings.AKSHARE_STATUS_CHECK_CRON}"
            )

        # BaoStock统一数据同步任务配置
        logger.info("🔄 配置BaoStock统一数据同步任务...")

        # 基础信息同步任务
        scheduler.add_job(
            run_baostock_basic_info_sync,
            CronTrigger.from_crontab(
                settings.BAOSTOCK_BASIC_INFO_SYNC_CRON, timezone=settings.TIMEZONE
            ),
            id="baostock_basic_info_sync",
            name="股票基础信息同步（BaoStock）",
        )
        if not (
            settings.BAOSTOCK_UNIFIED_ENABLED
            and settings.BAOSTOCK_BASIC_INFO_SYNC_ENABLED
        ):
            scheduler.pause_job("baostock_basic_info_sync")
            logger.info(
                f"⏸️ BaoStock基础信息同步已添加但暂停: {settings.BAOSTOCK_BASIC_INFO_SYNC_CRON}"
            )
        else:
            logger.info(
                f"📋 BaoStock基础信息同步已配置: {settings.BAOSTOCK_BASIC_INFO_SYNC_CRON}"
            )

        # 日K线同步任务（注意：BaoStock不支持实时行情）
        scheduler.add_job(
            run_baostock_daily_quotes_sync,
            CronTrigger.from_crontab(
                settings.BAOSTOCK_DAILY_QUOTES_SYNC_CRON, timezone=settings.TIMEZONE
            ),
            id="baostock_daily_quotes_sync",
            name="日K线数据同步（BaoStock）",
        )
        if not (
            settings.BAOSTOCK_UNIFIED_ENABLED
            and settings.BAOSTOCK_DAILY_QUOTES_SYNC_ENABLED
        ):
            scheduler.pause_job("baostock_daily_quotes_sync")
            logger.info(
                f"⏸️ BaoStock日K线同步已添加但暂停: {settings.BAOSTOCK_DAILY_QUOTES_SYNC_CRON}"
            )
        else:
            logger.info(
                f"📈 BaoStock日K线同步已配置: {settings.BAOSTOCK_DAILY_QUOTES_SYNC_CRON} (注意：BaoStock不支持实时行情)"
            )

        # 历史数据同步任务
        scheduler.add_job(
            run_baostock_historical_sync,
            CronTrigger.from_crontab(
                settings.BAOSTOCK_HISTORICAL_SYNC_CRON, timezone=settings.TIMEZONE
            ),
            id="baostock_historical_sync",
            name="历史数据同步（BaoStock）",
        )
        if not (
            settings.BAOSTOCK_UNIFIED_ENABLED
            and settings.BAOSTOCK_HISTORICAL_SYNC_ENABLED
        ):
            scheduler.pause_job("baostock_historical_sync")
            logger.info(
                f"⏸️ BaoStock历史数据同步已添加但暂停: {settings.BAOSTOCK_HISTORICAL_SYNC_CRON}"
            )
        else:
            logger.info(
                f"📊 BaoStock历史数据同步已配置: {settings.BAOSTOCK_HISTORICAL_SYNC_CRON}"
            )

        # 状态检查任务
        scheduler.add_job(
            run_baostock_status_check,
            CronTrigger.from_crontab(
                settings.BAOSTOCK_STATUS_CHECK_CRON, timezone=settings.TIMEZONE
            ),
            id="baostock_status_check",
            name="数据源状态检查（BaoStock）",
        )
        if not (
            settings.BAOSTOCK_UNIFIED_ENABLED and settings.BAOSTOCK_STATUS_CHECK_ENABLED
        ):
            scheduler.pause_job("baostock_status_check")
            logger.info(
                f"⏸️ BaoStock状态检查已添加但暂停: {settings.BAOSTOCK_STATUS_CHECK_CRON}"
            )
        else:
            logger.info(
                f"🔍 BaoStock状态检查已配置: {settings.BAOSTOCK_STATUS_CHECK_CRON}"
            )

        # 新闻数据同步任务配置（使用AKShare同步所有股票新闻）
        logger.info("🔄 配置新闻数据同步任务...")

        get_akshare_sync_service = getattr(
            importlib.import_module("app.worker.akshare.sync"),
            "get_akshare_sync_service",
        )

        async def run_news_sync():
            """运行新闻同步任务 - 使用AKShare同步自选股新闻"""
            try:
                logger.info("📰 开始新闻数据同步（AKShare - 仅自选股）...")
                service = await get_akshare_sync_service()
                result = await service.sync_news_data(
                    symbols=None,  # None + favorites_only=True 表示只同步自选股
                    max_news_per_stock=settings.NEWS_SYNC_MAX_PER_SOURCE,
                    favorites_only=True,  # 只同步自选股
                )
                logger.info(
                    f"✅ 新闻同步完成: "
                    f"处理{result['total_processed']}只自选股, "
                    f"成功{result['success_count']}只, "
                    f"失败{result['error_count']}只, "
                    f"新闻总数{result['news_count']}条, "
                    f"耗时{(datetime.utcnow() - result['start_time']).total_seconds():.2f}秒"
                )
            except Exception as e:
                logger.error(f"❌ 新闻同步失败: {e}", exc_info=True)

        # ==================== 港股/美股数据配置 ====================
        # 港股和美股采用按需获取+缓存模式，不再配置定时同步任务
        logger.info("🇭🇰 港股数据采用按需获取+缓存模式")
        logger.info("🇺🇸 美股数据采用按需获取+缓存模式")

        scheduler.add_job(
            run_news_sync,
            CronTrigger.from_crontab(
                settings.NEWS_SYNC_CRON, timezone=settings.TIMEZONE
            ),
            id="news_sync",
            name="新闻数据同步（AKShare - 仅自选股）",
        )
        if not settings.NEWS_SYNC_ENABLED:
            scheduler.pause_job("news_sync")
            logger.info(f"⏸️ 新闻数据同步已添加但暂停: {settings.NEWS_SYNC_CRON}")
        else:
            logger.info(f"📰 新闻数据同步已配置（仅自选股）: {settings.NEWS_SYNC_CRON}")

        scheduler.start()

        # 设置调度器实例到服务中，以便API可以管理任务
        set_scheduler_instance(scheduler)
        logger.info("✅ 调度器服务已初始化")
    except Exception as e:
        logger.error(f"❌ 调度器启动失败: {e}", exc_info=True)
        raise  # 抛出异常，阻止应用启动

    try:
        yield
    finally:
        # 关闭时清理
        if scheduler:
            try:
                scheduler.shutdown(wait=False)
                logger.info("🛑 Scheduler stopped")
            except Exception as e:
                logger.warning(f"Scheduler shutdown error: {e}")

        # 释放 UserService 文档存储连接
        try:
            user_service = getattr(
                importlib.import_module("app.services.user"), "user_service"
            )
            user_service.close()
        except Exception as e:
            logger.warning(f"UserService cleanup error: {e}")

        await close_db()
        logger.info("AGENTrader FastAPI backend stopped")


# 创建FastAPI应用
app = FastAPI(
    title="AGENTrader API",
    description="股票分析与批量队列系统 API",
    version=get_version(),
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# 安全中间件
if not settings.DEBUG:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# 操作日志中间件
app.add_middleware(OperationLogMiddleware)


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    # 跳过健康检查和静态文件请求的日志
    if request.url.path in ["/health", "/favicon.ico"] or request.url.path.startswith(
        "/static"
    ):
        response = await call_next(request)
        return response

    # 使用webapi logger记录请求
    logger = logging.getLogger("webapi")
    logger.info(f"🔄 {request.method} {request.url.path} - 开始处理")

    response = await call_next(request)
    process_time = time.time() - start_time

    # 记录请求完成
    status_emoji = "✅" if response.status_code < 400 else "❌"
    logger.info(
        f"{status_emoji} {request.method} {request.url.path} - 状态: {response.status_code} - 耗时: {process_time:.3f}s"
    )

    return response


# 请求ID/Trace-ID 中间件（需作为最外层，放在函数式中间件之后）
app.add_middleware(RequestIDMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Internal server error occurred",
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


# 测试端点 - 验证中间件是否工作
@app.get("/api/test-log", response_model=TestLogResponse)
async def test_log():
    """测试日志中间件是否工作"""
    print("🧪 测试端点被调用 - 这条消息应该出现在控制台")
    return {"message": "测试成功", "timestamp": time.time()}


# 注册路由
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(reports.router, tags=["reports"])
app.include_router(screening.router, prefix="/api/screening", tags=["screening"])
app.include_router(queue.router, prefix="/api/queue", tags=["queue"])
app.include_router(favorites.router, prefix="/api", tags=["favorites"])
app.include_router(stocks_router.router, prefix="/api", tags=["stocks"])
app.include_router(
    multi_market_stocks_router.router, prefix="/api", tags=["multi-market"]
)
app.include_router(stock_data_router.router, tags=["stock-data"])
app.include_router(stock_sync_router.router, tags=["stock-sync"])
app.include_router(tags.router, prefix="/api", tags=["tags"])
app.include_router(config.router, prefix="/api", tags=["config"])
app.include_router(model_capabilities.router, tags=["model-capabilities"])
app.include_router(usage_statistics.router, tags=["usage-statistics"])
app.include_router(database.router, prefix="/api/system", tags=["database"])
app.include_router(cache.router, tags=["cache"])
app.include_router(operations.router, prefix="/api/system", tags=["operations"])
app.include_router(logs.router, prefix="/api/system", tags=["logs"])
# 新增：系统配置只读摘要
app.include_router(system_config_router.router, prefix="/api/system", tags=["system"])

# 通知模块（REST + SSE）
app.include_router(notifications_router.router, prefix="/api", tags=["notifications"])

# 🔥 WebSocket 通知模块（替代 SSE + Redis PubSub）
app.include_router(
    websocket_notifications_router.router, prefix="/api", tags=["websocket"]
)

# 定时任务管理
app.include_router(scheduler_router.router, tags=["scheduler"])

app.include_router(sse.router, prefix="/api/stream", tags=["streaming"])
app.include_router(sync_router.router)
app.include_router(multi_source_sync.router)
app.include_router(paper_router.router, prefix="/api", tags=["paper"])
app.include_router(tushare_init.router, prefix="/api", tags=["tushare-init"])
app.include_router(akshare_init.router, prefix="/api", tags=["akshare-init"])
app.include_router(baostock_init.router, prefix="/api", tags=["baostock-init"])
app.include_router(historical_data.router, tags=["historical-data"])
app.include_router(multi_period_sync.router, tags=["multi-period-sync"])
app.include_router(financial_data.router, tags=["financial-data"])
app.include_router(news_data.router, tags=["news-data"])
app.include_router(social_media.router, tags=["social-media"])
app.include_router(internal_messages.router, tags=["internal-messages"])


@app.get("/", response_model=RootResponse)
async def root():
    """根路径，返回API信息"""
    print("🏠 根路径被访问")
    return {
        "name": "AGENTrader API",
        "version": get_version(),
        "status": "running",
        "docs_url": "/docs" if settings.DEBUG else None,
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
        reload_dirs=["app"] if settings.DEBUG else None,
        reload_excludes=[
            "__pycache__",
            "*.pyc",
            "*.pyo",
            "*.pyd",
            ".git",
            ".pytest_cache",
            "*.log",
            "*.tmp",
        ]
        if settings.DEBUG
        else None,
        reload_includes=["*.py"] if settings.DEBUG else None,
    )
