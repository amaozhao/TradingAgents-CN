# ruff: noqa: F401,F403,F405,F821
class _DataSourceManagerMixin4:
    def _get_baostock_stock_info(self, symbol: str) -> Dict:
        """使用BaoStock获取股票基本信息"""
        try:
            bs = importlib.import_module("baostock")

            # 转换股票代码格式
            if symbol.startswith("6"):
                bs_code = f"sh.{symbol}"
            else:
                bs_code = f"sz.{symbol}"

            # 登录BaoStock
            lg = bs.login()
            if lg.error_code != "0":
                logger.error(f"❌ [股票信息] BaoStock登录失败: {lg.error_msg}")
                return {"symbol": symbol, "name": f"股票{symbol}", "source": "baostock"}

            # 查询股票基本信息
            rs = bs.query_stock_basic(code=bs_code)
            if rs.error_code != "0":
                bs.logout()
                logger.error(f"❌ [股票信息] BaoStock查询失败: {rs.error_msg}")
                return {"symbol": symbol, "name": f"股票{symbol}", "source": "baostock"}

            # 解析结果
            data_list = []
            while (rs.error_code == "0") & rs.next():
                data_list.append(rs.get_row_data())

            # 登出
            bs.logout()

            if data_list:
                # BaoStock返回格式: [code, code_name, ipoDate, outDate, type, status]
                info = {"symbol": symbol, "source": "baostock"}
                info["name"] = data_list[0][1]  # code_name
                info["area"] = "未知"  # BaoStock没有地区信息
                info["industry"] = "未知"  # BaoStock没有行业信息
                info["market"] = "未知"  # 可以根据股票代码推断
                info["list_date"] = data_list[0][2]  # ipoDate

                return info
            else:
                return {"symbol": symbol, "name": f"股票{symbol}", "source": "baostock"}

        except Exception as e:
            logger.error(f"❌ [股票信息] BaoStock获取失败: {e}")
            return {
                "symbol": symbol,
                "name": f"股票{symbol}",
                "source": "baostock",
                "error": str(e),
            }

    def _parse_stock_info_string(self, info_str: str, symbol: str) -> Dict:
        """解析股票信息字符串为字典"""
        try:
            info = {"symbol": symbol, "source": self.current_source.value}
            lines = info_str.split("\n")

            for line in lines:
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()

                    if "股票名称" in key:
                        info["name"] = value
                    elif "所属行业" in key:
                        info["industry"] = value
                    elif "所属地区" in key:
                        info["area"] = value
                    elif "上市市场" in key:
                        info["market"] = value
                    elif "上市日期" in key:
                        info["list_date"] = value

            return info

        except Exception as e:
            logger.error(f"⚠️ 解析股票信息失败: {e}")
            return {
                "symbol": symbol,
                "name": f"股票{symbol}",
                "source": self.current_source.value,
            }

    def _get_postgres_fundamentals(self, symbol: str) -> str:
        """从 PostgreSQL 获取财务数据"""
        logger.debug(f"📊 [PostgreSQL] 调用参数: symbol={symbol}")

        try:
            get_postgres_cache_adapter = getattr(
                importlib.import_module("trader.flows.cache.postgres"),
                "get_postgres_cache_adapter",
            )
            pd = importlib.import_module("pandas")
            adapter = get_postgres_cache_adapter()

            # 从 PostgreSQL 获取财务数据
            financial_data = adapter.get_financial_data(symbol)

            # 检查数据类型和内容
            if financial_data is not None:
                # 如果是 DataFrame，转换为字典列表
                if isinstance(financial_data, pd.DataFrame):
                    if not financial_data.empty:
                        logger.info(
                            f"✅ [数据来源: PostgreSQL-财务数据] 成功获取: {symbol} ({len(financial_data)}条记录)"
                        )
                        # 转换为字典列表
                        financial_dict_list = financial_data.to_dict("records")
                        # 格式化财务数据为报告
                        return self._format_financial_data(symbol, financial_dict_list)
                    else:
                        logger.warning(
                            f"⚠️ [数据来源: PostgreSQL] 财务数据为空: {symbol}，降级到其他数据源"
                        )
                        return self._try_fallback_fundamentals(symbol)
                # 如果是列表
                elif isinstance(financial_data, list) and len(financial_data) > 0:
                    logger.info(
                        f"✅ [数据来源: PostgreSQL-财务数据] 成功获取: {symbol} ({len(financial_data)}条记录)"
                    )
                    return self._format_financial_data(symbol, financial_data)
                # 如果是单个字典（这是PostgreSQL实际返回的格式）
                elif isinstance(financial_data, dict):
                    logger.info(
                        f"✅ [数据来源: PostgreSQL-财务数据] 成功获取: {symbol} (单条记录)"
                    )
                    # 将单个字典包装成列表
                    financial_dict_list = [financial_data]
                    return self._format_financial_data(symbol, financial_dict_list)
                else:
                    logger.warning(
                        f"⚠️ [数据来源: PostgreSQL] 未找到财务数据: {symbol}，降级到其他数据源"
                    )
                    return self._try_fallback_fundamentals(symbol)
            else:
                logger.warning(
                    f"⚠️ [数据来源: PostgreSQL] 未找到财务数据: {symbol}，降级到其他数据源"
                )
                # PostgreSQL 没有数据，降级到其他数据源
                return self._try_fallback_fundamentals(symbol)

        except Exception as e:
            logger.error(
                f"❌ [数据来源: PostgreSQL异常] 获取财务数据失败: {e}", exc_info=True
            )
            # PostgreSQL 异常，降级到其他数据源
            return self._try_fallback_fundamentals(symbol)

    def _get_tushare_fundamentals(self, symbol: str) -> str:
        """从 Tushare 获取基本面数据 - 暂时不可用，需要实现"""
        logger.warning("⚠️ Tushare基本面数据功能暂时不可用")
        return "⚠️ Tushare基本面数据功能暂时不可用，请使用其他数据源"

    def _get_akshare_fundamentals(self, symbol: str) -> str:
        """从 AKShare 生成基本面分析"""
        logger.debug(f"📊 [AKShare] 调用参数: symbol={symbol}")

        try:
            # AKShare 没有直接的基本面数据接口，使用生成分析
            logger.info(f"📊 [数据来源: AKShare-生成分析] 生成基本面分析: {symbol}")
            return self._generate_fundamentals_analysis(symbol)

        except Exception as e:
            logger.error(f"❌ [数据来源: AKShare异常] 生成基本面分析失败: {e}")
            return f"❌ 生成{symbol}基本面分析失败: {e}"

    def _get_valuation_indicators(self, symbol: str) -> Dict:
        """从stock_basic_info集合获取估值指标"""
        try:
            db_manager = get_database_manager()
            if not db_manager.is_postgres_available():
                return {}

            client = db_manager.get_postgres_client()
            if client is None:
                return {}
            manager_config = cast(Any, db_manager).config
            db = client[manager_config.postgres_config.database_name]

            # 从stock_basic_info集合获取估值指标
            collection = db["stock_basic_info"]
            result = collection.find_one({"ts_code": symbol})

            if result:
                return {
                    "pe": result.get("pe"),
                    "pb": result.get("pb"),
                    "pe_ttm": result.get("pe_ttm"),
                    "total_mv": result.get("total_mv"),
                    "circ_mv": result.get("circ_mv"),
                }
            return {}

        except Exception as e:
            logger.error(f"获取{symbol}估值指标失败: {e}")
            return {}

    def _format_financial_data(self, symbol: str, financial_data: List[Dict]) -> str:
        """格式化财务数据为报告"""
        try:
            if not financial_data or len(financial_data) == 0:
                return f"❌ 未找到{symbol}的财务数据"

            # 获取最新的财务数据
            latest = financial_data[0]

            # 构建报告
            report = f"📊 {symbol} 基本面数据（来自PostgreSQL）\n\n"

            # 基本信息
            report += f"📅 报告期: {latest.get('report_period', latest.get('end_date', '未知'))}\n"
            report += "📈 数据来源: PostgreSQL财务数据库\n\n"

            # 财务指标
            report += "💰 财务指标:\n"
            revenue = latest.get("revenue") or latest.get("total_revenue")
            if revenue is not None:
                report += f"   营业总收入: {revenue:,.2f}\n"

            net_profit = latest.get("net_profit") or latest.get("net_income")
            if net_profit is not None:
                report += f"   净利润: {net_profit:,.2f}\n"

            total_assets = latest.get("total_assets")
            if total_assets is not None:
                report += f"   总资产: {total_assets:,.2f}\n"

            total_liab = latest.get("total_liab")
            if total_liab is not None:
                report += f"   总负债: {total_liab:,.2f}\n"

            total_equity = latest.get("total_equity")
            if total_equity is not None:
                report += f"   股东权益: {total_equity:,.2f}\n"

            # 估值指标 - 从stock_basic_info集合获取
            report += "\n📊 估值指标:\n"
            valuation_data = self._get_valuation_indicators(symbol)
            if valuation_data:
                pe = valuation_data.get("pe")
                if pe is not None:
                    report += f"   市盈率(PE): {pe:.2f}\n"

                pb = valuation_data.get("pb")
                if pb is not None:
                    report += f"   市净率(PB): {pb:.2f}\n"

                pe_ttm = valuation_data.get("pe_ttm")
                if pe_ttm is not None:
                    report += f"   市盈率TTM(PE_TTM): {pe_ttm:.2f}\n"

                total_mv = valuation_data.get("total_mv")
                if total_mv is not None:
                    report += f"   总市值: {total_mv:.2f}亿元\n"

                circ_mv = valuation_data.get("circ_mv")
                if circ_mv is not None:
                    report += f"   流通市值: {circ_mv:.2f}亿元\n"
            else:
                # 如果无法从stock_basic_info获取，尝试从财务数据计算
                pe = latest.get("pe")
                if pe is not None:
                    report += f"   市盈率(PE): {pe:.2f}\n"

                pb = latest.get("pb")
                if pb is not None:
                    report += f"   市净率(PB): {pb:.2f}\n"

                ps = latest.get("ps")
                if ps is not None:
                    report += f"   市销率(PS): {ps:.2f}\n"

            # 盈利能力
            report += "\n💹 盈利能力:\n"
            roe = latest.get("roe")
            if roe is not None:
                report += f"   净资产收益率(ROE): {roe:.2f}%\n"

            roa = latest.get("roa")
            if roa is not None:
                report += f"   总资产收益率(ROA): {roa:.2f}%\n"

            gross_margin = latest.get("gross_margin")
            if gross_margin is not None:
                report += f"   毛利率: {gross_margin:.2f}%\n"

            netprofit_margin = latest.get("netprofit_margin") or latest.get(
                "net_margin"
            )
            if netprofit_margin is not None:
                report += f"   净利率: {netprofit_margin:.2f}%\n"

            # 现金流
            n_cashflow_act = latest.get("n_cashflow_act")
            if n_cashflow_act is not None:
                report += "\n💰 现金流:\n"
                report += f"   经营活动现金流: {n_cashflow_act:,.2f}\n"

                n_cashflow_inv_act = latest.get("n_cashflow_inv_act")
                if n_cashflow_inv_act is not None:
                    report += f"   投资活动现金流: {n_cashflow_inv_act:,.2f}\n"

                c_cash_equ_end_period = latest.get("c_cash_equ_end_period")
                if c_cash_equ_end_period is not None:
                    report += f"   期末现金及等价物: {c_cash_equ_end_period:,.2f}\n"

            report += f"\n📝 共有 {len(financial_data)} 期财务数据\n"

            return report

        except Exception as e:
            logger.error(f"❌ 格式化财务数据失败: {e}")
            return f"❌ 格式化{symbol}财务数据失败: {e}"

    def _generate_fundamentals_analysis(self, symbol: str) -> str:
        """生成基本的基本面分析"""
        try:
            # 获取股票基本信息
            stock_info = self.get_stock_info(symbol)

            report = f"📊 {symbol} 基本面分析（生成）\n\n"
            report += f"📈 股票名称: {stock_info.get('name', '未知')}\n"
            report += f"🏢 所属行业: {stock_info.get('industry', '未知')}\n"
            report += f"📍 所属地区: {stock_info.get('area', '未知')}\n"
            report += f"📅 上市日期: {stock_info.get('list_date', '未知')}\n"
            report += f"🏛️ 交易所: {stock_info.get('exchange', '未知')}\n\n"

            report += "⚠️ 注意: 详细财务数据需要从数据源获取\n"
            report += "💡 建议: 启用PostgreSQL缓存以获取完整的财务数据\n"

            return report

        except Exception as e:
            logger.error(f"❌ 生成基本面分析失败: {e}")
            return f"❌ 生成{symbol}基本面分析失败: {e}"

    def _try_fallback_fundamentals(self, symbol: str) -> str:
        """基本面数据降级处理"""
        logger.error(f"🔄 {self.current_source.value}失败，尝试备用数据源获取基本面...")

        # 🔥 从数据库获取数据源优先级顺序（根据股票代码识别市场）
        fallback_order = self._get_data_source_priority_order(symbol)

        for source in fallback_order:
            if source != self.current_source and source in self.available_sources:
                try:
                    logger.info(f"🔄 尝试备用数据源获取基本面: {source.value}")

                    # 直接调用具体的数据源方法，避免递归
                    if source == ChinaDataSource.TUSHARE:
                        result = self._get_tushare_fundamentals(symbol)
                    elif source == ChinaDataSource.AKSHARE:
                        result = self._get_akshare_fundamentals(symbol)
                    else:
                        continue

                    if result and "❌" not in result:
                        logger.info(
                            f"✅ [数据来源: 备用数据源] 降级成功获取基本面: {source.value}"
                        )
                        return result
                    else:
                        logger.warning(f"⚠️ 备用数据源{source.value}返回错误结果")

                except Exception as e:
                    logger.error(f"❌ 备用数据源{source.value}异常: {e}")
                    continue

        # 所有数据源都失败，生成基本分析
        logger.warning(f"⚠️ [数据来源: 生成分析] 所有数据源失败，生成基本分析: {symbol}")
        return self._generate_fundamentals_analysis(symbol)

    def _get_postgres_news(
        self, symbol: str, hours_back: int, limit: int
    ) -> List[Dict[str, Any]]:
        """从PostgreSQL获取新闻数据"""
        try:
            get_postgres_cache_adapter = getattr(
                importlib.import_module("trader.flows.cache.postgres"),
                "get_postgres_cache_adapter",
            )
            adapter = get_postgres_cache_adapter()

            # 从PostgreSQL获取新闻数据
            news_data = adapter.get_news_data(
                symbol, hours_back=hours_back, limit=limit
            )

            if news_data and len(news_data) > 0:
                logger.info(
                    f"✅ [数据来源: PostgreSQL-新闻] 成功获取: {symbol or '市场新闻'} ({len(news_data)}条)"
                )
                return news_data
            else:
                logger.warning(
                    f"⚠️ [数据来源: PostgreSQL] 未找到新闻: {symbol or '市场新闻'}，降级到其他数据源"
                )
                return self._try_fallback_news(symbol, hours_back, limit)

        except Exception as e:
            logger.error(f"❌ [数据来源: PostgreSQL] 获取新闻失败: {e}")
            return self._try_fallback_news(symbol, hours_back, limit)

    def _get_tushare_news(
        self, symbol: str, hours_back: int, limit: int
    ) -> List[Dict[str, Any]]:
        """从Tushare获取新闻数据"""
        try:
            # Tushare新闻功能暂时不可用，返回空列表
            logger.warning("⚠️ [数据来源: Tushare] Tushare新闻功能暂时不可用")
            return []

        except Exception as e:
            logger.error(f"❌ [数据来源: Tushare] 获取新闻失败: {e}")
            return []

    def _get_akshare_news(
        self, symbol: str, hours_back: int, limit: int
    ) -> List[Dict[str, Any]]:
        """从AKShare获取新闻数据"""
        try:
            # AKShare新闻功能暂时不可用，返回空列表
            logger.warning("⚠️ [数据来源: AKShare] AKShare新闻功能暂时不可用")
            return []

        except Exception as e:
            logger.error(f"❌ [数据来源: AKShare] 获取新闻失败: {e}")
            return []

    def _try_fallback_news(
        self, symbol: str, hours_back: int, limit: int
    ) -> List[Dict[str, Any]]:
        """新闻数据降级处理"""
        logger.error(f"🔄 {self.current_source.value}失败，尝试备用数据源获取新闻...")

        # 🔥 从数据库获取数据源优先级顺序（根据股票代码识别市场）
        fallback_order = self._get_data_source_priority_order(symbol)

        for source in fallback_order:
            if source != self.current_source and source in self.available_sources:
                try:
                    logger.info(f"🔄 尝试备用数据源获取新闻: {source.value}")

                    # 直接调用具体的数据源方法，避免递归
                    if source == ChinaDataSource.TUSHARE:
                        result = self._get_tushare_news(symbol, hours_back, limit)
                    elif source == ChinaDataSource.AKSHARE:
                        result = self._get_akshare_news(symbol, hours_back, limit)
                    else:
                        continue

                    if result and len(result) > 0:
                        logger.info(
                            f"✅ [数据来源: 备用数据源] 降级成功获取新闻: {source.value}"
                        )
                        return result
                    else:
                        logger.warning(f"⚠️ 备用数据源{source.value}未返回新闻")

                except Exception as e:
                    logger.error(f"❌ 备用数据源{source.value}异常: {e}")
                    continue

        # 所有数据源都失败
        logger.warning(
            f"⚠️ [数据来源: 所有数据源失败] 无法获取新闻: {symbol or '市场新闻'}"
        )
        return []
