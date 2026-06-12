from .imports import (
    Any,
    Optional,
    cast,
    importlib,
    logger,
)


class _OptimizedChinaDataProviderMixin3:
    def _get_real_financial_metrics(
        self, symbol: str, price_value: float
    ) -> Optional[dict]:
        """获取真实财务指标 - 优先使用数据库缓存，再使用API"""
        try:
            # 🔥 优先从 market_quotes 获取实时股价，替换传入的 price_value
            get_database_manager = getattr(
                importlib.import_module("trader.config.databases"),
                "get_database_manager",
            )
            db_manager = get_database_manager()
            db_client = None

            if db_manager.is_postgres_available():
                try:
                    db_client = cast(Any, db_manager.get_postgres_client())
                    db = db_client["trading_agents"]

                    # 标准化股票代码为6位
                    code6 = symbol.replace(".SH", "").replace(".SZ", "").zfill(6)

                    # 从 market_quotes 获取实时股价
                    quote = db.market_quotes.find_one({"code": code6})
                    if quote and quote.get("close"):
                        realtime_price = float(quote.get("close"))
                        logger.info(
                            f"✅ 从 market_quotes 获取实时股价: {code6} = {realtime_price}元 (原价格: {price_value}元)"
                        )
                        price_value = realtime_price
                    else:
                        logger.info(
                            f"⚠️ market_quotes 中未找到{code6}的实时股价，使用传入价格: {price_value}元"
                        )
                except Exception as e:
                    logger.warning(
                        f"⚠️ 从 market_quotes 获取实时股价失败: {e}，使用传入价格: {price_value}元"
                    )
            else:
                logger.info(f"⚠️ PostgreSQL 不可用，使用传入价格: {price_value}元")

            # 第一优先级：从 PostgreSQL stock_financial_data 集合获取标准化财务数据
            use_app_cache_enabled = getattr(
                importlib.import_module("trader.config.runtime"),
                "use_app_cache_enabled",
            )
            if use_app_cache_enabled(False):
                logger.info(
                    f"🔍 优先从 PostgreSQL stock_financial_data 集合获取{symbol}财务数据"
                )

                # 直接从 PostgreSQL 获取标准化的财务数据
                get_postgres_cache_adapter = getattr(
                    importlib.import_module("trader.flows.cache.postgres"),
                    "get_postgres_cache_adapter",
                )
                adapter = get_postgres_cache_adapter()
                financial_data = adapter.get_financial_data(symbol)

                if financial_data:
                    logger.info(
                        f"✅ [财务数据] 从 stock_financial_data 集合获取{symbol}财务数据"
                    )
                    # 解析 PostgreSQL 标准化的财务数据
                    metrics = self._parse_postgres_financial_data(
                        financial_data, price_value
                    )
                    if metrics:
                        logger.info("✅ PostgreSQL 财务数据解析成功，返回指标")
                        return metrics
                    else:
                        logger.warning("⚠️ PostgreSQL 财务数据解析失败")
                else:
                    logger.info(
                        f"🔄 PostgreSQL 未找到{symbol}财务数据，尝试从 AKShare API 获取"
                    )
            else:
                logger.info(
                    f"🔄 数据库缓存未启用，直接从AKShare API获取{symbol}财务数据"
                )

            # 第二优先级：从AKShare API获取
            get_akshare_provider = getattr(
                importlib.import_module("trader.flows.providers.china.akshare"),
                "get_akshare_provider",
            )
            asyncio = importlib.import_module("asyncio")

            akshare_provider = get_akshare_provider()

            if akshare_provider.connected:
                # AKShare的get_financial_data是异步方法，需要使用asyncio运行
                loop = asyncio.get_event_loop()
                financial_data = loop.run_until_complete(
                    akshare_provider.get_financial_data(symbol)
                )

                if financial_data and any(
                    not v.empty if hasattr(v, "empty") else bool(v)
                    for v in financial_data.values()
                ):
                    logger.info(f"✅ AKShare财务数据获取成功: {symbol}")
                    # 获取股票基本信息（也是异步方法）
                    stock_info = loop.run_until_complete(
                        akshare_provider.get_stock_basic_info(symbol)
                    )

                    # 解析AKShare财务数据
                    logger.debug(f"🔧 调用AKShare解析函数，股价: {price_value}")
                    metrics = self._parse_akshare_financial_data(
                        financial_data, stock_info, price_value
                    )
                    logger.debug(f"🔧 AKShare解析结果: {metrics}")
                    if metrics:
                        logger.info("✅ AKShare解析成功，返回指标")
                        # 缓存原始财务数据到数据库（而不是解析后的指标）
                        cast(Any, self)._cache_raw_financial_data(
                            symbol, financial_data, stock_info
                        )
                        return metrics
                    else:
                        logger.warning("⚠️ AKShare解析失败，返回None")
                else:
                    logger.warning(f"⚠️ AKShare未获取到{symbol}财务数据，尝试Tushare")
            else:
                logger.warning("⚠️ AKShare未连接，尝试Tushare")

            # 第三优先级：使用Tushare数据源
            logger.info(f"🔄 使用Tushare备用数据源获取{symbol}财务数据")
            get_tushare_provider = getattr(
                importlib.import_module("trader.flows.providers.china.tushare"),
                "get_tushare_provider",
            )
            asyncio = importlib.import_module("asyncio")

            provider = get_tushare_provider()
            if not provider.connected:
                logger.debug(f"Tushare未连接，无法获取{symbol}真实财务数据")
                return None

            # 获取财务数据（异步方法）
            loop = asyncio.get_event_loop()
            financial_data = loop.run_until_complete(
                provider.get_financial_data(symbol)
            )
            if not financial_data:
                logger.debug(f"未获取到{symbol}的财务数据")
                return None

            # 获取股票基本信息（异步方法）
            stock_info = loop.run_until_complete(provider.get_stock_basic_info(symbol))
            if not isinstance(stock_info, dict):
                stock_info = {}

            # 解析Tushare财务数据
            if not isinstance(financial_data, dict):
                logger.debug(f"Tushare返回的{symbol}财务数据不是字典格式")
                return None

            metrics = self._parse_financial_data(
                financial_data, stock_info, price_value
            )
            if metrics:
                # 缓存原始财务数据到数据库
                cast(Any, self)._cache_raw_financial_data(
                    symbol, financial_data, stock_info
                )
                return metrics

        except Exception as e:
            logger.debug(f"获取{symbol}真实财务数据失败: {e}")

        return None

    def _parse_postgres_financial_data(
        self, financial_data: dict, price_value: float
    ) -> Optional[dict]:
        """解析 PostgreSQL 标准化的财务数据为指标"""
        try:
            logger.debug(
                f"📊 [财务数据] 开始解析 PostgreSQL 财务数据，包含字段: {list(financial_data.keys())}"
            )

            metrics = {}

            # PostgreSQL 的 financial_data 是扁平化的结构，直接包含所有财务指标
            # 不再是嵌套的 {balance_sheet, income_statement, ...} 结构

            # 直接从 financial_data 中提取指标
            latest_indicators = financial_data

            # ROE - 净资产收益率 (添加范围验证)
            roe = latest_indicators.get("roe") or latest_indicators.get("roe_waa")
            if roe is not None and str(roe) != "nan" and roe != "--":
                try:
                    roe_val = float(roe)
                    # ROE 通常在 -100% 到 100% 之间，极端情况可能超出
                    if -200 <= roe_val <= 200:
                        metrics["roe"] = f"{roe_val:.1f}%"
                    else:
                        logger.warning(
                            f"⚠️ ROE 数据异常: {roe_val}，超出合理范围 [-200%, 200%]，设为 N/A"
                        )
                        metrics["roe"] = "N/A"
                except (ValueError, TypeError):
                    metrics["roe"] = "N/A"
            else:
                metrics["roe"] = "N/A"

            # ROA - 总资产收益率 (添加范围验证)
            roa = latest_indicators.get("roa") or latest_indicators.get("roa2")
            if roa is not None and str(roa) != "nan" and roa != "--":
                try:
                    roa_val = float(roa)
                    # ROA 通常在 -50% 到 50% 之间
                    if -100 <= roa_val <= 100:
                        metrics["roa"] = f"{roa_val:.1f}%"
                    else:
                        logger.warning(
                            f"⚠️ ROA 数据异常: {roa_val}，超出合理范围 [-100%, 100%]，设为 N/A"
                        )
                        metrics["roa"] = "N/A"
                except (ValueError, TypeError):
                    metrics["roa"] = "N/A"
            else:
                metrics["roa"] = "N/A"

            # 毛利率 - 添加范围验证
            gross_margin = latest_indicators.get("gross_margin")
            if (
                gross_margin is not None
                and str(gross_margin) != "nan"
                and gross_margin != "--"
            ):
                try:
                    gross_margin_val = float(gross_margin)
                    # 验证范围：毛利率应该在 -100% 到 100% 之间
                    # 如果超出范围，可能是数据错误（如存储的是绝对金额而不是百分比）
                    if -100 <= gross_margin_val <= 100:
                        metrics["gross_margin"] = f"{gross_margin_val:.1f}%"
                    else:
                        logger.warning(
                            f"⚠️ 毛利率数据异常: {gross_margin_val}，超出合理范围 [-100%, 100%]，设为 N/A"
                        )
                        metrics["gross_margin"] = "N/A"
                except (ValueError, TypeError):
                    metrics["gross_margin"] = "N/A"
            else:
                metrics["gross_margin"] = "N/A"

            # 净利率 - 添加范围验证
            net_margin = latest_indicators.get("netprofit_margin")
            if (
                net_margin is not None
                and str(net_margin) != "nan"
                and net_margin != "--"
            ):
                try:
                    net_margin_val = float(net_margin)
                    # 验证范围：净利率应该在 -100% 到 100% 之间
                    if -100 <= net_margin_val <= 100:
                        metrics["net_margin"] = f"{net_margin_val:.1f}%"
                    else:
                        logger.warning(
                            f"⚠️ 净利率数据异常: {net_margin_val}，超出合理范围 [-100%, 100%]，设为 N/A"
                        )
                        metrics["net_margin"] = "N/A"
                except (ValueError, TypeError):
                    metrics["net_margin"] = "N/A"
            else:
                metrics["net_margin"] = "N/A"

            # 计算 PE/PB - 优先使用实时计算，降级到静态数据
            # 同时获取 PE 和 PE_TTM 两个指标
            pe_value = None
            pe_ttm_value = None
            pb_value = None
            is_loss_stock = False  # 🔥 标记是否为亏损股

            try:
                # 优先使用实时计算
                get_pe_pb_with_fallback = getattr(
                    importlib.import_module("trader.flows.metrics"),
                    "get_pe_pb_with_fallback",
                )
                get_database_manager = getattr(
                    importlib.import_module("trader.config.databases"),
                    "get_database_manager",
                )

                db_manager = get_database_manager()
                if db_manager.is_postgres_available():
                    client = db_manager.get_postgres_client()
                    # 从symbol中提取股票代码
                    stock_code = latest_indicators.get("code") or latest_indicators.get(
                        "symbol", ""
                    ).replace(".SZ", "").replace(".SH", "")

                    logger.info(f"📊 [PE计算] 开始计算股票 {stock_code} 的PE/PB")

                    if stock_code:
                        logger.info(
                            f"📊 [PE计算-第1层] 尝试实时计算 PE/PB (股票代码: {stock_code})"
                        )

                        # 获取实时PE/PB
                        realtime_metrics = get_pe_pb_with_fallback(stock_code, client)

                        if realtime_metrics:
                            # 获取市值数据（优先保存）
                            market_cap = realtime_metrics.get("market_cap")
                            if market_cap is not None and market_cap > 0:
                                is_realtime = realtime_metrics.get("is_realtime", False)
                                realtime_tag = " (实时)" if is_realtime else ""
                                metrics["total_mv"] = (
                                    f"{market_cap:.2f}亿元{realtime_tag}"
                                )
                                logger.info(
                                    f"✅ [总市值获取成功] 总市值={market_cap:.2f}亿元 | 实时={is_realtime}"
                                )

                            # 使用实时PE（动态市盈率）
                            pe_value = realtime_metrics.get("pe")
                            if pe_value is not None and pe_value > 0:
                                is_realtime = realtime_metrics.get("is_realtime", False)
                                realtime_tag = " (实时)" if is_realtime else ""
                                metrics["pe"] = f"{pe_value:.1f}倍{realtime_tag}"

                                # 详细日志
                                price = realtime_metrics.get("price", "N/A")
                                market_cap_log = realtime_metrics.get(
                                    "market_cap", "N/A"
                                )
                                source = realtime_metrics.get("source", "unknown")
                                updated_at = realtime_metrics.get("updated_at", "N/A")

                                logger.info(
                                    f"✅ [PE计算-第1层成功] PE={pe_value:.2f}倍 | 来源={source} | 实时={is_realtime}"
                                )
                                logger.info(
                                    f"   └─ 计算数据: 股价={price}元, 市值={market_cap_log}亿元, 更新时间={updated_at}"
                                )
                            elif pe_value is None:
                                # 🔥 PE 为 None，检查是否是亏损股
                                pe_ttm_check = latest_indicators.get("pe_ttm")
                                # pe_ttm 为 None、<= 0、'nan'、'--' 都认为是亏损股
                                if (
                                    pe_ttm_check is None
                                    or pe_ttm_check <= 0
                                    or str(pe_ttm_check) == "nan"
                                    or pe_ttm_check == "--"
                                ):
                                    is_loss_stock = True
                                    logger.info(
                                        f"⚠️ [PE计算-第1层] PE为None且pe_ttm={pe_ttm_check}，确认为亏损股"
                                    )

                            # 使用实时PE_TTM（TTM市盈率）
                            pe_ttm_value = realtime_metrics.get("pe_ttm")
                            if pe_ttm_value is not None and pe_ttm_value > 0:
                                is_realtime = realtime_metrics.get("is_realtime", False)
                                realtime_tag = " (实时)" if is_realtime else ""
                                metrics["pe_ttm"] = (
                                    f"{pe_ttm_value:.1f}倍{realtime_tag}"
                                )
                                logger.info(
                                    f"✅ [PE_TTM计算-第1层成功] PE_TTM={pe_ttm_value:.2f}倍 | 来源={source} | 实时={is_realtime}"
                                )
                            elif pe_ttm_value is None and not is_loss_stock:
                                # 🔥 PE_TTM 为 None，再次检查是否是亏损股
                                pe_ttm_check = latest_indicators.get("pe_ttm")
                                # pe_ttm 为 None、<= 0、'nan'、'--' 都认为是亏损股
                                if (
                                    pe_ttm_check is None
                                    or pe_ttm_check <= 0
                                    or str(pe_ttm_check) == "nan"
                                    or pe_ttm_check == "--"
                                ):
                                    is_loss_stock = True
                                    logger.info(
                                        f"⚠️ [PE_TTM计算-第1层] PE_TTM为None且pe_ttm={pe_ttm_check}，确认为亏损股"
                                    )

                            # 使用实时PB
                            pb_value = realtime_metrics.get("pb")
                            if pb_value is not None and pb_value > 0:
                                is_realtime = realtime_metrics.get("is_realtime", False)
                                realtime_tag = " (实时)" if is_realtime else ""
                                metrics["pb"] = f"{pb_value:.2f}倍{realtime_tag}"
                                logger.info(
                                    f"✅ [PB计算-第1层成功] PB={pb_value:.2f}倍 | 来源={realtime_metrics.get('source')} | 实时={is_realtime}"
                                )
                        else:
                            # 🔥 检查是否因为亏损导致返回 None
                            # 从 stock_basic_info 获取 pe_ttm 判断是否亏损
                            pe_ttm_static = latest_indicators.get("pe_ttm")
                            # pe_ttm 为 None、<= 0、'nan'、'--' 都认为是亏损股
                            if (
                                pe_ttm_static is None
                                or pe_ttm_static <= 0
                                or str(pe_ttm_static) == "nan"
                                or pe_ttm_static == "--"
                            ):
                                is_loss_stock = True
                                logger.info(
                                    f"⚠️ [PE计算-第1层失败] 检测到亏损股（pe_ttm={pe_ttm_static}），跳过降级计算"
                                )
                            else:
                                logger.warning(
                                    "⚠️ [PE计算-第1层失败] 实时计算返回空结果，将尝试降级计算"
                                )

            except Exception as e:
                logger.warning(
                    f"⚠️ [PE计算-第1层异常] 实时计算失败: {e}，将尝试降级计算"
                )

            # 如果实时计算失败，尝试从 latest_indicators 获取总市值
            if "total_mv" not in metrics:
                logger.info("📊 [总市值-第2层] 尝试从 stock_basic_info 获取")
                total_mv_static = latest_indicators.get("total_mv")
                if total_mv_static is not None and total_mv_static > 0:
                    metrics["total_mv"] = f"{total_mv_static:.2f}亿元"
                    logger.info(
                        f"✅ [总市值-第2层成功] 总市值={total_mv_static:.2f}亿元 (来源: stock_basic_info)"
                    )
                else:
                    # 尝试从 money_cap 计算（万元转亿元）
                    money_cap = latest_indicators.get("money_cap")
                    if money_cap is not None and money_cap > 0:
                        total_mv_yi = money_cap / 10000
                        metrics["total_mv"] = f"{total_mv_yi:.2f}亿元"
                        logger.info(
                            f"✅ [总市值-第3层成功] 总市值={total_mv_yi:.2f}亿元 (从money_cap转换)"
                        )
                    else:
                        metrics["total_mv"] = "N/A"
                        logger.warning("⚠️ [总市值-全部失败] 无可用总市值数据")

            # 如果实时计算失败，尝试传统计算方式
            if pe_value is None:
                # 🔥 如果已经确认是亏损股，直接设置 PE 为 N/A，不再尝试降级计算
                if is_loss_stock:
                    metrics["pe"] = "N/A"
                    logger.info(
                        "⚠️ [PE计算-亏损股] 已确认为亏损股，PE设置为N/A，跳过第2层计算"
                    )
                else:
                    logger.info("📊 [PE计算-第2层] 尝试使用市值/净利润计算")

                    net_profit = latest_indicators.get("net_profit")

                    # 🔥 关键修复：检查净利润是否为正数（亏损股不计算PE）
                    if net_profit and net_profit > 0:
                        try:
                            # 使用市值/净利润计算PE
                            money_cap = latest_indicators.get("money_cap")
                            if money_cap and money_cap > 0:
                                pe_calculated = money_cap / net_profit
                                metrics["pe"] = f"{pe_calculated:.1f}倍"
                                logger.info(
                                    f"✅ [PE计算-第2层成功] PE={pe_calculated:.2f}倍"
                                )
                                logger.info(
                                    f"   └─ 计算公式: 市值({money_cap}万元) / 净利润({net_profit}万元)"
                                )
                            else:
                                logger.warning(
                                    f"⚠️ [PE计算-第2层失败] 市值无效: {money_cap}，尝试第3层"
                                )

                                # 第三层降级：直接使用 latest_indicators 中的 pe 字段（仅当为正数时）
                                pe_static = latest_indicators.get("pe")
                                if (
                                    pe_static is not None
                                    and str(pe_static) != "nan"
                                    and pe_static != "--"
                                ):
                                    try:
                                        pe_float = float(pe_static)
                                        # 🔥 只接受正数的 PE
                                        if pe_float > 0:
                                            metrics["pe"] = f"{pe_float:.1f}倍"
                                            logger.info(
                                                f"✅ [PE计算-第3层成功] 使用静态PE: {metrics['pe']}"
                                            )
                                            logger.info(
                                                "   └─ 数据来源: stock_basic_info.pe"
                                            )
                                        else:
                                            metrics["pe"] = "N/A"
                                            logger.info(
                                                f"⚠️ [PE计算-第3层跳过] 静态PE为负数或零（亏损股）: {pe_float}"
                                            )
                                    except (ValueError, TypeError):
                                        metrics["pe"] = "N/A"
                                        logger.error(
                                            f"❌ [PE计算-第3层失败] 静态PE格式错误: {pe_static}"
                                        )
                                else:
                                    metrics["pe"] = "N/A"
                                    logger.error("❌ [PE计算-全部失败] 无可用PE数据")
                        except (ValueError, TypeError, ZeroDivisionError) as e:
                            metrics["pe"] = "N/A"
                            logger.error(f"❌ [PE计算-第2层异常] 计算失败: {e}")
                    elif net_profit and net_profit < 0:
                        # 🔥 亏损股：PE 设置为 N/A
                        metrics["pe"] = "N/A"
                        logger.info(
                            f"⚠️ [PE计算-亏损股] 净利润为负数（{net_profit}万元），PE设置为N/A"
                        )
                    else:
                        logger.warning(
                            f"⚠️ [PE计算-第2层跳过] 净利润无效: {net_profit}，尝试第3层"
                        )

                        # 第三层降级：直接使用 latest_indicators 中的 pe 字段（仅当为正数时）
                        pe_static = latest_indicators.get("pe")
                        if (
                            pe_static is not None
                            and str(pe_static) != "nan"
                            and pe_static != "--"
                        ):
                            try:
                                pe_float = float(pe_static)
                                # 🔥 只接受正数的 PE
                                if pe_float > 0:
                                    metrics["pe"] = f"{pe_float:.1f}倍"
                                    logger.info(
                                        f"✅ [PE计算-第3层成功] 使用静态PE: {metrics['pe']}"
                                    )
                                    logger.info("   └─ 数据来源: stock_basic_info.pe")
                                else:
                                    metrics["pe"] = "N/A"
                                    logger.info(
                                        f"⚠️ [PE计算-第3层跳过] 静态PE为负数或零（亏损股）: {pe_float}"
                                    )
                            except (ValueError, TypeError):
                                metrics["pe"] = "N/A"
                                logger.error(
                                    f"❌ [PE计算-第3层失败] 静态PE格式错误: {pe_static}"
                                )
                        else:
                            metrics["pe"] = "N/A"
                            logger.error("❌ [PE计算-全部失败] 无可用PE数据")

            # 如果 PE_TTM 未获取到，尝试从静态数据获取
            if pe_ttm_value is None:
                # 🔥 如果已经确认是亏损股，直接设置 PE_TTM 为 N/A
                if is_loss_stock:
                    metrics["pe_ttm"] = "N/A"
                    logger.info("⚠️ [PE_TTM计算-亏损股] 已确认为亏损股，PE_TTM设置为N/A")
                else:
                    logger.info("📊 [PE_TTM计算-第2层] 尝试从静态数据获取")
                    pe_ttm_static = latest_indicators.get("pe_ttm")
                    if (
                        pe_ttm_static is not None
                        and str(pe_ttm_static) != "nan"
                        and pe_ttm_static != "--"
                    ):
                        try:
                            pe_ttm_float = float(pe_ttm_static)
                            # 🔥 只接受正数的 PE_TTM（亏损股不显示PE_TTM）
                            if pe_ttm_float > 0:
                                metrics["pe_ttm"] = f"{pe_ttm_float:.1f}倍"
                                logger.info(
                                    f"✅ [PE_TTM计算-第2层成功] 使用静态PE_TTM: {metrics['pe_ttm']}"
                                )
                                logger.info("   └─ 数据来源: stock_basic_info.pe_ttm")
                            else:
                                metrics["pe_ttm"] = "N/A"
                                logger.info(
                                    f"⚠️ [PE_TTM计算-第2层跳过] 静态PE_TTM为负数或零（亏损股）: {pe_ttm_float}"
                                )
                        except (ValueError, TypeError):
                            metrics["pe_ttm"] = "N/A"
                            logger.error(
                                f"❌ [PE_TTM计算-第2层失败] 静态PE_TTM格式错误: {pe_ttm_static}"
                            )
                    else:
                        metrics["pe_ttm"] = "N/A"
                        logger.warning("⚠️ [PE_TTM计算-全部失败] 无可用PE_TTM数据")

            if pb_value is None:
                total_equity = latest_indicators.get("total_hldr_eqy_exc_min_int")
                if total_equity and total_equity > 0:
                    try:
                        # 使用市值/净资产计算PB
                        money_cap = latest_indicators.get("money_cap")
                        if money_cap and money_cap > 0:
                            # 注意单位转换：money_cap 是万元，total_equity 是元
                            # PB = 市值(万元) * 10000 / 净资产(元)
                            pb_calculated = (money_cap * 10000) / total_equity
                            metrics["pb"] = f"{pb_calculated:.2f}倍"
                            logger.info(
                                f"✅ [PB计算-第2层成功] PB={pb_calculated:.2f}倍"
                            )
                            logger.info(
                                f"   └─ 计算公式: 市值{money_cap}万元 * 10000 / 净资产{total_equity}元 = {metrics['pb']}"
                            )
                        else:
                            # 第三层降级：直接使用 latest_indicators 中的 pb 字段
                            pb_static = latest_indicators.get(
                                "pb"
                            ) or latest_indicators.get("pb_mrq")
                            if (
                                pb_static is not None
                                and str(pb_static) != "nan"
                                and pb_static != "--"
                            ):
                                try:
                                    metrics["pb"] = f"{float(pb_static):.2f}倍"
                                    logger.info(
                                        f"✅ [PB计算-第3层成功] 使用静态PB: {metrics['pb']}"
                                    )
                                    logger.info("   └─ 数据来源: stock_basic_info.pb")
                                except (ValueError, TypeError):
                                    metrics["pb"] = "N/A"
                            else:
                                metrics["pb"] = "N/A"
                    except (ValueError, TypeError, ZeroDivisionError) as e:
                        logger.error(f"❌ [PB计算-第2层异常] 计算失败: {e}")
                        metrics["pb"] = "N/A"
                else:
                    # 第三层降级：直接使用 latest_indicators 中的 pb 字段
                    pb_static = latest_indicators.get("pb") or latest_indicators.get(
                        "pb_mrq"
                    )
                    if (
                        pb_static is not None
                        and str(pb_static) != "nan"
                        and pb_static != "--"
                    ):
                        try:
                            metrics["pb"] = f"{float(pb_static):.2f}倍"
                            logger.info(
                                f"✅ [PB计算-第3层成功] 使用静态PB: {metrics['pb']}"
                            )
                            logger.info("   └─ 数据来源: stock_basic_info.pb")
                        except (ValueError, TypeError):
                            metrics["pb"] = "N/A"
                    else:
                        metrics["pb"] = "N/A"

            # 资产负债率
            debt_ratio = latest_indicators.get("debt_to_assets")
            if (
                debt_ratio is not None
                and str(debt_ratio) != "nan"
                and debt_ratio != "--"
            ):
                try:
                    metrics["debt_ratio"] = f"{float(debt_ratio):.1f}%"
                except (ValueError, TypeError):
                    metrics["debt_ratio"] = "N/A"
            else:
                metrics["debt_ratio"] = "N/A"

            # 计算 PS - 市销率（使用TTM营业收入）
            # 优先使用 TTM 营业收入，如果没有则使用单期营业收入
            revenue_ttm = latest_indicators.get("revenue_ttm")
            revenue = latest_indicators.get("revenue")

            # 选择使用哪个营业收入数据
            revenue_for_ps = revenue_ttm if revenue_ttm and revenue_ttm > 0 else revenue
            revenue_type = "TTM" if revenue_ttm and revenue_ttm > 0 else "单期"

            if revenue_for_ps and revenue_for_ps > 0:
                try:
                    # 使用市值/营业收入计算PS
                    money_cap = latest_indicators.get("money_cap")
                    if money_cap and money_cap > 0:
                        ps_calculated = money_cap / revenue_for_ps
                        metrics["ps"] = f"{ps_calculated:.2f}倍"
                        logger.debug(
                            f"✅ 计算PS({revenue_type}): 市值{money_cap}万元 / 营业收入{revenue_for_ps}万元 = {metrics['ps']}"
                        )
                    else:
                        metrics["ps"] = "N/A"
                except (ValueError, TypeError, ZeroDivisionError):
                    metrics["ps"] = "N/A"
            else:
                metrics["ps"] = "N/A"

            # 股息收益率 - 暂时设为N/A，需要股息数据
            metrics["dividend_yield"] = "N/A"
            metrics["current_ratio"] = latest_indicators.get("current_ratio", "N/A")
            metrics["quick_ratio"] = latest_indicators.get("quick_ratio", "N/A")
            metrics["cash_ratio"] = latest_indicators.get("cash_ratio", "N/A")

            # 添加评分字段（使用默认值）
            metrics["fundamental_score"] = 7.0  # 基于真实数据的默认评分
            metrics["valuation_score"] = 6.5
            metrics["growth_score"] = 7.0
            metrics["risk_level"] = "中等"

            logger.info(
                f"✅ PostgreSQL 财务数据解析成功: ROE={metrics.get('roe')}, ROA={metrics.get('roa')}, 毛利率={metrics.get('gross_margin')}, 净利率={metrics.get('net_margin')}"
            )
            return metrics

        except Exception as e:
            logger.error(f"❌ PostgreSQL财务数据解析失败: {e}", exc_info=True)
            return None
