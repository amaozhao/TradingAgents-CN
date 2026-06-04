# ruff: noqa: F401,F403,F405,F821
def get_hk_stock_data_akshare(
    symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None
):
    """
    兼容性函数：使用 AKShare 新浪财经接口获取港股历史数据

    Args:
        symbol: 港股代码
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        港股数据（格式化字符串）
    """
    try:
        if ak is None:
            return f"❌ AKShare 未安装，无法获取港股{symbol}的历史数据"

        # 标准化代码
        provider = get_improved_hk_provider()
        normalized_symbol = provider._normalize_hk_symbol(symbol)

        # 设置默认日期
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        logger.info(
            f"🔄 [AKShare-新浪] 获取港股历史数据: {symbol} ({start_date} ~ {end_date})"
        )

        # 使用新浪财经接口获取历史数据
        df = ak.stock_hk_daily(symbol=normalized_symbol, adjust="qfq")

        if df is None or df.empty:
            logger.warning(f"⚠️ [AKShare-新浪] 返回空数据: {symbol}")
            return f"❌ 无法获取港股{symbol}的历史数据"

        # 过滤日期范围
        df["date"] = pd.to_datetime(df["date"])
        mask = (df["date"] >= start_date) & (df["date"] <= end_date)
        df = df.loc[mask]

        if df.empty:
            logger.warning(f"⚠️ [AKShare-新浪] 日期范围内无数据: {symbol}")
            return f"❌ 港股{symbol}在指定日期范围内无数据"

        # 🔥 添加 pre_close 字段（从前一天的 close 获取）
        # AKShare 不返回 pre_close 字段，需要手动计算
        df["pre_close"] = df["close"].shift(1)

        # 计算涨跌额和涨跌幅
        df["change"] = df["close"] - df["pre_close"]
        df["pct_change"] = (df["change"] / df["pre_close"] * 100).round(2)

        df = add_all_indicators(df, close_col="close", high_col="high", low_col="low")

        # 🔥 获取财务指标并计算 PE、PB
        financial_indicators = provider.get_financial_indicators(symbol)

        # 格式化输出（包含价格数据和技术指标）
        latest = df.iloc[-1]
        current_price = latest["close"]

        # 计算 PE、PB
        pe_ratio = None
        pb_ratio = None
        financial_section = ""

        if financial_indicators:
            eps_ttm = financial_indicators.get("eps_ttm")
            bps = financial_indicators.get("bps")

            if eps_ttm and eps_ttm > 0:
                pe_ratio = current_price / eps_ttm

            if bps and bps > 0:
                pb_ratio = current_price / bps

            # 构建财务指标部分（处理 None 值）
            operate_income = financial_indicators.get("operate_income")
            holder_profit = financial_indicators.get("holder_profit")

            def format_value(value, format_str=".2f", suffix="", default="N/A"):
                """格式化数值，处理 None 情况"""
                if value is None:
                    return default
                try:
                    return f"{value:{format_str}}{suffix}"
                except Exception:
                    return default

            financial_section = f"""
### 财务指标（最新报告期：{financial_indicators.get("report_date", "N/A")}）
**估值指标**:
- PE (市盈率): {f"{pe_ratio:.2f}" if pe_ratio else "N/A"} (当前价 / EPS_TTM)
- PB (市净率): {f"{pb_ratio:.2f}" if pb_ratio else "N/A"} (当前价 / BPS)

**每股指标**:
- 基本每股收益 (EPS): HK${format_value(financial_indicators.get("eps_basic"))}
- 滚动每股收益 (EPS_TTM): HK${format_value(financial_indicators.get("eps_ttm"))}
- 每股净资产 (BPS): HK${format_value(financial_indicators.get("bps"))}
- 每股经营现金流: HK${format_value(financial_indicators.get("per_netcash_operate"))}

**盈利能力**:
- 净资产收益率 (ROE): {format_value(financial_indicators.get("roe_avg"), suffix="%")}
- 总资产收益率 (ROA): {format_value(financial_indicators.get("roa"), suffix="%")}
- 净利率: {format_value(financial_indicators.get("net_profit_ratio"), suffix="%")}
- 毛利率: {format_value(financial_indicators.get("gross_profit_ratio"), suffix="%")}

**营收情况**:
- 营业收入: {format_value(operate_income / 1e8 if operate_income else None, suffix=" 亿港元")}
- 营收同比增长: {format_value(financial_indicators.get("operate_income_yoy"), suffix="%")}
- 归母净利润: {format_value(holder_profit / 1e8 if holder_profit else None, suffix=" 亿港元")}
- 净利润同比增长: {format_value(financial_indicators.get("holder_profit_yoy"), suffix="%")}

**偿债能力**:
- 资产负债率: {format_value(financial_indicators.get("debt_asset_ratio"), suffix="%")}
- 流动比率: {format_value(financial_indicators.get("current_ratio"))}
"""

        result = f"""## 港股历史数据 ({symbol})
**数据源**: AKShare (新浪财经)
**日期范围**: {start_date} ~ {end_date}
**数据条数**: {len(df)} 条

### 最新价格信息
- 最新价: HK${latest["close"]:.2f}
- 昨收: HK${latest["pre_close"]:.2f}
- 涨跌额: HK${latest["change"]:.2f}
- 涨跌幅: {latest["pct_change"]:.2f}%
- 最高: HK${latest["high"]:.2f}
- 最低: HK${latest["low"]:.2f}
- 成交量: {latest["volume"]:,.0f}

### 技术指标（最新值）
**移动平均线**:
- MA5: HK${latest["ma5"]:.2f}
- MA10: HK${latest["ma10"]:.2f}
- MA20: HK${latest["ma20"]:.2f}
- MA60: HK${latest["ma60"]:.2f}

**MACD指标**:
- DIF: {latest["macd_dif"]:.2f}
- DEA: {latest["macd_dea"]:.2f}
- MACD: {latest["macd"]:.2f}

**RSI指标**:
- RSI(14): {latest["rsi"]:.2f}

**布林带**:
- 上轨: HK${latest["boll_upper"]:.2f}
- 中轨: HK${latest["boll_mid"]:.2f}
- 下轨: HK${latest["boll_lower"]:.2f}
{financial_section}
### 最近10个交易日价格
{df[["date", "open", "high", "low", "close", "pre_close", "change", "pct_change", "volume"]].tail(10).to_string(index=False)}

### 数据统计
- 最高价: HK${df["high"].max():.2f}
- 最低价: HK${df["low"].min():.2f}
- 平均收盘价: HK${df["close"].mean():.2f}
- 总成交量: {df["volume"].sum():,.0f}
"""

        logger.info(f"✅ [AKShare-新浪] 港股历史数据获取成功: {symbol} ({len(df)}条)")
        return result

    except Exception as e:
        logger.error(f"❌ [AKShare-新浪] 港股历史数据获取失败: {symbol} - {e}")
        return f"❌ 港股{symbol}历史数据获取失败: {str(e)}"


# 🔥 全局缓存：缓存 AKShare 的所有港股数据
_akshare_hk_spot_cache = {
    "data": None,
    "timestamp": None,
    "ttl": 600,  # 缓存 10 分钟（参考美股实时行情缓存时长）
}

_akshare_hk_spot_lock = threading.Lock()


def get_hk_stock_info_akshare(symbol: str) -> Dict[str, Any]:
    """
    兼容性函数：直接使用 akshare 获取港股信息（避免循环调用）
    🔥 使用全局缓存 + 线程锁，避免重复调用 ak.stock_hk_spot()

    Args:
        symbol: 港股代码

    Returns:
        Dict: 港股信息
    """
    try:
        ak = importlib.import_module("akshare")
        datetime = getattr(importlib.import_module("datetime"), "datetime")

        # 标准化代码
        provider = get_improved_hk_provider()
        normalized_symbol = provider._normalize_hk_symbol(symbol)

        # 尝试从 akshare 获取实时行情
        try:
            # 🔥 使用互斥锁保护 AKShare API 调用（防止并发导致被封禁）
            # 策略：
            # 1. 尝试获取锁（最多等待 60 秒）
            # 2. 获取锁后，先检查缓存是否已被其他线程更新
            # 3. 如果缓存有效，直接使用；否则调用 API

            thread_id = threading.current_thread().name
            logger.info(f"🔒 [AKShare锁-{thread_id}] 尝试获取锁...")

            # 尝试获取锁，最多等待 60 秒
            lock_acquired = _akshare_hk_spot_lock.acquire(timeout=60)

            if not lock_acquired:
                # 超时，返回错误
                logger.error(f"⏰ [AKShare锁-{thread_id}] 获取锁超时（60秒），放弃")
                raise Exception("AKShare API 调用超时（其他线程占用）")

            try:
                logger.info(f"✅ [AKShare锁-{thread_id}] 已获取锁")

                # 获取锁后，检查缓存是否已被其他线程更新
                now = datetime.now()
                cache = _akshare_hk_spot_cache

                if cache["data"] is not None and cache["timestamp"] is not None:
                    elapsed = (now - cache["timestamp"]).total_seconds()
                    if elapsed <= cache["ttl"]:
                        # 缓存有效（可能是其他线程刚更新的）
                        logger.info(
                            f"⚡ [AKShare缓存-{thread_id}] 使用缓存数据（{elapsed:.1f}秒前，可能由其他线程更新）"
                        )
                        df = cache["data"]
                    else:
                        # 缓存过期，需要调用 API
                        logger.info(
                            f"🔄 [AKShare缓存-{thread_id}] 缓存过期（{elapsed:.1f}秒前），调用 API 刷新"
                        )
                        df = ak.stock_hk_spot()
                        cache["data"] = df
                        cache["timestamp"] = now
                        logger.info(
                            f"✅ [AKShare缓存-{thread_id}] 已缓存 {len(df)} 只港股数据"
                        )
                else:
                    # 缓存为空，首次调用
                    logger.info(f"🔄 [AKShare缓存-{thread_id}] 首次获取港股数据")
                    df = ak.stock_hk_spot()
                    cache["data"] = df
                    cache["timestamp"] = now
                    logger.info(
                        f"✅ [AKShare缓存-{thread_id}] 已缓存 {len(df)} 只港股数据"
                    )

            finally:
                # 释放锁
                _akshare_hk_spot_lock.release()
                logger.info(f"🔓 [AKShare锁-{thread_id}] 已释放锁")

            # 从缓存的数据中查找目标股票
            if df is not None and not df.empty:
                matched = df[df["代码"] == normalized_symbol]
                if not matched.empty:
                    row = matched.iloc[0]

                    # 辅助函数：安全转换数值
                    def safe_float(value):
                        try:
                            if (
                                value is None
                                or value == ""
                                or (isinstance(value, float) and value != value)
                            ):  # NaN check
                                return None
                            return float(value)
                        except Exception:
                            return None

                    def safe_int(value):
                        try:
                            if (
                                value is None
                                or value == ""
                                or (isinstance(value, float) and value != value)
                            ):  # NaN check
                                return None
                            return int(value)
                        except Exception:
                            return None

                    return {
                        "symbol": symbol,
                        "name": row["中文名称"],  # 新浪接口的列名
                        "price": safe_float(row.get("最新价")),
                        "open": safe_float(row.get("今开")),
                        "high": safe_float(row.get("最高")),
                        "low": safe_float(row.get("最低")),
                        "volume": safe_int(row.get("成交量")),
                        "change_percent": safe_float(row.get("涨跌幅")),
                        "currency": "HKD",
                        "exchange": "HKG",
                        "market": "港股",
                        "source": "akshare_sina",
                    }
        except Exception as e:
            logger.debug(f"📊 [港股AKShare-新浪] 获取失败: {e}")

        # 如果失败，返回基本信息
        return {
            "symbol": symbol,
            "name": f"港股{normalized_symbol}",
            "currency": "HKD",
            "exchange": "HKG",
            "market": "港股",
            "source": "akshare_fallback",
        }

    except Exception as e:
        logger.error(f"❌ [港股AKShare-新浪] 获取信息失败: {e}")
        return {
            "symbol": symbol,
            "name": f"港股{symbol}",
            "currency": "HKD",
            "exchange": "HKG",
            "market": "港股",
            "source": "error",
            "error": str(e),
        }
