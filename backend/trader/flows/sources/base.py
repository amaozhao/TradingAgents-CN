from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .imports import (
        Any,
        ChinaDataSource,
        Optional,
        cast,
        importlib,
        logger,
        np,
        pd,
        time,
    )

class _DataSourceManagerMixin2:
    def _format_stock_data_response(
        self,
        data: pd.DataFrame,
        symbol: str,
        stock_name: str,
        start_date: str,
        end_date: str,
    ) -> str:
        """
        格式化股票数据响应（包含技术指标）

        Args:
            data: 股票数据DataFrame
            symbol: 股票代码
            stock_name: 股票名称
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            str: 格式化的数据报告（包含技术指标）
        """
        try:
            original_data_count = len(data)
            logger.info(f"📊 [技术指标] 开始计算技术指标，原始数据: {original_data_count}条")

            # 🔧 计算技术指标（使用完整数据）
            # 确保数据按日期排序
            if "date" in data.columns:
                data = data.sort_values("date")

            # 计算移动平均线
            data["ma5"] = data["close"].rolling(window=5, min_periods=1).mean()
            data["ma10"] = data["close"].rolling(window=10, min_periods=1).mean()
            data["ma20"] = data["close"].rolling(window=20, min_periods=1).mean()
            data["ma60"] = data["close"].rolling(window=60, min_periods=1).mean()

            # 计算RSI（相对强弱指标）- 同花顺风格：使用中国式SMA（EMA with adjust=True）
            # 参考：https://blog.csdn.net/u011218867/article/details/117427927
            # 同花顺/通达信的RSI使用SMA函数，等价于pandas的ewm(com=N-1, adjust=True)
            delta = data["close"].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)

            # RSI6 - 使用中国式SMA
            avg_gain6 = gain.ewm(com=5, adjust=True).mean()  # com = N - 1
            avg_loss6 = loss.ewm(com=5, adjust=True).mean()
            rs6 = avg_gain6 / avg_loss6.replace(0, np.nan)
            data["rsi6"] = 100 - (100 / (1 + rs6))

            # RSI12 - 使用中国式SMA
            avg_gain12 = gain.ewm(com=11, adjust=True).mean()
            avg_loss12 = loss.ewm(com=11, adjust=True).mean()
            rs12 = avg_gain12 / avg_loss12.replace(0, np.nan)
            data["rsi12"] = 100 - (100 / (1 + rs12))

            # RSI24 - 使用中国式SMA
            avg_gain24 = gain.ewm(com=23, adjust=True).mean()
            avg_loss24 = loss.ewm(com=23, adjust=True).mean()
            rs24 = avg_gain24 / avg_loss24.replace(0, np.nan)
            data["rsi24"] = 100 - (100 / (1 + rs24))

            # 保留RSI14作为国际标准参考（使用简单移动平均）
            gain14 = gain.rolling(window=14, min_periods=1).mean()
            loss14 = loss.rolling(window=14, min_periods=1).mean()
            rs14 = gain14 / cast(Any, loss14).replace(0, np.nan)
            data["rsi14"] = 100 - (100 / (1 + rs14))

            # 计算MACD
            ema12 = data["close"].ewm(span=12, adjust=False).mean()
            ema26 = data["close"].ewm(span=26, adjust=False).mean()
            data["macd_dif"] = ema12 - ema26
            data["macd_dea"] = data["macd_dif"].ewm(span=9, adjust=False).mean()
            data["macd"] = (data["macd_dif"] - data["macd_dea"]) * 2

            # 计算布林带
            data["boll_mid"] = data["close"].rolling(window=20, min_periods=1).mean()
            std = data["close"].rolling(window=20, min_periods=1).std()
            data["boll_upper"] = data["boll_mid"] + 2 * std
            data["boll_lower"] = data["boll_mid"] - 2 * std

            logger.info("✅ [技术指标] 技术指标计算完成")

            # 🔧 只保留最后3-5天的数据用于展示（减少token消耗）
            display_rows = min(5, len(data))
            display_data = data.tail(display_rows)
            latest_data = data.iloc[-1]

            # 🔍 [调试日志] 打印最近5天的原始数据和技术指标
            logger.info(f"🔍 [技术指标详情] ===== 最近{display_rows}个交易日数据 =====")
            for i, (idx, row) in enumerate(display_data.iterrows(), 1):
                logger.info(f"🔍 [技术指标详情] 第{i}天 ({row.get('date', 'N/A')}):")
                logger.info(
                    f"   价格: 开={row.get('open', 0):.2f}, 高={row.get('high', 0):.2f}, 低={row.get('low', 0):.2f}, 收={row.get('close', 0):.2f}"
                )
                logger.info(
                    f"   MA: MA5={row.get('ma5', 0):.2f}, MA10={row.get('ma10', 0):.2f}, MA20={row.get('ma20', 0):.2f}, MA60={row.get('ma60', 0):.2f}"
                )
                logger.info(
                    f"   MACD: DIF={row.get('macd_dif', 0):.4f}, DEA={row.get('macd_dea', 0):.4f}, MACD={row.get('macd', 0):.4f}"
                )
                logger.info(
                    f"   RSI: RSI6={row.get('rsi6', 0):.2f}, RSI12={row.get('rsi12', 0):.2f}, RSI24={row.get('rsi24', 0):.2f} (同花顺风格)"
                )
                logger.info(f"   RSI14: {row.get('rsi14', 0):.2f} (国际标准)")
                logger.info(
                    f"   BOLL: 上={row.get('boll_upper', 0):.2f}, 中={row.get('boll_mid', 0):.2f}, 下={row.get('boll_lower', 0):.2f}"
                )

            logger.info("🔍 [技术指标详情] ===== 数据详情结束 =====")

            # 计算最新价格和涨跌幅
            latest_price = latest_data.get("close", 0)
            prev_close = data.iloc[-2].get("close", latest_price) if len(data) > 1 else latest_price
            change = latest_price - prev_close
            change_pct = (change / prev_close * 100) if prev_close != 0 else 0

            # 格式化数据报告
            result = f"📊 {stock_name}({symbol}) - 技术分析数据\n"
            result += f"数据期间: {start_date} 至 {end_date}\n"
            result += f"数据条数: {original_data_count}条 (展示最近{display_rows}个交易日)\n\n"

            result += f"💰 最新价格: ¥{latest_price:.2f}\n"
            result += f"📈 涨跌额: {change:+.2f} ({change_pct:+.2f}%)\n\n"

            # 添加技术指标
            result += "📊 移动平均线 (MA):\n"
            result += f"   MA5:  ¥{latest_data['ma5']:.2f}"
            if latest_price > latest_data["ma5"]:
                result += " (价格在MA5上方 ↑)\n"
            else:
                result += " (价格在MA5下方 ↓)\n"

            result += f"   MA10: ¥{latest_data['ma10']:.2f}"
            if latest_price > latest_data["ma10"]:
                result += " (价格在MA10上方 ↑)\n"
            else:
                result += " (价格在MA10下方 ↓)\n"

            result += f"   MA20: ¥{latest_data['ma20']:.2f}"
            if latest_price > latest_data["ma20"]:
                result += " (价格在MA20上方 ↑)\n"
            else:
                result += " (价格在MA20下方 ↓)\n"

            result += f"   MA60: ¥{latest_data['ma60']:.2f}"
            if latest_price > latest_data["ma60"]:
                result += " (价格在MA60上方 ↑)\n\n"
            else:
                result += " (价格在MA60下方 ↓)\n\n"

            # MACD指标
            result += "📈 MACD指标:\n"
            result += f"   DIF:  {latest_data['macd_dif']:.3f}\n"
            result += f"   DEA:  {latest_data['macd_dea']:.3f}\n"
            result += f"   MACD: {latest_data['macd']:.3f}"
            if latest_data["macd"] > 0:
                result += " (多头 ↑)\n"
            else:
                result += " (空头 ↓)\n"

            # 判断金叉/死叉
            if len(data) > 1:
                prev_dif = data.iloc[-2]["macd_dif"]
                prev_dea = data.iloc[-2]["macd_dea"]
                curr_dif = latest_data["macd_dif"]
                curr_dea = latest_data["macd_dea"]

                if prev_dif <= prev_dea and curr_dif > curr_dea:
                    result += "   ⚠️ MACD金叉信号（DIF上穿DEA）\n\n"
                elif prev_dif >= prev_dea and curr_dif < curr_dea:
                    result += "   ⚠️ MACD死叉信号（DIF下穿DEA）\n\n"
                else:
                    result += "\n"
            else:
                result += "\n"

            # RSI指标 - 同花顺风格 (6, 12, 24)
            rsi6 = latest_data["rsi6"]
            rsi12 = latest_data["rsi12"]
            rsi24 = latest_data["rsi24"]
            result += "📉 RSI指标 (同花顺风格):\n"
            result += f"   RSI6:  {rsi6:.2f}"
            if rsi6 >= 80:
                result += " (超买 ⚠️)\n"
            elif rsi6 <= 20:
                result += " (超卖 ⚠️)\n"
            else:
                result += "\n"

            result += f"   RSI12: {rsi12:.2f}"
            if rsi12 >= 80:
                result += " (超买 ⚠️)\n"
            elif rsi12 <= 20:
                result += " (超卖 ⚠️)\n"
            else:
                result += "\n"

            result += f"   RSI24: {rsi24:.2f}"
            if rsi24 >= 80:
                result += " (超买 ⚠️)\n"
            elif rsi24 <= 20:
                result += " (超卖 ⚠️)\n"
            else:
                result += "\n"

            # 判断RSI趋势
            if rsi6 > rsi12 > rsi24:
                result += "   趋势: 多头排列 ↑\n\n"
            elif rsi6 < rsi12 < rsi24:
                result += "   趋势: 空头排列 ↓\n\n"
            else:
                result += "   趋势: 震荡整理 ↔\n\n"

            # 布林带
            result += "📊 布林带 (BOLL):\n"
            result += f"   上轨: ¥{latest_data['boll_upper']:.2f}\n"
            result += f"   中轨: ¥{latest_data['boll_mid']:.2f}\n"
            result += f"   下轨: ¥{latest_data['boll_lower']:.2f}\n"

            # 判断价格在布林带的位置
            boll_position = (
                (latest_price - latest_data["boll_lower"])
                / (latest_data["boll_upper"] - latest_data["boll_lower"])
                * 100
            )
            result += f"   价格位置: {boll_position:.1f}%"
            if boll_position >= 80:
                result += " (接近上轨，可能超买 ⚠️)\n\n"
            elif boll_position <= 20:
                result += " (接近下轨，可能超卖 ⚠️)\n\n"
            else:
                result += " (中性区域)\n\n"

            # 价格统计
            result += f"📊 价格统计 (最近{display_rows}个交易日):\n"
            result += f"   最高价: ¥{display_data['high'].max():.2f}\n"
            result += f"   最低价: ¥{display_data['low'].min():.2f}\n"
            result += f"   平均价: ¥{display_data['close'].mean():.2f}\n"

            # 防御性获取成交量数据
            volume_value = self._get_volume_safely(display_data)
            result += f"   平均成交量: {volume_value:,.0f}股\n"

            return result

        except Exception as e:
            logger.error(f"❌ 格式化数据响应失败: {e}", exc_info=True)
            return f"❌ 格式化{symbol}数据失败: {e}"

    def get_stock_dataframe(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = "daily",
    ) -> pd.DataFrame:
        """
        获取股票数据的 DataFrame 接口，支持多数据源和自动降级

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 数据周期（daily/weekly/monthly），默认为daily

        Returns:
            pd.DataFrame: 股票数据 DataFrame，列标准：open, high, low, close, vol, amount, date
        """
        logger.info(f"📊 [DataFrame接口] 获取股票数据: {symbol} ({start_date} 到 {end_date})")
        resolved_start_date = start_date or "1990-01-01"
        resolved_end_date = end_date or pd.Timestamp.today().strftime("%Y-%m-%d")

        try:
            # 尝试当前数据源
            df = None
            if self.current_source == ChinaDataSource.POSTGRES:
                get_postgres_cache_adapter = getattr(
                    importlib.import_module("trader.flows.cache.postgres"),
                    "get_postgres_cache_adapter",
                )
                adapter = get_postgres_cache_adapter()
                df = adapter.get_historical_data(symbol, resolved_start_date, resolved_end_date, period=period)
            elif self.current_source == ChinaDataSource.TUSHARE:
                get_tushare_provider = getattr(
                    importlib.import_module("trader.flows.providers.china.tushare"),
                    "get_tushare_provider",
                )
                provider = cast(Any, get_tushare_provider())
                df = getattr(provider, "get_daily_data", provider.get_historical_data)(
                    symbol, resolved_start_date, resolved_end_date
                )
            elif self.current_source == ChinaDataSource.AKSHARE:
                get_akshare_provider = getattr(
                    importlib.import_module("trader.flows.providers.china.akshare"),
                    "get_akshare_provider",
                )
                provider = cast(Any, get_akshare_provider())
                df = getattr(provider, "get_stock_data", provider.get_historical_data)(
                    symbol, resolved_start_date, resolved_end_date
                )
            elif self.current_source == ChinaDataSource.BAOSTOCK:
                get_baostock_provider = getattr(
                    importlib.import_module("trader.flows.providers.china.baostock"),
                    "get_baostock_provider",
                )
                provider = cast(Any, get_baostock_provider())
                df = getattr(provider, "get_stock_data", provider.get_historical_data)(
                    symbol, resolved_start_date, resolved_end_date
                )

            if df is not None and not df.empty:
                logger.info(f"✅ [DataFrame接口] 从 {self.current_source.value} 获取成功: {len(df)}条")
                return self._standardize_dataframe(df)

            # 降级到其他数据源
            logger.warning(f"⚠️ [DataFrame接口] {self.current_source.value} 失败，尝试降级")
            for source in self.available_sources:
                if source == self.current_source:
                    continue
                try:
                    if source == ChinaDataSource.POSTGRES:
                        get_postgres_cache_adapter = getattr(
                            importlib.import_module("trader.flows.cache.postgres"),
                            "get_postgres_cache_adapter",
                        )
                        adapter = get_postgres_cache_adapter()
                        df = adapter.get_historical_data(
                            symbol,
                            resolved_start_date,
                            resolved_end_date,
                            period=period,
                        )
                    elif source == ChinaDataSource.TUSHARE:
                        get_tushare_provider = getattr(
                            importlib.import_module("trader.flows.providers.china.tushare"),
                            "get_tushare_provider",
                        )
                        provider = cast(Any, get_tushare_provider())
                        df = getattr(provider, "get_daily_data", provider.get_historical_data)(
                            symbol, resolved_start_date, resolved_end_date
                        )
                    elif source == ChinaDataSource.AKSHARE:
                        get_akshare_provider = getattr(
                            importlib.import_module("trader.flows.providers.china.akshare"),
                            "get_akshare_provider",
                        )
                        provider = cast(Any, get_akshare_provider())
                        df = getattr(provider, "get_stock_data", provider.get_historical_data)(
                            symbol, resolved_start_date, resolved_end_date
                        )
                    elif source == ChinaDataSource.BAOSTOCK:
                        get_baostock_provider = getattr(
                            importlib.import_module("trader.flows.providers.china.baostock"),
                            "get_baostock_provider",
                        )
                        provider = cast(Any, get_baostock_provider())
                        df = getattr(provider, "get_stock_data", provider.get_historical_data)(
                            symbol, resolved_start_date, resolved_end_date
                        )

                    if df is not None and not df.empty:
                        logger.info(f"✅ [DataFrame接口] 降级到 {source.value} 成功: {len(df)}条")
                        return self._standardize_dataframe(df)
                except Exception as e:
                    logger.warning(f"⚠️ [DataFrame接口] {source.value} 失败: {e}")
                    continue

            logger.error(f"❌ [DataFrame接口] 所有数据源都失败: {symbol}")
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"❌ [DataFrame接口] 获取失败: {e}", exc_info=True)
            return pd.DataFrame()

    def _standardize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化 DataFrame 列名和格式

        Args:
            df: 原始 DataFrame

        Returns:
            pd.DataFrame: 标准化后的 DataFrame
        """
        if df is None or df.empty:
            return pd.DataFrame()

        out = df.copy()

        # 列名映射
        colmap = {
            # English
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "vol",
            "Amount": "amount",
            "symbol": "code",
            "Symbol": "code",
            # Already lower
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "vol": "vol",
            "volume": "vol",
            "amount": "amount",
            "code": "code",
            "date": "date",
            "trade_date": "date",
            # Chinese (AKShare common)
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "vol",
            "成交额": "amount",
            "涨跌幅": "pct_change",
            "涨跌额": "change",
        }
        out = out.rename(columns={c: colmap.get(c, c) for c in out.columns})

        # 确保日期排序
        if "date" in out.columns:
            try:
                out["date"] = pd.to_datetime(out["date"])
                out = out.sort_values("date")
            except Exception:
                pass

        # 计算涨跌幅（如果缺失）
        if "pct_change" not in out.columns and "close" in out.columns:
            out["pct_change"] = out["close"].pct_change() * 100.0

        return out

    def get_stock_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = "daily",
    ) -> str:
        """
        获取股票数据的统一接口，支持多周期数据

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 数据周期（daily/weekly/monthly），默认为daily

        Returns:
            str: 格式化的股票数据
        """
        # 记录详细的输入参数
        logger.info(
            f"📊 [数据来源: {self.current_source.value}] 开始获取{period}数据: {symbol}",
            extra={
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date,
                "period": period,
                "data_source": self.current_source.value,
                "event_type": "data_fetch_start",
            },
        )

        # 添加详细的股票代码追踪日志
        logger.info(
            f"🔍 [股票代码追踪] DataSourceManager.get_stock_data 接收到的股票代码: '{symbol}' (类型: {type(symbol)})"
        )
        logger.info(f"🔍 [股票代码追踪] 股票代码长度: {len(str(symbol))}")
        logger.info(f"🔍 [股票代码追踪] 股票代码字符: {list(str(symbol))}")
        logger.info(f"🔍 [股票代码追踪] 当前数据源: {self.current_source.value}")

        start_time = time.time()
        resolved_start_date = start_date or "1990-01-01"
        resolved_end_date = end_date or pd.Timestamp.today().strftime("%Y-%m-%d")

        try:
            # 根据数据源调用相应的获取方法
            actual_source = None  # 实际使用的数据源

            if self.current_source == ChinaDataSource.POSTGRES:
                result, actual_source = self._get_postgres_data(symbol, resolved_start_date, resolved_end_date, period)
            elif self.current_source == ChinaDataSource.TUSHARE:
                logger.info(f"🔍 [股票代码追踪] 调用 Tushare 数据源，传入参数: symbol='{symbol}', period='{period}'")
                result = self._get_tushare_data(symbol, resolved_start_date, resolved_end_date, period)
                actual_source = "tushare"
            elif self.current_source == ChinaDataSource.AKSHARE:
                result = self._get_akshare_data(symbol, resolved_start_date, resolved_end_date, period)
                actual_source = "akshare"
            elif self.current_source == ChinaDataSource.BAOSTOCK:
                result = self._get_baostock_data(symbol, resolved_start_date, resolved_end_date, period)
                actual_source = "baostock"
            # TDX 已移除
            else:
                result = f"❌ 不支持的数据源: {self.current_source.value}"
                actual_source = None

            # 记录详细的输出结果
            duration = time.time() - start_time
            result_length = len(result) if result else 0
            is_success = result and "❌" not in result and "错误" not in result

            # 使用实际数据源名称，如果没有则使用 current_source
            display_source = actual_source or self.current_source.value

            if is_success:
                logger.info(
                    f"✅ [数据来源: {display_source}] 成功获取股票数据: {symbol} ({result_length}字符, 耗时{duration:.2f}秒)",
                    extra={
                        "symbol": symbol,
                        "start_date": start_date,
                        "end_date": end_date,
                        "data_source": display_source,
                        "actual_source": actual_source,
                        "requested_source": self.current_source.value,
                        "duration": duration,
                        "result_length": result_length,
                        "result_preview": result[:200] + "..." if result_length > 200 else result,
                        "event_type": "data_fetch_success",
                    },
                )
                return result
            else:
                logger.warning(
                    f"⚠️ [数据来源: {self.current_source.value}失败] 数据质量异常，尝试降级到其他数据源: {symbol}",
                    extra={
                        "symbol": symbol,
                        "start_date": start_date,
                        "end_date": end_date,
                        "data_source": self.current_source.value,
                        "duration": duration,
                        "result_length": result_length,
                        "result_preview": result[:200] + "..." if result_length > 200 else result,
                        "event_type": "data_fetch_warning",
                    },
                )

                # 数据质量异常时也尝试降级到其他数据源
                fallback_result, _fallback_source = self._try_fallback_sources(
                    symbol, resolved_start_date, resolved_end_date
                )
                if fallback_result and "❌" not in fallback_result and "错误" not in fallback_result:
                    logger.info(f"✅ [数据来源: 备用数据源] 降级成功获取数据: {symbol}")
                    return fallback_result
                else:
                    logger.error(f"❌ [数据来源: 所有数据源失败] 所有数据源都无法获取有效数据: {symbol}")
                    return result  # 返回原始结果（包含错误信息）

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"❌ [数据获取] 异常失败: {e}",
                extra={
                    "symbol": symbol,
                    "start_date": start_date,
                    "end_date": end_date,
                    "data_source": self.current_source.value,
                    "duration": duration,
                    "error": str(e),
                    "event_type": "data_fetch_exception",
                },
                exc_info=True,
            )
            fallback_result, _fallback_source = self._try_fallback_sources(
                symbol, resolved_start_date, resolved_end_date
            )
            return fallback_result

    def _get_postgres_data(
        self, symbol: str, start_date: str, end_date: str, period: str = "daily"
    ) -> tuple[str, str | None]:
        """
        从PostgreSQL获取多周期数据 - 包含技术指标计算

        Returns:
            tuple[str, str | None]: (结果字符串, 实际使用的数据源名称)
        """
        logger.debug(
            f"📊 [PostgreSQL] 调用参数: symbol={symbol}, start_date={start_date}, end_date={end_date}, period={period}"
        )

        try:
            get_postgres_cache_adapter = getattr(
                importlib.import_module("trader.flows.cache.postgres"),
                "get_postgres_cache_adapter",
            )
            adapter = get_postgres_cache_adapter()

            # 从PostgreSQL获取指定周期的历史数据
            df = adapter.get_historical_data(symbol, start_date, end_date, period=period)

            if df is not None and not df.empty:
                logger.info(f"✅ [数据来源: PostgreSQL缓存] 成功获取{period}数据: {symbol} ({len(df)}条记录)")

                # 🔧 修复：使用统一的格式化方法，包含技术指标计算
                # 获取股票名称（从DataFrame中提取或使用默认值）
                stock_name = f"股票{symbol}"
                if "name" in df.columns and not df["name"].empty:
                    stock_name = df["name"].iloc[0]

                # 调用统一的格式化方法（包含技术指标计算）
                result = self._format_stock_data_response(df, symbol, stock_name, start_date, end_date)

                logger.info("✅ [PostgreSQL] 已计算技术指标: MA5/10/20/60, MACD, RSI, BOLL")
                return result, "postgres"
            else:
                # PostgreSQL没有数据（adapter内部已记录详细的数据源信息），降级到其他数据源
                logger.info(f"🔄 [PostgreSQL] 未找到{period}数据: {symbol}，开始尝试备用数据源")
                return self._try_fallback_sources(symbol, start_date, end_date, period)

        except Exception as e:
            logger.error(f"❌ [数据来源: PostgreSQL异常] 获取{period}数据失败: {symbol}, 错误: {e}")
            # PostgreSQL异常，降级到其他数据源
            return self._try_fallback_sources(symbol, start_date, end_date, period)
