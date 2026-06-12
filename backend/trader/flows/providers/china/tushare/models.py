from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .imports import (
        Any,
        Dict,
        Optional,
        UTC,
        datetime,
        pd,
    )

class _TushareProviderMixin3:
    def _standardize_historical_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化历史数据"""
        # 重命名列
        column_mapping = {"trade_date": "date", "vol": "volume"}
        df = df.rename(columns=column_mapping)

        # 格式化日期
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
            df.set_index("date", inplace=True)

        # 按日期排序
        df = df.sort_index()

        return df

    def _standardize_tushare_financial_data(self, financial_data: Dict[str, Any], ts_code: str) -> Dict[str, Any]:
        """
        标准化Tushare财务数据

        Args:
            financial_data: 原始财务数据字典
            ts_code: Tushare股票代码

        Returns:
            标准化后的财务数据
        """
        try:
            # 获取最新的数据记录（第一条记录通常是最新的）
            latest_income = (
                financial_data.get("income_statement", [{}])[0] if financial_data.get("income_statement") else {}
            )
            latest_balance = financial_data.get("balance_sheet", [{}])[0] if financial_data.get("balance_sheet") else {}
            latest_cashflow = (
                financial_data.get("cashflow_statement", [{}])[0] if financial_data.get("cashflow_statement") else {}
            )
            latest_indicator = (
                financial_data.get("financial_indicators", [{}])[0]
                if financial_data.get("financial_indicators")
                else {}
            )

            # 提取基础信息
            symbol = ts_code.split(".")[0] if "." in ts_code else ts_code
            report_period = str(
                latest_income.get("end_date") or latest_balance.get("end_date") or latest_cashflow.get("end_date") or ""
            )
            ann_date = (
                latest_income.get("ann_date") or latest_balance.get("ann_date") or latest_cashflow.get("ann_date")
            )

            # 计算 TTM 数据
            income_statements = financial_data.get("income_statement", [])
            revenue_ttm = self._calculate_ttm_from_tushare(income_statements, "revenue")
            net_profit_ttm = self._calculate_ttm_from_tushare(income_statements, "n_income_attr_p")

            standardized_data = {
                # 基础信息
                "symbol": symbol,
                "ts_code": ts_code,
                "report_period": report_period,
                "ann_date": ann_date,
                "report_type": self._determine_report_type(report_period),
                # 利润表核心指标
                "revenue": self._safe_float(latest_income.get("revenue")),  # 营业收入（单期）
                "revenue_ttm": revenue_ttm,  # 营业收入（TTM）
                "oper_rev": self._safe_float(latest_income.get("oper_rev")),  # 营业收入
                "net_income": self._safe_float(latest_income.get("n_income")),  # 净利润（单期）
                "net_profit": self._safe_float(latest_income.get("n_income_attr_p")),  # 归属母公司净利润（单期）
                "net_profit_ttm": net_profit_ttm,  # 归属母公司净利润（TTM）
                "oper_profit": self._safe_float(latest_income.get("oper_profit")),  # 营业利润
                "total_profit": self._safe_float(latest_income.get("total_profit")),  # 利润总额
                "oper_cost": self._safe_float(latest_income.get("oper_cost")),  # 营业成本
                "oper_exp": self._safe_float(latest_income.get("oper_exp")),  # 营业费用
                "admin_exp": self._safe_float(latest_income.get("admin_exp")),  # 管理费用
                "fin_exp": self._safe_float(latest_income.get("fin_exp")),  # 财务费用
                "rd_exp": self._safe_float(latest_income.get("rd_exp")),  # 研发费用
                # 资产负债表核心指标
                "total_assets": self._safe_float(latest_balance.get("total_assets")),  # 总资产
                "total_liab": self._safe_float(latest_balance.get("total_liab")),  # 总负债
                "total_equity": self._safe_float(latest_balance.get("total_hldr_eqy_exc_min_int")),  # 股东权益
                "total_cur_assets": self._safe_float(latest_balance.get("total_cur_assets")),  # 流动资产
                "total_nca": self._safe_float(latest_balance.get("total_nca")),  # 非流动资产
                "total_cur_liab": self._safe_float(latest_balance.get("total_cur_liab")),  # 流动负债
                "total_ncl": self._safe_float(latest_balance.get("total_ncl")),  # 非流动负债
                "money_cap": self._safe_float(latest_balance.get("money_cap")),  # 货币资金
                "accounts_receiv": self._safe_float(latest_balance.get("accounts_receiv")),  # 应收账款
                "inventories": self._safe_float(latest_balance.get("inventories")),  # 存货
                "fix_assets": self._safe_float(latest_balance.get("fix_assets")),  # 固定资产
                # 现金流量表核心指标
                "n_cashflow_act": self._safe_float(latest_cashflow.get("n_cashflow_act")),  # 经营活动现金流
                "n_cashflow_inv_act": self._safe_float(latest_cashflow.get("n_cashflow_inv_act")),  # 投资活动现金流
                "n_cashflow_fin_act": self._safe_float(latest_cashflow.get("n_cashflow_fin_act")),  # 筹资活动现金流
                "c_cash_equ_end_period": self._safe_float(latest_cashflow.get("c_cash_equ_end_period")),  # 期末现金
                "c_cash_equ_beg_period": self._safe_float(latest_cashflow.get("c_cash_equ_beg_period")),  # 期初现金
                # 财务指标
                "roe": self._safe_float(latest_indicator.get("roe")),  # 净资产收益率
                "roa": self._safe_float(latest_indicator.get("roa")),  # 总资产收益率
                "roe_waa": self._safe_float(latest_indicator.get("roe_waa")),  # 加权平均净资产收益率
                "roe_dt": self._safe_float(latest_indicator.get("roe_dt")),  # 净资产收益率(扣除非经常损益)
                "roa2": self._safe_float(latest_indicator.get("roa2")),  # 总资产收益率(扣除非经常损益)
                "gross_margin": self._safe_float(
                    latest_indicator.get("grossprofit_margin")
                ),  # 🔥 修复：使用 grossprofit_margin（销售毛利率%）而不是 gross_margin（毛利绝对值）
                "netprofit_margin": self._safe_float(latest_indicator.get("netprofit_margin")),  # 销售净利率
                "cogs_of_sales": self._safe_float(latest_indicator.get("cogs_of_sales")),  # 销售成本率
                "expense_of_sales": self._safe_float(latest_indicator.get("expense_of_sales")),  # 销售期间费用率
                "profit_to_gr": self._safe_float(latest_indicator.get("profit_to_gr")),  # 净利润/营业总收入
                "saleexp_to_gr": self._safe_float(latest_indicator.get("saleexp_to_gr")),  # 销售费用/营业总收入
                "adminexp_of_gr": self._safe_float(latest_indicator.get("adminexp_of_gr")),  # 管理费用/营业总收入
                "finaexp_of_gr": self._safe_float(latest_indicator.get("finaexp_of_gr")),  # 财务费用/营业总收入
                "debt_to_assets": self._safe_float(latest_indicator.get("debt_to_assets")),  # 资产负债率
                "assets_to_eqt": self._safe_float(latest_indicator.get("assets_to_eqt")),  # 权益乘数
                "dp_assets_to_eqt": self._safe_float(latest_indicator.get("dp_assets_to_eqt")),  # 权益乘数(杜邦分析)
                "ca_to_assets": self._safe_float(latest_indicator.get("ca_to_assets")),  # 流动资产/总资产
                "nca_to_assets": self._safe_float(latest_indicator.get("nca_to_assets")),  # 非流动资产/总资产
                "current_ratio": self._safe_float(latest_indicator.get("current_ratio")),  # 流动比率
                "quick_ratio": self._safe_float(latest_indicator.get("quick_ratio")),  # 速动比率
                "cash_ratio": self._safe_float(latest_indicator.get("cash_ratio")),  # 现金比率
                # 原始数据保留（用于详细分析）
                "raw_data": {
                    "income_statement": financial_data.get("income_statement", []),
                    "balance_sheet": financial_data.get("balance_sheet", []),
                    "cashflow_statement": financial_data.get("cashflow_statement", []),
                    "financial_indicators": financial_data.get("financial_indicators", []),
                    "main_business": financial_data.get("main_business", []),
                },
                # 元数据
                "data_source": "tushare",
                "updated_at": datetime.now(UTC).replace(tzinfo=None),
            }

            return standardized_data

        except Exception as e:
            self.logger.error(f"❌ 标准化Tushare财务数据失败: {e}")
            return {
                "symbol": ts_code.split(".")[0] if "." in ts_code else ts_code,
                "data_source": "tushare",
                "updated_at": datetime.now(UTC).replace(tzinfo=None),
                "error": str(e),
            }

    def _calculate_ttm_from_tushare(self, income_statements: list, field: str) -> Optional[float]:
        """
        从 Tushare 利润表数据计算 TTM（最近12个月）

        Tushare 利润表数据是累计值（从年初到报告期的累计）：
        - 2025Q1 (20250331): 2025年1-3月累计
        - 2025Q2 (20250630): 2025年1-6月累计
        - 2025Q3 (20250930): 2025年1-9月累计
        - 2025Q4 (20251231): 2025年1-12月累计（年报）

        TTM 计算公式：
        TTM = 去年同期之后的最近年报 + (本期累计 - 去年同期累计)

        例如：2025Q2 TTM = 2024年报 + (2025Q2 - 2024Q2)
                        = 2024年1-12月 + (2025年1-6月 - 2024年1-6月)
                        = 2024年7-12月 + 2025年1-6月
                        = 最近12个月

        Args:
            income_statements: 利润表数据列表（按报告期倒序）
            field: 字段名（'revenue' 或 'n_income_attr_p'）

        Returns:
            TTM 值，如果无法计算则返回 None
        """
        if not income_statements or len(income_statements) < 1:
            return None

        try:
            latest = income_statements[0]
            latest_period = latest.get("end_date")
            latest_value = self._safe_float(latest.get(field))

            if not latest_period or latest_value is None:
                return None

            # 判断最新期的类型
            month_day = latest_period[4:8]

            # 如果最新期是年报（1231），直接使用
            if month_day == "1231":
                self.logger.debug(f"✅ TTM计算: 使用年报数据 {latest_period} = {latest_value:.2f}")
                return latest_value

            # 如果是季报/半年报，需要计算 TTM = 基准期 + (本期累计 - 去年同期累计)

            # 1. 查找去年同期
            latest_year = latest_period[:4]
            last_year = str(int(latest_year) - 1)
            last_year_same_period = last_year + latest_period[4:]

            last_year_same = None
            for stmt in income_statements:
                if stmt.get("end_date") == last_year_same_period:
                    last_year_same = stmt
                    break

            if not last_year_same:
                # 缺少去年同期数据，无法准确计算 TTM
                self.logger.warning(
                    f"⚠️ TTM计算失败: 缺少去年同期数据（需要: {last_year_same_period}，最新期: {latest_period}）"
                )
                return None

            last_year_value = self._safe_float(last_year_same.get(field))
            if last_year_value is None:
                self.logger.warning(f"⚠️ TTM计算失败: 去年同期数据值为空（{last_year_same_period}）")
                return None

            # 2. 查找"去年同期之后的最近年报"作为基准期
            # 例如：如果最新期是 2025Q2，去年同期是 2024Q2，则查找 2024年报（20241231）
            base_period = None
            for stmt in income_statements:
                period = stmt.get("end_date")
                # 必须满足：在去年同期之后 且 是年报（1231）
                if period and period > last_year_same_period and period[4:8] == "1231":
                    base_period = stmt
                    break

            if not base_period:
                # 没有找到合适的年报，无法计算
                # 这种情况通常发生在：最新期是 2025Q1，但 2024年报还没公布
                self.logger.warning(
                    f"⚠️ TTM计算失败: 缺少基准年报（需要在 {last_year_same_period} 之后的年报，最新期: {latest_period}）"
                )
                return None

            base_value = self._safe_float(base_period.get(field))
            if base_value is None:
                self.logger.warning(f"⚠️ TTM计算失败: 基准年报数据值为空（{base_period.get('end_date')}）")
                return None

            # 3. 计算 TTM = 基准年报 + (本期累计 - 去年同期累计)
            ttm_value = base_value + (latest_value - last_year_value)

            self.logger.debug(
                f"✅ TTM计算: {base_period.get('end_date')}({base_value:.2f}) + "
                f"({latest_period}({latest_value:.2f}) - {last_year_same_period}({last_year_value:.2f})) = {ttm_value:.2f}"
            )

            return ttm_value

        except Exception as e:
            self.logger.warning(f"❌ TTM计算异常: {e}")
            return None

    def _determine_report_type(self, report_period: str) -> str:
        """根据报告期确定报告类型"""
        if not report_period:
            return "quarterly"

        try:
            # 报告期格式: YYYYMMDD
            month_day = report_period[4:8]
            if month_day == "1231":
                return "annual"  # 年报
            else:
                return "quarterly"  # 季报
        except Exception:
            return "quarterly"

    def _safe_float(self, value) -> Optional[float]:
        """安全转换为浮点数，处理各种异常情况"""
        if value is None:
            return None

        try:
            # 处理字符串类型
            if isinstance(value, str):
                value = value.strip()
                if not value or value.lower() in ["nan", "null", "none", "--", ""]:
                    return None
                # 移除可能的单位符号
                value = value.replace(",", "").replace("万", "").replace("亿", "")

            # 处理数值类型
            if isinstance(value, (int, float)):
                # 检查是否为NaN
                if isinstance(value, float) and (value != value):  # NaN检查
                    return None
                return float(value)

            # 尝试转换
            return float(value)

        except (ValueError, TypeError, AttributeError):
            return None

    def _calculate_gross_profit(self, revenue, oper_cost) -> Optional[float]:
        """安全计算毛利润"""
        revenue_float = self._safe_float(revenue)
        oper_cost_float = self._safe_float(oper_cost)

        if revenue_float is not None and oper_cost_float is not None:
            return revenue_float - oper_cost_float
        return None

    def _safe_str(self, value) -> Optional[str]:
        """安全转换为字符串，处理NaN值"""
        if value is None:
            return None
        if isinstance(value, float) and (value != value):  # 检查NaN
            return None
        return str(value) if value else None
