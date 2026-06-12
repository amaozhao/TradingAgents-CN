from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .imports import (
        Any,
        Optional,
        cast,
        importlib,
        logger,
    )

class _OptimizedChinaDataProviderMixin4:
    def _parse_akshare_financial_data(
        self, financial_data: dict, stock_info: Optional[dict], price_value: float
    ) -> Optional[dict]:
        """解析AKShare财务数据为指标"""
        try:
            stock_info = stock_info or {}

            # 获取最新的财务数据
            financial_data.get("balance_sheet", [])
            financial_data.get("income_statement", [])
            financial_data.get("cash_flow", [])
            main_indicators = financial_data.get("main_indicators")

            # main_indicators 可能是 DataFrame 或 list（to_dict('records') 的结果）
            if main_indicators is None:
                logger.warning("AKShare主要财务指标为空")
                return None

            # 检查是否为空
            if isinstance(main_indicators, list):
                if not main_indicators:
                    logger.warning("AKShare主要财务指标列表为空")
                    return None
                # 列表格式：[{指标: 值, ...}, ...]
                # 转换为 DataFrame 以便统一处理
                pd = importlib.import_module("pandas")
                main_indicators = pd.DataFrame(main_indicators)
            elif hasattr(main_indicators, "empty") and main_indicators.empty:
                logger.warning("AKShare主要财务指标DataFrame为空")
                return None

            # main_indicators是DataFrame，需要转换为字典格式便于查找
            # 获取最新数据列（第3列，索引为2）
            latest_col = main_indicators.columns[2] if len(main_indicators.columns) > 2 else None
            if latest_col is None:
                logger.warning("AKShare主要财务指标缺少数据列")
                return None

            logger.info(f"📅 使用AKShare最新数据期间: {latest_col}")

            # 创建指标名称到值的映射
            indicators_dict = {}
            for _, row in main_indicators.iterrows():
                indicator_name = row["指标"]
                value = row[latest_col]
                indicators_dict[indicator_name] = value

            logger.debug(f"AKShare主要财务指标数量: {len(indicators_dict)}")

            # 计算财务指标
            metrics = {}

            # 🔥 优先尝试使用实时 PE/PB 计算（与 PostgreSQL 解析保持一致）
            pe_value = None
            pe_ttm_value = None
            pb_value = None

            try:
                # 获取股票代码
                stock_code = stock_info.get("code", "").replace(".SH", "").replace(".SZ", "").zfill(6)
                if stock_code:
                    logger.info(f"📊 [AKShare-PE计算-第1层] 尝试使用实时PE/PB计算: {stock_code}")

                    get_database_manager = getattr(
                        importlib.import_module("trader.config.databases"),
                        "get_database_manager",
                    )
                    get_pe_pb_with_fallback = getattr(
                        importlib.import_module("trader.flows.metrics"),
                        "get_pe_pb_with_fallback",
                    )

                    db_manager = get_database_manager()
                    if db_manager.is_postgres_available():
                        client = db_manager.get_postgres_client()

                        # 获取实时PE/PB
                        realtime_metrics = get_pe_pb_with_fallback(stock_code, client)

                        if realtime_metrics:
                            # 获取总市值
                            market_cap = realtime_metrics.get("market_cap")
                            if market_cap is not None and market_cap > 0:
                                is_realtime = realtime_metrics.get("is_realtime", False)
                                realtime_tag = " (实时)" if is_realtime else ""
                                metrics["total_mv"] = f"{market_cap:.2f}亿元{realtime_tag}"
                                logger.info(
                                    f"✅ [AKShare-总市值获取成功] 总市值={market_cap:.2f}亿元 | 实时={is_realtime}"
                                )

                            # 使用实时PE
                            pe_value = realtime_metrics.get("pe")
                            if pe_value is not None and pe_value > 0:
                                is_realtime = realtime_metrics.get("is_realtime", False)
                                realtime_tag = " (实时)" if is_realtime else ""
                                metrics["pe"] = f"{pe_value:.1f}倍{realtime_tag}"
                                logger.info(
                                    f"✅ [AKShare-PE计算-第1层成功] PE={pe_value:.2f}倍 | 来源={realtime_metrics.get('source')} | 实时={is_realtime}"
                                )

                            # 使用实时PE_TTM
                            pe_ttm_value = realtime_metrics.get("pe_ttm")
                            if pe_ttm_value is not None and pe_ttm_value > 0:
                                is_realtime = realtime_metrics.get("is_realtime", False)
                                realtime_tag = " (实时)" if is_realtime else ""
                                metrics["pe_ttm"] = f"{pe_ttm_value:.1f}倍{realtime_tag}"
                                logger.info(f"✅ [AKShare-PE_TTM计算-第1层成功] PE_TTM={pe_ttm_value:.2f}倍")

                            # 使用实时PB
                            pb_value = realtime_metrics.get("pb")
                            if pb_value is not None and pb_value > 0:
                                is_realtime = realtime_metrics.get("is_realtime", False)
                                realtime_tag = " (实时)" if is_realtime else ""
                                metrics["pb"] = f"{pb_value:.2f}倍{realtime_tag}"
                                logger.info(f"✅ [AKShare-PB计算-第1层成功] PB={pb_value:.2f}倍")
                        else:
                            logger.warning("⚠️ [AKShare-PE计算-第1层失败] 实时计算返回空结果，将尝试降级计算")
            except Exception as e:
                logger.warning(f"⚠️ [AKShare-PE计算-第1层异常] 实时计算失败: {e}，将尝试降级计算")

            # 获取ROE - 直接从指标中获取
            roe_value = indicators_dict.get("净资产收益率(ROE)")
            if roe_value is not None and str(roe_value) != "nan" and roe_value != "--":
                try:
                    roe_val = float(roe_value)
                    # ROE通常是百分比形式
                    metrics["roe"] = f"{roe_val:.1f}%"
                    logger.debug(f"✅ 获取ROE: {metrics['roe']}")
                except (ValueError, TypeError):
                    metrics["roe"] = "N/A"
            else:
                metrics["roe"] = "N/A"

            # 如果实时计算失败，尝试从 stock_info 获取总市值
            if "total_mv" not in metrics:
                logger.info("📊 [AKShare-总市值-第2层] 尝试从 stock_info 获取")
                total_mv_static = stock_info.get("total_mv")
                if total_mv_static is not None and total_mv_static > 0:
                    metrics["total_mv"] = f"{total_mv_static:.2f}亿元"
                    logger.info(f"✅ [AKShare-总市值-第2层成功] 总市值={total_mv_static:.2f}亿元")
                else:
                    metrics["total_mv"] = "N/A"
                    logger.warning("⚠️ [AKShare-总市值-全部失败] 无可用总市值数据")

            # 🔥 如果实时计算失败，降级到传统计算方式
            if pe_value is None:
                logger.info("📊 [AKShare-PE计算-第2层] 尝试使用股价/EPS计算")

                # 计算 PE - 优先使用 TTM 数据
                # 尝试从 main_indicators DataFrame 计算 TTM EPS
                ttm_eps = None
                try:
                    # main_indicators 是 DataFrame，包含多期数据
                    # 尝试计算 TTM EPS
                    if "基本每股收益" in main_indicators["指标"].values:
                        # 提取基本每股收益的所有期数数据
                        eps_row = main_indicators[main_indicators["指标"] == "基本每股收益"]
                        if not eps_row.empty:
                            # 获取所有数值列（排除'指标'列）
                            value_cols = [col for col in eps_row.columns if col != "指标"]

                            # 构建 DataFrame 用于 TTM 计算
                            pd = importlib.import_module("pandas")
                            eps_data = []
                            for col in value_cols:
                                eps_val = cast(Any, eps_row[col]).iloc[0]
                                if eps_val is not None and str(eps_val) != "nan" and eps_val != "--":
                                    eps_data.append({"报告期": col, "基本每股收益": eps_val})

                            if len(eps_data) >= 2:
                                eps_df = pd.DataFrame(eps_data)
                                # 使用 TTM 计算函数
                                _calculate_ttm_metric = getattr(
                                    importlib.import_module("scripts.sync.financial.data.script"),
                                    "_calculate_ttm_metric",
                                )
                                ttm_eps = _calculate_ttm_metric(eps_df, "基本每股收益")
                                if ttm_eps:
                                    logger.info(f"✅ 计算 TTM EPS: {ttm_eps:.4f} 元")
                except Exception as e:
                    logger.debug(f"计算 TTM EPS 失败: {e}")

                # 使用 TTM EPS 或单期 EPS 计算 PE
                eps_for_pe = ttm_eps if ttm_eps else None
                pe_type = "TTM" if ttm_eps else "单期"

                if not eps_for_pe:
                    # 降级到单期 EPS
                    eps_value = indicators_dict.get("基本每股收益")
                    if eps_value is not None and str(eps_value) != "nan" and eps_value != "--":
                        try:
                            eps_for_pe = float(eps_value)
                        except (ValueError, TypeError):
                            pass

                if eps_for_pe and eps_for_pe > 0:
                    pe_val = price_value / eps_for_pe
                    metrics["pe"] = f"{pe_val:.1f}倍"
                    logger.info(
                        f"✅ [AKShare-PE计算-第2层成功] PE({pe_type}): 股价{price_value} / EPS{eps_for_pe:.4f} = {metrics['pe']}"
                    )
                elif eps_for_pe and eps_for_pe <= 0:
                    metrics["pe"] = "N/A（亏损）"
                    logger.warning(f"⚠️ [AKShare-PE计算-第2层失败] 亏损股票，EPS={eps_for_pe}")
                else:
                    metrics["pe"] = "N/A"
                    logger.error("❌ [AKShare-PE计算-全部失败] 无可用EPS数据")

            # 🔥 如果实时PB计算失败，降级到传统计算方式
            if pb_value is None:
                logger.info("📊 [AKShare-PB计算-第2层] 尝试使用股价/BPS计算")

                # 获取每股净资产 - 用于计算PB
                bps_value = indicators_dict.get("每股净资产_最新股数")
                if bps_value is not None and str(bps_value) != "nan" and bps_value != "--":
                    try:
                        bps_val = float(bps_value)
                        if bps_val > 0:
                            # 计算PB = 股价 / 每股净资产
                            pb_val = price_value / bps_val
                            metrics["pb"] = f"{pb_val:.2f}倍"
                            logger.info(
                                f"✅ [AKShare-PB计算-第2层成功] PB: 股价{price_value} / BPS{bps_val} = {metrics['pb']}"
                            )
                        else:
                            metrics["pb"] = "N/A"
                            logger.warning(f"⚠️ [AKShare-PB计算-第2层失败] BPS无效: {bps_val}")
                    except (ValueError, TypeError) as e:
                        metrics["pb"] = "N/A"
                        logger.error(f"❌ [AKShare-PB计算-第2层异常] {e}")
                else:
                    metrics["pb"] = "N/A"
                    logger.error("❌ [AKShare-PB计算-全部失败] 无可用BPS数据")

            # 尝试获取其他指标
            # 总资产收益率(ROA)
            roa_value = indicators_dict.get("总资产报酬率")
            if roa_value is not None and str(roa_value) != "nan" and roa_value != "--":
                try:
                    roa_val = float(roa_value)
                    metrics["roa"] = f"{roa_val:.1f}%"
                except (ValueError, TypeError):
                    metrics["roa"] = "N/A"
            else:
                metrics["roa"] = "N/A"

            # 毛利率
            gross_margin_value = indicators_dict.get("毛利率")
            if gross_margin_value is not None and str(gross_margin_value) != "nan" and gross_margin_value != "--":
                try:
                    gross_margin_val = float(gross_margin_value)
                    metrics["gross_margin"] = f"{gross_margin_val:.1f}%"
                except (ValueError, TypeError):
                    metrics["gross_margin"] = "N/A"
            else:
                metrics["gross_margin"] = "N/A"

            # 销售净利率
            net_margin_value = indicators_dict.get("销售净利率")
            if net_margin_value is not None and str(net_margin_value) != "nan" and net_margin_value != "--":
                try:
                    net_margin_val = float(net_margin_value)
                    metrics["net_margin"] = f"{net_margin_val:.1f}%"
                except (ValueError, TypeError):
                    metrics["net_margin"] = "N/A"
            else:
                metrics["net_margin"] = "N/A"

            # 资产负债率
            debt_ratio_value = indicators_dict.get("资产负债率")
            if debt_ratio_value is not None and str(debt_ratio_value) != "nan" and debt_ratio_value != "--":
                try:
                    debt_ratio_val = float(debt_ratio_value)
                    metrics["debt_ratio"] = f"{debt_ratio_val:.1f}%"
                except (ValueError, TypeError):
                    metrics["debt_ratio"] = "N/A"
            else:
                metrics["debt_ratio"] = "N/A"

            # 流动比率
            current_ratio_value = indicators_dict.get("流动比率")
            if current_ratio_value is not None and str(current_ratio_value) != "nan" and current_ratio_value != "--":
                try:
                    current_ratio_val = float(current_ratio_value)
                    metrics["current_ratio"] = f"{current_ratio_val:.2f}"
                except (ValueError, TypeError):
                    metrics["current_ratio"] = "N/A"
            else:
                metrics["current_ratio"] = "N/A"

            # 速动比率
            quick_ratio_value = indicators_dict.get("速动比率")
            if quick_ratio_value is not None and str(quick_ratio_value) != "nan" and quick_ratio_value != "--":
                try:
                    quick_ratio_val = float(quick_ratio_value)
                    metrics["quick_ratio"] = f"{quick_ratio_val:.2f}"
                except (ValueError, TypeError):
                    metrics["quick_ratio"] = "N/A"
            else:
                metrics["quick_ratio"] = "N/A"

            # 计算 PS - 市销率（优先使用 TTM 营业收入）
            # 尝试从 main_indicators DataFrame 计算 TTM 营业收入
            ttm_revenue = None
            try:
                if "营业收入" in main_indicators["指标"].values:
                    revenue_row = main_indicators[main_indicators["指标"] == "营业收入"]
                    if not revenue_row.empty:
                        value_cols = [col for col in revenue_row.columns if col != "指标"]

                        pd = importlib.import_module("pandas")
                        revenue_data = []
                        for col in value_cols:
                            rev_val = cast(Any, revenue_row[col]).iloc[0]
                            if rev_val is not None and str(rev_val) != "nan" and rev_val != "--":
                                revenue_data.append({"报告期": col, "营业收入": rev_val})

                        if len(revenue_data) >= 2:
                            revenue_df = pd.DataFrame(revenue_data)
                            _calculate_ttm_metric = getattr(
                                importlib.import_module("scripts.sync.financial.data.script"),
                                "_calculate_ttm_metric",
                            )
                            ttm_revenue = _calculate_ttm_metric(revenue_df, "营业收入")
                            if ttm_revenue:
                                logger.info(f"✅ 计算 TTM 营业收入: {ttm_revenue:.2f} 万元")
            except Exception as e:
                logger.debug(f"计算 TTM 营业收入失败: {e}")

            # 计算 PS
            revenue_for_ps = ttm_revenue if ttm_revenue else None
            ps_type = "TTM" if ttm_revenue else "单期"

            if not revenue_for_ps:
                # 降级到单期营业收入
                revenue_value = indicators_dict.get("营业收入")
                if revenue_value is not None and str(revenue_value) != "nan" and revenue_value != "--":
                    try:
                        revenue_for_ps = float(revenue_value)
                    except (ValueError, TypeError):
                        pass

            if revenue_for_ps and revenue_for_ps > 0:
                # 获取总股本计算市值
                total_share = stock_info.get("total_share") if stock_info else None
                if total_share and total_share > 0:
                    # 市值（万元）= 股价（元）× 总股本（万股）
                    market_cap = price_value * total_share
                    ps_val = market_cap / revenue_for_ps
                    metrics["ps"] = f"{ps_val:.2f}倍"
                    logger.info(
                        f"✅ 计算PS({ps_type}): 市值{market_cap:.2f}万元 / 营业收入{revenue_for_ps:.2f}万元 = {metrics['ps']}"
                    )
                else:
                    metrics["ps"] = "N/A（无总股本数据）"
                    logger.warning("⚠️ 无法计算PS: 缺少总股本数据")
            else:
                metrics["ps"] = "N/A"

            # 补充其他指标的默认值
            metrics.update({"dividend_yield": "待查询", "cash_ratio": "待分析"})

            # 评分（基于AKShare数据的简化评分）
            fundamental_score = self._calculate_fundamental_score(metrics, stock_info)
            valuation_score = self._calculate_valuation_score(metrics)
            growth_score = self._calculate_growth_score(metrics, stock_info)
            risk_level = self._calculate_risk_level(metrics, stock_info)

            metrics.update({
                "fundamental_score": fundamental_score,
                "valuation_score": valuation_score,
                "growth_score": growth_score,
                "risk_level": risk_level,
                "data_source": "AKShare",
            })

            logger.info(f"✅ AKShare财务数据解析成功: PE={metrics['pe']}, PB={metrics['pb']}, ROE={metrics['roe']}")
            return metrics

        except Exception as e:
            logger.error(f"❌ AKShare财务数据解析失败: {e}")
            return None

    def _parse_financial_data(
        self, financial_data: dict, stock_info: Optional[dict], price_value: float
    ) -> Optional[dict]:
        """解析财务数据为指标"""
        try:
            stock_info = stock_info or {}

            # 获取最新的财务数据
            balance_sheet = financial_data.get("balance_sheet", [])
            income_statement = financial_data.get("income_statement", [])
            cash_flow = financial_data.get("cash_flow", [])

            if not (balance_sheet or income_statement):
                return None

            latest_balance = balance_sheet[0] if balance_sheet else {}
            latest_income = income_statement[0] if income_statement else {}
            cash_flow[0] if cash_flow else {}

            # 计算财务指标
            metrics = {}

            # 基础数据
            total_assets = latest_balance.get("total_assets", 0) or 0
            total_liab = latest_balance.get("total_liab", 0) or 0
            total_equity = latest_balance.get("total_hldr_eqy_exc_min_int", 0) or 0

            # 计算 TTM 营业收入和净利润
            # Tushare income_statement 的数据是累计值（从年初到报告期）
            # 需要使用 TTM 公式计算
            ttm_revenue = None
            ttm_net_income = None

            try:
                if len(income_statement) >= 2:
                    # 准备数据用于 TTM 计算
                    pd = importlib.import_module("pandas")

                    # 构建营业收入 DataFrame
                    revenue_data = []
                    for stmt in income_statement:
                        end_date = stmt.get("end_date")
                        revenue = stmt.get("total_revenue")
                        if end_date and revenue is not None:
                            revenue_data.append({"报告期": str(end_date), "营业收入": float(revenue)})

                    if len(revenue_data) >= 2:
                        revenue_df = pd.DataFrame(revenue_data)
                        _calculate_ttm_metric = getattr(
                            importlib.import_module("scripts.sync.financial.data.script"),
                            "_calculate_ttm_metric",
                        )
                        ttm_revenue = _calculate_ttm_metric(revenue_df, "营业收入")
                        if ttm_revenue:
                            logger.info(f"✅ Tushare 计算 TTM 营业收入: {ttm_revenue:.2f} 万元")

                    # 构建净利润 DataFrame
                    profit_data = []
                    for stmt in income_statement:
                        end_date = stmt.get("end_date")
                        profit = stmt.get("n_income")
                        if end_date and profit is not None:
                            profit_data.append({"报告期": str(end_date), "净利润": float(profit)})

                    if len(profit_data) >= 2:
                        profit_df = pd.DataFrame(profit_data)
                        ttm_net_income = _calculate_ttm_metric(profit_df, "净利润")
                        if ttm_net_income:
                            logger.info(f"✅ Tushare 计算 TTM 净利润: {ttm_net_income:.2f} 万元")
            except Exception as e:
                logger.warning(f"⚠️ Tushare TTM 计算失败: {e}")

            # 降级到单期数据
            total_revenue = ttm_revenue if ttm_revenue else (latest_income.get("total_revenue", 0) or 0)
            net_income = ttm_net_income if ttm_net_income else (latest_income.get("n_income", 0) or 0)
            revenue_type = "TTM" if ttm_revenue else "单期"
            profit_type = "TTM" if ttm_net_income else "单期"

            # 获取实际总股本计算市值
            # 优先从 stock_info 获取，如果没有则无法计算准确的估值指标
            total_share = stock_info.get("total_share") if stock_info else None

            if total_share and total_share > 0:
                # 市值（元）= 股价（元）× 总股本（万股）× 10000
                market_cap = price_value * total_share * 10000
                market_cap_yi = market_cap / 100000000  # 转换为亿元
                metrics["total_mv"] = f"{market_cap_yi:.2f}亿元"
                logger.info(
                    f"✅ [Tushare-总市值计算成功] 总市值={market_cap_yi:.2f}亿元 (股价{price_value}元 × 总股本{total_share}万股)"
                )
            else:
                logger.error(f"❌ {stock_info.get('code', 'Unknown')} 无法获取总股本，无法计算准确的估值指标")
                market_cap = None
                metrics["total_mv"] = "N/A"

            # 计算各项指标（只有在有准确市值时才计算）
            if market_cap:
                # PE比率（优先使用 TTM 净利润）
                if net_income > 0:
                    pe_ratio = market_cap / (net_income * 10000)  # 转换单位
                    metrics["pe"] = f"{pe_ratio:.1f}倍"
                    logger.info(
                        f"✅ Tushare 计算PE({profit_type}): 市值{market_cap / 100000000:.2f}亿元 / 净利润{net_income:.2f}万元 = {pe_ratio:.1f}倍"
                    )
                else:
                    metrics["pe"] = "N/A（亏损）"

                # PB比率（净资产使用最新期数据，相对准确）
                if total_equity > 0:
                    pb_ratio = market_cap / (total_equity * 10000)
                    metrics["pb"] = f"{pb_ratio:.2f}倍"
                else:
                    metrics["pb"] = "N/A"

                # PS比率（优先使用 TTM 营业收入）
                if total_revenue > 0:
                    ps_ratio = market_cap / (total_revenue * 10000)
                    metrics["ps"] = f"{ps_ratio:.1f}倍"
                    logger.info(
                        f"✅ Tushare 计算PS({revenue_type}): 市值{market_cap / 100000000:.2f}亿元 / 营业收入{total_revenue:.2f}万元 = {ps_ratio:.1f}倍"
                    )
                else:
                    metrics["ps"] = "N/A"
            else:
                # 无法获取总股本，无法计算估值指标
                metrics["pe"] = "N/A（无总股本数据）"
                metrics["pb"] = "N/A（无总股本数据）"
                metrics["ps"] = "N/A（无总股本数据）"

            # ROE
            if total_equity > 0 and net_income > 0:
                roe = (net_income / total_equity) * 100
                metrics["roe"] = f"{roe:.1f}%"
            else:
                metrics["roe"] = "N/A"

            # ROA
            if total_assets > 0 and net_income > 0:
                roa = (net_income / total_assets) * 100
                metrics["roa"] = f"{roa:.1f}%"
            else:
                metrics["roa"] = "N/A"

            # 净利率
            if total_revenue > 0 and net_income > 0:
                net_margin = (net_income / total_revenue) * 100
                metrics["net_margin"] = f"{net_margin:.1f}%"
            else:
                metrics["net_margin"] = "N/A"

            # 资产负债率
            if total_assets > 0:
                debt_ratio = (total_liab / total_assets) * 100
                metrics["debt_ratio"] = f"{debt_ratio:.1f}%"
            else:
                metrics["debt_ratio"] = "N/A"

            # 其他指标设为默认值
            metrics.update({
                "dividend_yield": "待查询",
                "gross_margin": "待计算",
                "current_ratio": "待计算",
                "quick_ratio": "待计算",
                "cash_ratio": "待分析",
            })

            # 评分（基于真实数据的简化评分）
            fundamental_score = self._calculate_fundamental_score(metrics, stock_info)
            valuation_score = self._calculate_valuation_score(metrics)
            growth_score = self._calculate_growth_score(metrics, stock_info)
            risk_level = self._calculate_risk_level(metrics, stock_info)

            metrics.update({
                "fundamental_score": fundamental_score,
                "valuation_score": valuation_score,
                "growth_score": growth_score,
                "risk_level": risk_level,
            })

            return metrics

        except Exception as e:
            logger.error(f"解析财务数据失败: {e}")
            return None

    def _calculate_fundamental_score(self, metrics: dict, stock_info: dict) -> float:
        """计算基本面评分"""
        score = 5.0  # 基础分

        # ROE评分
        roe_str = metrics.get("roe", "N/A")
        if roe_str != "N/A":
            try:
                roe = float(roe_str.replace("%", ""))
                if roe > 15:
                    score += 1.5
                elif roe > 10:
                    score += 1.0
                elif roe > 5:
                    score += 0.5
            except Exception:
                pass

        # 净利率评分
        net_margin_str = metrics.get("net_margin", "N/A")
        if net_margin_str != "N/A":
            try:
                net_margin = float(net_margin_str.replace("%", ""))
                if net_margin > 20:
                    score += 1.0
                elif net_margin > 10:
                    score += 0.5
            except Exception:
                pass

        return min(score, 10.0)
