# ruff: noqa: F401,F403,F405,F821


def _detect_market_and_code(code: str) -> Tuple[str, str]:
    code = code.strip().upper()
    if code.endswith(".HK"):
        return "HK", code[:-3].zfill(5)
    if re.match(r"^[A-Z]+$", code):
        return "US", code
    if re.match(r"^\d{4,5}$", code):
        return "HK", code.zfill(5)
    if re.match(r"^\d{6}$", code):
        return "CN", code
    return "CN", code


def _dump_model(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value) if isinstance(value, dict) else {}


def _build_quote_payload(
    code: str, data: Dict[str, Any], source: str
) -> Dict[str, Any]:
    price = data.get("price") or data.get("current_price") or data.get("close")
    prev_close = data.get("prev_close") or data.get("pre_close")
    return {
        **data,
        "symbol": data.get("symbol") or data.get("code") or code,
        "code": data.get("code") or data.get("symbol") or code,
        "name": data.get("name") or f"股票{code}",
        "market": data.get("market") or "A股",
        "price": price,
        "prev_close": prev_close,
        "change_percent": data.get("change_percent") or data.get("pct_chg"),
        "turnover_rate": data.get("turnover_rate") or data.get("turnover"),
        "amplitude": data.get("amplitude"),
        "trade_date": data.get("trade_date") or data.get("date"),
        "updated_at": data.get("updated_at") or data.get("last_sync"),
        "source": source,
    }


def _build_fundamentals_payload(
    code: str,
    basic: Dict[str, Any],
    quote: Dict[str, Any],
    source: str,
) -> Dict[str, Any]:
    return {
        **basic,
        "symbol": basic.get("symbol") or basic.get("code") or code,
        "code": basic.get("code") or basic.get("symbol") or code,
        "name": basic.get("name") or quote.get("name") or f"股票{code}",
        "market": basic.get("market") or quote.get("market") or "A股",
        "industry": basic.get("industry"),
        "sector": basic.get("sector") or basic.get("sec"),
        "pe": quote.get("pe") or basic.get("pe"),
        "pb": quote.get("pb") or basic.get("pb"),
        "pe_ttm": quote.get("pe_ttm") or basic.get("pe_ttm") or quote.get("pe"),
        "pb_mrq": basic.get("pb_mrq") or quote.get("pb"),
        "roe": basic.get("roe"),
        "total_mv": quote.get("total_mv") or basic.get("total_mv"),
        "circ_mv": quote.get("circ_mv") or basic.get("circ_mv"),
        "turnover_rate": quote.get("turnover_rate") or basic.get("turnover_rate"),
        "volume_ratio": quote.get("volume_ratio") or basic.get("volume_ratio"),
        "updated_at": quote.get("updated_at") or basic.get("updated_at"),
        "source": source,
    }


def _format_kline_item(row: Dict[str, Any]) -> Dict[str, Any]:
    trade_time = row.get("time") or row.get("trade_date") or row.get("date")
    if hasattr(trade_time, "isoformat"):
        trade_time = trade_time.isoformat()[:10]
    return {
        "time": str(trade_time)[:10] if trade_time is not None else "",
        "open": row.get("open"),
        "high": row.get("high"),
        "low": row.get("low"),
        "close": row.get("close"),
        "volume": row.get("volume"),
        "amount": row.get("amount"),
    }


def _as_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _trade_date_value(row: Dict[str, Any]) -> str:
    value = row.get("time") or row.get("trade_date") or row.get("date") or ""
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    return str(value)


async def _enrich_quote_from_daily_quotes(
    code: str, quote: Dict[str, Any]
) -> Dict[str, Any]:
    try:
        db = get_postgres_db()
        service = UnifiedStockService(db)
        rows = await service.get_daily_quotes("CN", code, limit=3)
    except Exception as e:
        logger.debug("从K线补充行情字段失败 %s: %s", code, e)
        return quote

    dated_rows = [row for row in rows if _trade_date_value(row)]
    if not dated_rows:
        return quote

    dated_rows.sort(key=_trade_date_value)
    latest = dated_rows[-1]
    previous = dated_rows[-2] if len(dated_rows) >= 2 else {}

    latest_close = _as_float(latest.get("close"))
    previous_close = _as_float(previous.get("close")) or _as_float(
        quote.get("prev_close") or quote.get("pre_close")
    )
    high = _as_float(latest.get("high"))
    low = _as_float(latest.get("low"))

    quote["trade_date"] = _trade_date_value(latest)
    quote.setdefault("close", latest_close)
    quote.setdefault("price", latest_close)
    quote.setdefault("prev_close", previous_close)
    quote.setdefault("volume", latest.get("volume"))
    quote.setdefault("amount", latest.get("amount"))

    if quote.get("change_percent") in (None, "") and latest_close and previous_close:
        quote["change_percent"] = round(
            (latest_close - previous_close) / previous_close * 100, 3
        )
    if quote.get("amplitude") in (None, "") and high and low and previous_close:
        quote["amplitude"] = round((high - low) / previous_close * 100, 3)

    return quote


async def _get_akshare_provider():
    get_akshare_provider = getattr(
        importlib.import_module("trader.flows.providers.china.akshare"),
        "get_akshare_provider",
    )
    return get_akshare_provider()


@router.get("/{code}/quote", response_model=ApiResponse)
async def get_quote(code: str, current_user: dict = Depends(get_current_user)):
    market, normalized_code = _detect_market_and_code(code)
    if market != "CN":
        ForeignStockService = getattr(
            importlib.import_module("app.services.stocks.foreign"),
            "ForeignStockService",
        )
        quote = await ForeignStockService().get_quote(market, normalized_code)
        if not quote:
            raise HTTPException(status_code=404, detail="Not Found")
        return ok(_build_quote_payload(normalized_code, quote, "foreign"))

    service = StockDataService()
    quote = _dump_model(await service.get_market_quotes(normalized_code))
    source = "database"
    if not quote:
        provider = await _get_akshare_provider()
        quote = await provider.get_stock_quotes(normalized_code) or {}
        source = "akshare"
        if quote:
            await service.update_market_quotes(normalized_code, quote)
    if not quote:
        raise HTTPException(status_code=404, detail="Not Found")
    if not quote.get("name") or quote.get("name") == f"股票{normalized_code}":
        basic = _dump_model(await service.get_stock_basic_info(normalized_code))
        if basic.get("name"):
            quote["name"] = basic["name"]
            quote.setdefault("market", basic.get("market"))
    quote = await _enrich_quote_from_daily_quotes(normalized_code, quote)
    return ok(_build_quote_payload(normalized_code, quote, source))


@router.get("/{code}/fundamentals", response_model=ApiResponse)
async def get_fundamentals(code: str, current_user: dict = Depends(get_current_user)):
    market, normalized_code = _detect_market_and_code(code)
    if market != "CN":
        return ok(
            {
                "symbol": normalized_code,
                "code": normalized_code,
                "market": market,
                "name": normalized_code,
                "source": "none",
            }
        )

    service = StockDataService()
    basic = _dump_model(await service.get_stock_basic_info(normalized_code))
    quote = _dump_model(await service.get_market_quotes(normalized_code))
    source = "database"

    if not basic or not quote:
        provider = await _get_akshare_provider()
        if not basic:
            basic = await provider.get_stock_basic_info(normalized_code) or {}
            if basic:
                await service.update_stock_basic_info(
                    normalized_code, basic, source="akshare"
                )
        if not quote:
            quote = await provider.get_stock_quotes(normalized_code) or {}
            if quote:
                await service.update_market_quotes(normalized_code, quote)
        source = "akshare"

    if not basic and not quote:
        raise HTTPException(status_code=404, detail="Not Found")
    quote = await _enrich_quote_from_daily_quotes(normalized_code, quote)
    return ok(_build_fundamentals_payload(normalized_code, basic, quote, source))


@router.get("/{code}/kline", response_model=ApiResponse)
async def get_kline(
    code: str,
    period: str = Query("day", description="day/week/month/5m/15m/30m/60m"),
    limit: int = Query(120, ge=1, le=1000),
    adj: str = Query("none"),
    current_user: dict = Depends(get_current_user),
):
    market, normalized_code = _detect_market_and_code(code)
    period_map = {"day": "daily", "week": "weekly", "month": "monthly"}
    data_source = "database"
    items: list[Dict[str, Any]] = []

    if market == "CN":
        try:
            db = get_postgres_db()
            service = UnifiedStockService(db)
            rows = await service.get_daily_quotes("CN", normalized_code, limit=limit)
            items = [_format_kline_item(row) for row in reversed(rows)]
        except Exception as e:
            logger.warning("数据库K线查询失败，尝试AKShare兜底: %s", e)

        if not items:
            provider = await _get_akshare_provider()
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (
                datetime.now() - timedelta(days=max(limit * 2, 180))
            ).strftime("%Y-%m-%d")
            df = await provider.get_historical_data(
                code=normalized_code,
                start_date=start_date,
                end_date=end_date,
                period=period_map.get(period, "daily"),
            )
            if df is not None and not df.empty:
                rows = df.tail(limit).to_dict("records")
                items = [_format_kline_item(row) for row in rows]
                data_source = "akshare"
    else:
        ForeignStockService = getattr(
            importlib.import_module("app.services.stocks.foreign"),
            "ForeignStockService",
        )
        rows = await ForeignStockService().get_kline(
            market, normalized_code, period=period, limit=limit
        )
        items = [_format_kline_item(row) for row in rows or []]
        data_source = "foreign"

    return ok(
        {
            "symbol": normalized_code,
            "code": normalized_code,
            "period": period,
            "limit": limit,
            "adj": adj,
            "source": data_source,
            "items": items,
        }
    )


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
