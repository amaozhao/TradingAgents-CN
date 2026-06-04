# ruff: noqa: F401,F403,F405,F821
@router.get("/{code}/news", response_model=ApiResponse)
async def get_news(
    code: str,
    days: int = 30,
    limit: int = 50,
    include_announcements: bool = True,
    current_user: dict = Depends(get_current_user),
):
    """获取新闻与公告（支持A股、港股、美股）"""
    ForeignStockService = getattr(
        importlib.import_module("app.services.stocks.foreign"), "ForeignStockService"
    )
    get_news_data_service = getattr(
        importlib.import_module("app.services.market.news"), "get_news_data_service"
    )
    NewsQueryParams = getattr(
        importlib.import_module("app.services.market.news"), "NewsQueryParams"
    )

    # 检测股票类型
    market, normalized_code = _detect_market_and_code(code)

    if market == "US":
        # 美股：使用 ForeignStockService
        service = ForeignStockService()
        result = await service.get_us_news(normalized_code, days=days, limit=limit)
        return ok(result)
    elif market == "HK":
        # 港股：暂时返回空数据（TODO: 实现港股新闻）
        data = {
            "code": normalized_code,
            "days": days,
            "limit": limit,
            "source": "none",
            "items": [],
        }
        return ok(data)
    else:
        # A股：直接调用同步服务的查询方法（包含智能回退逻辑）
        try:
            logger.info("=" * 80)
            logger.info(
                f"📰 开始获取新闻: code={code}, normalized_code={normalized_code}, days={days}, limit={limit}"
            )

            # 直接使用 news_data 路由的查询逻辑
            get_news_data_service = getattr(
                importlib.import_module("app.services.market.news"),
                "get_news_data_service",
            )
            NewsQueryParams = getattr(
                importlib.import_module("app.services.market.news"), "NewsQueryParams"
            )
            datetime = getattr(importlib.import_module("datetime"), "datetime")
            get_akshare_sync_service = getattr(
                importlib.import_module("app.worker.akshare.sync"),
                "get_akshare_sync_service",
            )

            service = await get_news_data_service()
            sync_service = await get_akshare_sync_service()

            # 🔥 不设置 start_time 限制，直接查询最新的 N 条新闻
            # 因为数据库中的新闻可能不是最近几天的，而是历史数据
            params = NewsQueryParams(
                symbol=normalized_code,
                limit=limit,
                sort_by="publish_time",
                sort_order=-1,
            )

            logger.info(
                f"🔍 查询参数: symbol={params.symbol}, limit={params.limit} (不限制时间范围)"
            )

            # 1. 先从数据库查询
            logger.info("📊 步骤1: 从数据库查询新闻...")
            news_list = await service.query_news(params)
            logger.info(f"📊 数据库查询结果: 返回 {len(news_list)} 条新闻")

            data_source = "database"

            # 2. 如果数据库没有数据，调用同步服务
            if not news_list:
                logger.info(f"⚠️ 数据库无新闻数据，调用同步服务获取: {normalized_code}")
                try:
                    # 🔥 调用同步服务，传入单个股票代码列表
                    logger.info("📡 步骤2: 调用同步服务...")
                    await sync_service.sync_news_data(
                        symbols=[normalized_code],
                        max_news_per_stock=limit,
                        force_update=False,
                        favorites_only=False,
                    )

                    # 重新查询
                    logger.info("🔄 步骤3: 重新从数据库查询...")
                    news_list = await service.query_news(params)
                    logger.info(f"📊 重新查询结果: 返回 {len(news_list)} 条新闻")
                    data_source = "realtime"

                except Exception as e:
                    logger.error(f"❌ 同步服务异常: {e}", exc_info=True)

            # 转换为旧格式（兼容前端）
            logger.info("🔄 步骤4: 转换数据格式...")
            items = []
            for news in news_list:
                # 🔥 将 datetime 对象转换为 ISO 字符串
                publish_time = news.get("publish_time", "")
                if isinstance(publish_time, datetime):
                    publish_time = publish_time.isoformat()

                items.append(
                    {
                        "title": news.get("title", ""),
                        "source": news.get("source", ""),
                        "time": publish_time,
                        "url": news.get("url", ""),
                        "type": "news",
                        "content": news.get("content", ""),
                        "summary": news.get("summary", ""),
                    }
                )

            logger.info(f"✅ 转换完成: {len(items)} 条新闻")

            if not items:
                logger.info(
                    f"🔄 数据库/同步服务无新闻，尝试统一数据源兜底: {normalized_code}"
                )
                try:
                    DataSourceManager = getattr(
                        importlib.import_module("app.services.sources.manager"),
                        "DataSourceManager",
                    )

                    fallback_items, fallback_source = (
                        DataSourceManager().get_news_with_fallback(
                            normalized_code,
                            days=days,
                            limit=limit,
                            include_announcements=include_announcements,
                        )
                    )
                    if fallback_items:
                        items = fallback_items
                        data_source = fallback_source
                        logger.info(
                            f"✅ 统一数据源兜底成功: source={fallback_source}, items={len(items)}"
                        )
                except Exception as fallback_error:
                    logger.error(
                        f"❌ 统一数据源兜底失败: {fallback_error}", exc_info=True
                    )

            data = {
                "code": normalized_code,
                "days": days,
                "limit": limit,
                "include_announcements": include_announcements,
                "source": data_source,
                "items": items,
            }

            logger.info(f"📤 最终返回: source={data_source}, items_count={len(items)}")
            logger.info("=" * 80)
            return ok(data)

        except Exception as e:
            logger.error(f"❌ 获取新闻失败: {e}", exc_info=True)
            try:
                DataSourceManager = getattr(
                    importlib.import_module("app.services.sources.manager"),
                    "DataSourceManager",
                )

                fallback_items, fallback_source = (
                    DataSourceManager().get_news_with_fallback(
                        normalized_code,
                        days=days,
                        limit=limit,
                        include_announcements=include_announcements,
                    )
                )
                data = {
                    "code": normalized_code,
                    "days": days,
                    "limit": limit,
                    "include_announcements": include_announcements,
                    "source": fallback_source,
                    "items": fallback_items or [],
                }
                return ok(data)
            except Exception as fallback_error:
                logger.error(
                    f"❌ 新闻备用数据源也失败: {fallback_error}", exc_info=True
                )
            data = {
                "code": normalized_code,
                "days": days,
                "limit": limit,
                "include_announcements": include_announcements,
                "source": None,
                "items": [],
            }
            return ok(data)
