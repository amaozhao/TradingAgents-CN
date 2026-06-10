# ruff: noqa: F401,F403,F405,F821
class _BaoStockProviderMixin2:
    async def get_financial_data(
        self, code: str, year: Optional[int] = None, quarter: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        获取财务数据

        Args:
            code: 股票代码
            year: 年份
            quarter: 季度

        Returns:
            财务数据字典
        """
        if not self.connected:
            return {}

        try:
            logger.info(f"💰 获取BaoStock财务数据: {code}")

            # 如果没有指定年份和季度，使用当前年份的最新季度
            if year is None:
                year = datetime.now().year
            if quarter is None:
                current_month = datetime.now().month
                quarter = (current_month - 1) // 3 + 1

            financial_data = {}

            # 1. 获取盈利能力数据
            try:
                profit_data = await self._get_profit_data(code, year, quarter)
                if profit_data:
                    financial_data["profit_data"] = profit_data
                    logger.debug(f"✅ {code}盈利能力数据获取成功")
            except Exception as e:
                logger.debug(f"获取{code}盈利能力数据失败: {e}")

            # 2. 获取营运能力数据
            try:
                operation_data = await self._get_operation_data(code, year, quarter)
                if operation_data:
                    financial_data["operation_data"] = operation_data
                    logger.debug(f"✅ {code}营运能力数据获取成功")
            except Exception as e:
                logger.debug(f"获取{code}营运能力数据失败: {e}")

            # 3. 获取成长能力数据
            try:
                growth_data = await self._get_growth_data(code, year, quarter)
                if growth_data:
                    financial_data["growth_data"] = growth_data
                    logger.debug(f"✅ {code}成长能力数据获取成功")
            except Exception as e:
                logger.debug(f"获取{code}成长能力数据失败: {e}")

            # 4. 获取偿债能力数据
            try:
                balance_data = await self._get_balance_data(code, year, quarter)
                if balance_data:
                    financial_data["balance_data"] = balance_data
                    logger.debug(f"✅ {code}偿债能力数据获取成功")
            except Exception as e:
                logger.debug(f"获取{code}偿债能力数据失败: {e}")

            # 5. 获取现金流量数据
            try:
                cash_flow_data = await self._get_cash_flow_data(code, year, quarter)
                if cash_flow_data:
                    financial_data["cash_flow_data"] = cash_flow_data
                    logger.debug(f"✅ {code}现金流量数据获取成功")
            except Exception as e:
                logger.debug(f"获取{code}现金流量数据失败: {e}")

            if financial_data:
                logger.info(
                    f"✅ BaoStock财务数据获取成功: {code}, {len(financial_data)}个数据集"
                )
            else:
                logger.warning(f"⚠️ BaoStock财务数据为空: {code}")

            return financial_data

        except Exception as e:
            logger.error(f"❌ BaoStock获取{code}财务数据失败: {e}")
            return {}

    async def _get_profit_data(
        self, code: str, year: int, quarter: int
    ) -> Optional[Dict[str, Any]]:
        """获取盈利能力数据"""
        try:

            def fetch_profit_data(bs):
                bs_code = self._to_baostock_code(code)
                rs = bs.query_profit_data(code=bs_code, year=year, quarter=quarter)
                if rs.error_code != "0":
                    return None

                data_list = []
                while (rs.error_code == "0") & rs.next():
                    data_list.append(rs.get_row_data())

                return data_list, rs.fields

            result = await run_baostock_session_async(fetch_profit_data, timeout=60)
            if not result or not result[0]:
                return None

            data_list, fields = result
            df = pd.DataFrame(data_list, columns=fields)
            return df.to_dict("records")[0] if not df.empty else None

        except Exception as e:
            logger.debug(f"获取{code}盈利能力数据失败: {e}")
            return None

    async def _get_operation_data(
        self, code: str, year: int, quarter: int
    ) -> Optional[Dict[str, Any]]:
        """获取营运能力数据"""
        try:

            def fetch_operation_data(bs):
                bs_code = self._to_baostock_code(code)
                rs = bs.query_operation_data(code=bs_code, year=year, quarter=quarter)
                if rs.error_code != "0":
                    return None

                data_list = []
                while (rs.error_code == "0") & rs.next():
                    data_list.append(rs.get_row_data())

                return data_list, rs.fields

            result = await run_baostock_session_async(fetch_operation_data, timeout=60)
            if not result or not result[0]:
                return None

            data_list, fields = result
            df = pd.DataFrame(data_list, columns=fields)
            return df.to_dict("records")[0] if not df.empty else None

        except Exception as e:
            logger.debug(f"获取{code}营运能力数据失败: {e}")
            return None

    async def _get_growth_data(
        self, code: str, year: int, quarter: int
    ) -> Optional[Dict[str, Any]]:
        """获取成长能力数据"""
        try:

            def fetch_growth_data(bs):
                bs_code = self._to_baostock_code(code)
                rs = bs.query_growth_data(code=bs_code, year=year, quarter=quarter)
                if rs.error_code != "0":
                    return None

                data_list = []
                while (rs.error_code == "0") & rs.next():
                    data_list.append(rs.get_row_data())

                return data_list, rs.fields

            result = await run_baostock_session_async(fetch_growth_data, timeout=60)
            if not result or not result[0]:
                return None

            data_list, fields = result
            df = pd.DataFrame(data_list, columns=fields)
            return df.to_dict("records")[0] if not df.empty else None

        except Exception as e:
            logger.debug(f"获取{code}成长能力数据失败: {e}")
            return None

    async def _get_balance_data(
        self, code: str, year: int, quarter: int
    ) -> Optional[Dict[str, Any]]:
        """获取偿债能力数据"""
        try:

            def fetch_balance_data(bs):
                bs_code = self._to_baostock_code(code)
                rs = bs.query_balance_data(code=bs_code, year=year, quarter=quarter)
                if rs.error_code != "0":
                    return None

                data_list = []
                while (rs.error_code == "0") & rs.next():
                    data_list.append(rs.get_row_data())

                return data_list, rs.fields

            result = await run_baostock_session_async(fetch_balance_data, timeout=60)
            if not result or not result[0]:
                return None

            data_list, fields = result
            df = pd.DataFrame(data_list, columns=fields)
            return df.to_dict("records")[0] if not df.empty else None

        except Exception as e:
            logger.debug(f"获取{code}偿债能力数据失败: {e}")
            return None

    async def _get_cash_flow_data(
        self, code: str, year: int, quarter: int
    ) -> Optional[Dict[str, Any]]:
        """获取现金流量数据"""
        try:

            def fetch_cash_flow_data(bs):
                bs_code = self._to_baostock_code(code)
                rs = bs.query_cash_flow_data(code=bs_code, year=year, quarter=quarter)
                if rs.error_code != "0":
                    return None

                data_list = []
                while (rs.error_code == "0") & rs.next():
                    data_list.append(rs.get_row_data())

                return data_list, rs.fields

            result = await run_baostock_session_async(fetch_cash_flow_data, timeout=60)
            if not result or not result[0]:
                return None

            data_list, fields = result
            df = pd.DataFrame(data_list, columns=fields)
            return df.to_dict("records")[0] if not df.empty else None

        except Exception as e:
            logger.debug(f"获取{code}现金流量数据失败: {e}")
            return None
