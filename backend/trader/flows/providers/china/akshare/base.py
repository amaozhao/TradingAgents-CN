# ruff: noqa: F401,F403,F405,F821
class _AKShareProviderMixin2:
    async def get_batch_stock_quotes(
        self, codes: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        批量获取股票实时行情（优化版：一次获取全市场快照）

        优先使用新浪财经接口（更稳定），失败时回退到东方财富接口

        Args:
            codes: 股票代码列表

        Returns:
            股票代码到行情数据的映射字典
        """
        if not self.connected:
            return {}

        # 重试逻辑
        max_retries = 2
        retry_delay = 1  # 秒

        for attempt in range(max_retries):
            try:
                logger.debug(
                    f"📊 批量获取 {len(codes)} 只股票的实时行情... (尝试 {attempt + 1}/{max_retries})"
                )

                # 优先使用新浪财经接口（更稳定，不容易被封）
                def fetch_spot_data_sina():
                    time = importlib.import_module("time")
                    time.sleep(0.3)  # 添加延迟避免频率限制
                    return self.ak.stock_zh_a_spot()

                try:
                    spot_df = await asyncio.to_thread(fetch_spot_data_sina)
                    logger.debug("✅ 使用新浪财经接口获取数据")
                except Exception as e:
                    logger.warning(f"⚠️ 新浪财经接口失败: {e}，尝试东方财富接口...")

                    # 回退到东方财富接口
                    def fetch_spot_data_em():
                        time = importlib.import_module("time")
                        time.sleep(0.5)
                        return self.ak.stock_zh_a_spot_em()

                    spot_df = await asyncio.to_thread(fetch_spot_data_em)
                    logger.debug("✅ 使用东方财富接口获取数据")

                if spot_df is None or spot_df.empty:
                    logger.warning("⚠️ 全市场快照为空")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    return {}

                # 构建代码到行情的映射
                quotes_map = {}
                codes_set = set(codes)

                # 构建代码映射表（支持带前缀的代码匹配）
                # 例如：sh600000 -> 600000, sz000001 -> 000001
                code_mapping = {}
                for code in codes:
                    code_mapping[code] = code  # 原始代码
                    # 添加可能的前缀变体
                    for prefix in ["sh", "sz", "bj"]:
                        code_mapping[f"{prefix}{code}"] = code

                for _, row in spot_df.iterrows():
                    raw_code = str(row.get("代码", ""))

                    # 尝试匹配代码（支持带前缀和不带前缀）
                    matched_code = None
                    if raw_code in code_mapping:
                        matched_code = code_mapping[raw_code]
                    elif raw_code in codes_set:
                        matched_code = raw_code

                    if matched_code:
                        quotes_data = {
                            "name": str(row.get("名称", f"股票{matched_code}")),
                            "price": self._safe_float(row.get("最新价", 0)),
                            "change": self._safe_float(row.get("涨跌额", 0)),
                            "change_percent": self._safe_float(row.get("涨跌幅", 0)),
                            "volume": self._safe_int(row.get("成交量", 0)),
                            "amount": self._safe_float(row.get("成交额", 0)),
                            "open": self._safe_float(row.get("今开", 0)),
                            "high": self._safe_float(row.get("最高", 0)),
                            "low": self._safe_float(row.get("最低", 0)),
                            "pre_close": self._safe_float(row.get("昨收", 0)),
                            # 🔥 新增：财务指标字段
                            "turnover_rate": self._safe_float(
                                row.get("换手率", None)
                            ),  # 换手率（%）
                            "volume_ratio": self._safe_float(
                                row.get("量比", None)
                            ),  # 量比
                            "pe": self._safe_float(
                                row.get("市盈率-动态", None)
                            ),  # 动态市盈率
                            "pb": self._safe_float(row.get("市净率", None)),  # 市净率
                            "total_mv": self._safe_float(
                                row.get("总市值", None)
                            ),  # 总市值（元）
                            "circ_mv": self._safe_float(
                                row.get("流通市值", None)
                            ),  # 流通市值（元）
                        }

                        # 转换为标准化字典（使用匹配后的代码）
                        quotes_map[matched_code] = {
                            "code": matched_code,
                            "symbol": matched_code,
                            "name": quotes_data.get("name", f"股票{matched_code}"),
                            "price": float(quotes_data.get("price", 0)),
                            "change": float(quotes_data.get("change", 0)),
                            "change_percent": float(
                                quotes_data.get("change_percent", 0)
                            ),
                            "volume": int(quotes_data.get("volume", 0)),
                            "amount": float(quotes_data.get("amount", 0)),
                            "open_price": float(quotes_data.get("open", 0)),
                            "high_price": float(quotes_data.get("high", 0)),
                            "low_price": float(quotes_data.get("low", 0)),
                            "pre_close": float(quotes_data.get("pre_close", 0)),
                            # 🔥 新增：财务指标字段
                            "turnover_rate": quotes_data.get(
                                "turnover_rate"
                            ),  # 换手率（%）
                            "volume_ratio": quotes_data.get("volume_ratio"),  # 量比
                            "pe": quotes_data.get("pe"),  # 动态市盈率
                            "pe_ttm": quotes_data.get(
                                "pe"
                            ),  # TTM市盈率（与动态市盈率相同）
                            "pb": quotes_data.get("pb"),  # 市净率
                            "total_mv": float(quotes_data["total_mv"]) / 1e8
                            if quotes_data.get("total_mv") is not None
                            else None,  # 总市值（转换为亿元）
                            "circ_mv": float(quotes_data["circ_mv"]) / 1e8
                            if quotes_data.get("circ_mv") is not None
                            else None,  # 流通市值（转换为亿元）
                            # 扩展字段
                            "full_symbol": self._get_full_symbol(matched_code),
                            "market_info": self._get_market_info(matched_code),
                            "data_source": "akshare",
                            "last_sync": datetime.now(timezone.utc),
                            "sync_status": "success",
                        }

                found_count = len(quotes_map)
                missing_count = len(codes) - found_count
                logger.debug(
                    f"✅ 批量获取完成: 找到 {found_count} 只, 未找到 {missing_count} 只"
                )

                # 记录未找到的股票
                if missing_count > 0:
                    missing_codes = codes_set - set(quotes_map.keys())
                    if missing_count <= 10:
                        logger.debug(f"⚠️ 未找到行情的股票: {list(missing_codes)}")
                    else:
                        logger.debug(
                            f"⚠️ 未找到行情的股票: {list(missing_codes)[:10]}... (共{missing_count}只)"
                        )

                return quotes_map

            except Exception as e:
                logger.warning(
                    f"⚠️ 批量获取实时行情失败 (尝试 {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"❌ 批量获取实时行情失败，已达最大重试次数: {e}")
                    return {}
        return {}

    async def get_stock_quotes(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取单个股票实时行情

        🔥 策略：优先使用单股报价接口，失败时回退到全市场快照和历史数据
        - 主接口: stock_bid_ask_em
        - 备份接口1: stock_zh_a_spot（新浪快照）
        - 备份接口2: stock_zh_a_spot_em（东方财富快照）
        - 最终兜底: stock_zh_a_hist（最新日线）

        Args:
            code: 股票代码

        Returns:
            标准化的行情数据
        """
        if not self.connected:
            return None

        try:
            logger.info(f"📈 使用 stock_bid_ask_em 接口获取 {code} 实时行情...")
            try:
                # 🔥 使用 stock_bid_ask_em 接口获取单个股票实时行情
                def fetch_bid_ask():
                    return self.ak.stock_bid_ask_em(symbol=code)

                bid_ask_df = await asyncio.to_thread(fetch_bid_ask)

                logger.info(f"📊 stock_bid_ask_em 返回数据类型: {type(bid_ask_df)}")
                if bid_ask_df is not None:
                    logger.info(f"📊 DataFrame shape: {bid_ask_df.shape}")
                    logger.info(f"📊 DataFrame columns: {list(bid_ask_df.columns)}")
                    logger.info(f"📊 DataFrame 完整数据:\n{bid_ask_df.to_string()}")

                if bid_ask_df is not None and not bid_ask_df.empty:
                    data_dict = dict(zip(bid_ask_df["item"], bid_ask_df["value"]))
                    logger.info(f"📊 转换后的字典: {data_dict}")
                    quotes = self._build_bid_ask_quotes(code, data_dict)
                    logger.info(
                        f"✅ {code} 实时行情获取成功: 来源=stock_bid_ask_em, 最新价={quotes['price']}, 涨跌幅={quotes['change_percent']}%, 成交量={quotes['volume']}, 成交额={quotes['amount']}"
                    )
                    return quotes

                logger.warning(
                    f"⚠️ stock_bid_ask_em 未返回 {code} 的行情数据，尝试备份接口"
                )
            except Exception as primary_error:
                logger.warning(
                    f"⚠️ stock_bid_ask_em 获取 {code} 失败，尝试备份接口: {primary_error}"
                )

            fallback_quotes = await self._get_realtime_quotes_data(code)
            if fallback_quotes:
                logger.info(
                    f"✅ {code} 通过备份接口获取行情成功: 来源={fallback_quotes.get('quote_source', 'unknown')}, "
                    f"最新价={fallback_quotes['price']}, 涨跌幅={fallback_quotes['change_percent']}%, "
                    f"成交量={fallback_quotes['volume']}, 成交额={fallback_quotes['amount']}"
                )
                return self._build_standard_quotes(code, fallback_quotes)

            logger.warning(f"⚠️ 未找到{code}的行情数据")
            return None

        except Exception as e:
            logger.error(f"❌ 获取{code}实时行情失败: {e}", exc_info=True)
            return None

    async def _get_realtime_quotes_data(self, code: str) -> Dict[str, Any]:
        """获取实时行情数据"""
        try:
            # 方法1: 使用新浪全市场快照
            def fetch_spot_data_sina():
                return self.ak.stock_zh_a_spot()

            try:
                spot_df = await asyncio.to_thread(fetch_spot_data_sina)

                if spot_df is not None and not spot_df.empty:
                    # 查找对应股票
                    stock_data = spot_df[spot_df["代码"] == code]

                    if not stock_data.empty:
                        row = stock_data.iloc[0]

                        # 解析行情数据
                        return {
                            "name": str(row.get("名称", f"股票{code}")),
                            "price": self._safe_float(row.get("最新价", 0)),
                            "change": self._safe_float(row.get("涨跌额", 0)),
                            "change_percent": self._safe_float(row.get("涨跌幅", 0)),
                            "volume": self._safe_int(row.get("成交量", 0)),
                            "amount": self._safe_float(row.get("成交额", 0)),
                            "open": self._safe_float(row.get("今开", 0)),
                            "high": self._safe_float(row.get("最高", 0)),
                            "low": self._safe_float(row.get("最低", 0)),
                            "pre_close": self._safe_float(row.get("昨收", 0)),
                            # 🔥 新增：财务指标字段
                            "turnover_rate": self._safe_float(
                                row.get("换手率", None)
                            ),  # 换手率（%）
                            "volume_ratio": self._safe_float(
                                row.get("量比", None)
                            ),  # 量比
                            "pe": self._safe_float(
                                row.get("市盈率-动态", None)
                            ),  # 动态市盈率
                            "pb": self._safe_float(row.get("市净率", None)),  # 市净率
                            "total_mv": self._safe_float(
                                row.get("总市值", None)
                            ),  # 总市值（元）
                            "circ_mv": self._safe_float(
                                row.get("流通市值", None)
                            ),  # 流通市值（元）
                            "quote_source": "stock_zh_a_spot",
                        }
            except Exception as e:
                logger.debug(f"获取{code}新浪实时快照失败: {e}")

            # 方法2: 使用东方财富全市场快照
            def fetch_spot_data_em():
                return self.ak.stock_zh_a_spot_em()

            try:
                spot_df = await asyncio.to_thread(fetch_spot_data_em)

                if spot_df is not None and not spot_df.empty:
                    stock_data = spot_df[spot_df["代码"] == code]

                    if not stock_data.empty:
                        row = stock_data.iloc[0]
                        return {
                            "name": str(row.get("名称", f"股票{code}")),
                            "price": self._safe_float(row.get("最新价", 0)),
                            "change": self._safe_float(row.get("涨跌额", 0)),
                            "change_percent": self._safe_float(row.get("涨跌幅", 0)),
                            "volume": self._safe_int(row.get("成交量", 0)),
                            "amount": self._safe_float(row.get("成交额", 0)),
                            "open": self._safe_float(row.get("今开", 0)),
                            "high": self._safe_float(row.get("最高", 0)),
                            "low": self._safe_float(row.get("最低", 0)),
                            "pre_close": self._safe_float(row.get("昨收", 0)),
                            "turnover_rate": self._safe_float(row.get("换手率", None)),
                            "volume_ratio": self._safe_float(row.get("量比", None)),
                            "pe": self._safe_float(row.get("市盈率-动态", None)),
                            "pb": self._safe_float(row.get("市净率", None)),
                            "total_mv": self._safe_float(row.get("总市值", None)),
                            "circ_mv": self._safe_float(row.get("流通市值", None)),
                            "quote_source": "stock_zh_a_spot_em",
                        }
            except Exception as e:
                logger.debug(f"获取{code}东方财富实时快照失败: {e}")

            # 方法3: 使用最新日线兜底
            def fetch_individual_spot():
                return self.ak.stock_zh_a_hist(symbol=code, period="daily", adjust="")

            try:
                hist_df = await asyncio.to_thread(fetch_individual_spot)
                if hist_df is not None and not hist_df.empty:
                    # 取最新一天的数据作为当前行情
                    latest_row = hist_df.iloc[-1]
                    return {
                        "name": f"股票{code}",
                        "price": self._safe_float(latest_row.get("收盘", 0)),
                        "change": 0,  # 历史数据无法计算涨跌额
                        "change_percent": self._safe_float(latest_row.get("涨跌幅", 0)),
                        "volume": self._safe_int(latest_row.get("成交量", 0)),
                        "amount": self._safe_float(latest_row.get("成交额", 0)),
                        "open": self._safe_float(latest_row.get("开盘", 0)),
                        "high": self._safe_float(latest_row.get("最高", 0)),
                        "low": self._safe_float(latest_row.get("最低", 0)),
                        "pre_close": self._safe_float(latest_row.get("收盘", 0)),
                        "quote_source": "stock_zh_a_hist",
                    }
            except Exception as e:
                logger.debug(f"获取{code}历史数据作为行情失败: {e}")

            return {}

        except Exception as e:
            logger.debug(f"获取{code}实时行情数据失败: {e}")
            return {}

    def _build_bid_ask_quotes(
        self, code: str, data_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """将 stock_bid_ask_em 数据转换为标准行情结构"""
        cn_tz = timezone(timedelta(hours=8))
        now_cn = datetime.now(cn_tz)
        trade_date = now_cn.strftime("%Y-%m-%d")

        volume_in_lots = int(data_dict.get("总手", 0))
        volume_in_shares = volume_in_lots * 100

        return {
            "code": code,
            "symbol": code,
            "name": f"股票{code}",
            "price": float(data_dict.get("最新", 0)),
            "close": float(data_dict.get("最新", 0)),
            "current_price": float(data_dict.get("最新", 0)),
            "change": float(data_dict.get("涨跌", 0)),
            "change_percent": float(data_dict.get("涨幅", 0)),
            "pct_chg": float(data_dict.get("涨幅", 0)),
            "volume": volume_in_shares,
            "amount": float(data_dict.get("金额", 0)),
            "open": float(data_dict.get("今开", 0)),
            "high": float(data_dict.get("最高", 0)),
            "low": float(data_dict.get("最低", 0)),
            "pre_close": float(data_dict.get("昨收", 0)),
            "turnover_rate": float(data_dict.get("换手", 0)),
            "volume_ratio": float(data_dict.get("量比", 0)),
            "pe": None,
            "pe_ttm": None,
            "pb": None,
            "total_mv": None,
            "circ_mv": None,
            "trade_date": trade_date,
            "updated_at": now_cn.isoformat(),
            "full_symbol": self._get_full_symbol(code),
            "market_info": self._get_market_info(code),
            "data_source": "akshare",
            "quote_source": "stock_bid_ask_em",
            "last_sync": datetime.now(timezone.utc),
            "sync_status": "success",
        }

    def _build_standard_quotes(
        self, code: str, quote_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """将备份接口返回的数据转换为统一行情结构"""
        cn_tz = timezone(timedelta(hours=8))
        now_cn = datetime.now(cn_tz)
        trade_date = now_cn.strftime("%Y-%m-%d")

        return {
            "code": code,
            "symbol": code,
            "name": quote_data.get("name", f"股票{code}"),
            "price": self._safe_float(quote_data.get("price", 0)),
            "close": self._safe_float(quote_data.get("price", 0)),
            "current_price": self._safe_float(quote_data.get("price", 0)),
            "change": self._safe_float(quote_data.get("change", 0)),
            "change_percent": self._safe_float(quote_data.get("change_percent", 0)),
            "pct_chg": self._safe_float(quote_data.get("change_percent", 0)),
            "volume": self._safe_int(quote_data.get("volume", 0)),
            "amount": self._safe_float(quote_data.get("amount", 0)),
            "open": self._safe_float(quote_data.get("open", 0)),
            "high": self._safe_float(quote_data.get("high", 0)),
            "low": self._safe_float(quote_data.get("low", 0)),
            "pre_close": self._safe_float(quote_data.get("pre_close", 0)),
            "turnover_rate": self._safe_float(quote_data.get("turnover_rate", 0)),
            "volume_ratio": self._safe_float(quote_data.get("volume_ratio", 0)),
            "pe": quote_data.get("pe"),
            "pe_ttm": quote_data.get("pe"),
            "pb": quote_data.get("pb"),
            "total_mv": float(quote_data["total_mv"]) / 1e8
            if quote_data.get("total_mv") is not None
            else None,
            "circ_mv": float(quote_data["circ_mv"]) / 1e8
            if quote_data.get("circ_mv") is not None
            else None,
            "trade_date": trade_date,
            "updated_at": now_cn.isoformat(),
            "full_symbol": self._get_full_symbol(code),
            "market_info": self._get_market_info(code),
            "data_source": "akshare",
            "quote_source": quote_data.get("quote_source", "unknown"),
            "last_sync": datetime.now(timezone.utc),
            "sync_status": "success",
        }

    def _safe_float(self, value: Any) -> float:
        """安全转换为浮点数"""
        try:
            if pd.isna(value) or value is None:
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def _safe_int(self, value: Any) -> int:
        """安全转换为整数"""
        try:
            if pd.isna(value) or value is None:
                return 0
            return int(float(value))
        except (ValueError, TypeError):
            return 0

    def _safe_str(self, value: Any) -> str:
        """安全转换为字符串"""
        try:
            if pd.isna(value) or value is None:
                return ""
            return str(value)
        except Exception:
            return ""

    async def get_historical_data(
        self,
        code: Optional[str] = None,
        start_date: Any = None,
        end_date: Any = None,
        period: str = "daily",
        **kwargs,
    ) -> Optional[pd.DataFrame]:
        """
        获取历史行情数据

        Args:
            code: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            period: 周期 (daily, weekly, monthly)

        Returns:
            历史行情数据DataFrame
        """
        code = str(code or kwargs.get("symbol") or "")
        if not code:
            logger.error("❌ 获取历史数据失败: 缺少股票代码")
            return None

        if hasattr(start_date, "strftime"):
            start_date = start_date.strftime("%Y-%m-%d")
        if hasattr(end_date, "strftime"):
            end_date = end_date.strftime("%Y-%m-%d")

        if not self.connected:
            return None

        try:
            logger.debug(f"📊 获取{code}历史数据: {start_date} 到 {end_date}")

            # 转换周期格式
            period_map = {"daily": "daily", "weekly": "weekly", "monthly": "monthly"}
            ak_period = period_map.get(period, "daily")

            # 格式化日期
            start_date_formatted = start_date.replace("-", "")
            end_date_formatted = end_date.replace("-", "")

            # 获取历史数据
            def fetch_historical_data():
                try:
                    return self.ak.stock_zh_a_hist(
                        symbol=code,
                        period=ak_period,
                        start_date=start_date_formatted,
                        end_date=end_date_formatted,
                        adjust="qfq",  # 前复权
                    )
                except Exception as hist_error:
                    logger.warning(
                        "⚠️ AKShare stock_zh_a_hist 获取%s失败，尝试直连备用接口: %s",
                        code,
                        hist_error,
                    )
                    if ak_period != "daily":
                        raise

                    full_symbol = self._get_full_symbol(code)
                    if full_symbol.endswith(".SS"):
                        fallback_symbol = f"sh{code}"
                    elif full_symbol.endswith(".SZ"):
                        fallback_symbol = f"sz{code}"
                    elif full_symbol.endswith(".BJ"):
                        fallback_symbol = f"bj{code}"
                    else:
                        fallback_symbol = code
                    return self.ak.stock_zh_a_daily(
                        symbol=fallback_symbol,
                        start_date=start_date_formatted,
                        end_date=end_date_formatted,
                        adjust="qfq",
                    )

            hist_df = await asyncio.to_thread(fetch_historical_data)

            if hist_df is None or hist_df.empty:
                logger.warning(f"⚠️ {code}历史数据为空")
                return None

            # 标准化列名
            hist_df = self._standardize_historical_columns(hist_df, code)

            logger.debug(f"✅ {code}历史数据获取成功: {len(hist_df)}条记录")
            return hist_df

        except Exception as e:
            logger.error(f"❌ 获取{code}历史数据失败: {e}")
            return None

    def _standardize_historical_columns(
        self, df: pd.DataFrame, code: str
    ) -> pd.DataFrame:
        """标准化历史数据列名"""
        try:
            # 标准化列名映射
            column_mapping = {
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount",
                "振幅": "amplitude",
                "涨跌幅": "change_percent",
                "涨跌额": "change",
                "换手率": "turnover",
            }

            # 重命名列
            df = df.rename(columns=column_mapping)

            # 添加标准字段
            df["code"] = code
            df["full_symbol"] = self._get_full_symbol(code)

            # 确保日期格式
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])

            # 数据类型转换
            numeric_columns = ["open", "close", "high", "low", "volume", "amount"]
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = cast(Any, pd.to_numeric(df[col], errors="coerce")).fillna(
                        0
                    )

            return df

        except Exception as e:
            logger.error(f"标准化{code}历史数据列名失败: {e}")
            return df

    async def get_financial_data(self, code: str) -> Dict[str, Any]:
        """
        获取财务数据

        Args:
            code: 股票代码

        Returns:
            财务数据字典
        """
        if not self.connected:
            return {}

        try:
            logger.debug(f"💰 获取{code}财务数据...")

            financial_data = {}

            # 1. 获取主要财务指标
            try:

                def fetch_financial_abstract():
                    return self.ak.stock_financial_abstract(symbol=code)

                main_indicators = await asyncio.to_thread(fetch_financial_abstract)
                if main_indicators is not None and not main_indicators.empty:
                    financial_data["main_indicators"] = main_indicators.to_dict(
                        "records"
                    )
                    logger.debug(f"✅ {code}主要财务指标获取成功")
            except Exception as e:
                logger.debug(f"获取{code}主要财务指标失败: {e}")

            # 2. 获取资产负债表
            try:

                def fetch_balance_sheet():
                    return self.ak.stock_balance_sheet_by_report_em(symbol=code)

                balance_sheet = await asyncio.to_thread(fetch_balance_sheet)
                if balance_sheet is not None and not balance_sheet.empty:
                    financial_data["balance_sheet"] = balance_sheet.to_dict("records")
                    logger.debug(f"✅ {code}资产负债表获取成功")
            except Exception as e:
                logger.debug(f"获取{code}资产负债表失败: {e}")

            # 3. 获取利润表
            try:

                def fetch_income_statement():
                    return self.ak.stock_profit_sheet_by_report_em(symbol=code)

                income_statement = await asyncio.to_thread(fetch_income_statement)
                if income_statement is not None and not income_statement.empty:
                    financial_data["income_statement"] = income_statement.to_dict(
                        "records"
                    )
                    logger.debug(f"✅ {code}利润表获取成功")
            except Exception as e:
                logger.debug(f"获取{code}利润表失败: {e}")

            # 4. 获取现金流量表
            try:

                def fetch_cash_flow():
                    return self.ak.stock_cash_flow_sheet_by_report_em(symbol=code)

                cash_flow = await asyncio.to_thread(fetch_cash_flow)
                if cash_flow is not None and not cash_flow.empty:
                    financial_data["cash_flow"] = cash_flow.to_dict("records")
                    logger.debug(f"✅ {code}现金流量表获取成功")
            except Exception as e:
                logger.debug(f"获取{code}现金流量表失败: {e}")

            if financial_data:
                logger.debug(
                    f"✅ {code}财务数据获取完成: {len(financial_data)}个数据集"
                )
            else:
                logger.warning(f"⚠️ {code}未获取到任何财务数据")

            return financial_data

        except Exception as e:
            logger.error(f"❌ 获取{code}财务数据失败: {e}")
            return {}

    async def get_market_status(self) -> Dict[str, Any]:
        """
        获取市场状态信息

        Returns:
            市场状态信息
        """
        try:
            # AKShare没有直接的市场状态API，返回基本信息
            now = datetime.now()

            # 简单的交易时间判断
            is_trading_time = (
                now.weekday() < 5  # 工作日
                and ((9 <= now.hour < 12) or (13 <= now.hour < 15))  # 交易时间
            )

            return {
                "market_status": "open" if is_trading_time else "closed",
                "current_time": now.isoformat(),
                "data_source": "akshare",
                "trading_day": now.weekday() < 5,
            }

        except Exception as e:
            logger.error(f"❌ 获取市场状态失败: {e}")
            return {
                "market_status": "unknown",
                "current_time": datetime.now().isoformat(),
                "data_source": "akshare",
                "error": str(e),
            }
