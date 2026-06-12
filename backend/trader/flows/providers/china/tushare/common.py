from .imports import (
    TUSHARE_AVAILABLE,
    Any,
    Dict,
    List,
    Optional,
    Union,
    asyncio,
    date,
    datetime,
    get_provider_config,
    importlib,
    pd,
    timedelta,
    ts,
)

class _TushareProviderMixin1:
    def __init__(self):
        super().__init__("Tushare")
        self.api: Any = None
        self.config = get_provider_config("tushare")
        self.token_source = None  # 记录 Token 来源: 'database' 或 'env'

        if not TUSHARE_AVAILABLE:
            self.logger.error("❌ Tushare库未安装，请运行: pip install tushare")

    def _get_token_from_database(self) -> Optional[str]:
        """
        从数据库读取 Tushare Token

        优先级：数据库配置 > 环境变量
        这样用户在 Web 后台修改配置后可以立即生效
        """
        try:
            self.logger.info("🔍 [DB查询] 开始从数据库读取 Token...")
            get_postgres_db_sync = getattr(importlib.import_module("app.core.database"), "get_postgres_db_sync")
            db = get_postgres_db_sync()
            config_collection = db.system_configs

            # 获取最新的激活配置
            self.logger.info("🔍 [DB查询] 查询 is_active=True 的配置...")
            config_data = config_collection.find_one({"is_active": True}, sort=[("version", -1)])

            if config_data:
                self.logger.info(f"✅ [DB查询] 找到激活配置，版本: {config_data.get('version')}")
                if config_data.get("data_source_configs"):
                    self.logger.info(f"✅ [DB查询] 配置中有 {len(config_data['data_source_configs'])} 个数据源")
                    for ds_config in config_data["data_source_configs"]:
                        ds_type = ds_config.get("type")
                        self.logger.info(f"🔍 [DB查询] 检查数据源: {ds_type}")
                        if ds_type == "tushare":
                            api_key = ds_config.get("api_key")
                            self.logger.info(
                                f"✅ [DB查询] 找到 Tushare 配置，api_key 长度: {len(api_key) if api_key else 0}"
                            )
                            if api_key and not api_key.startswith("your_"):
                                self.logger.info(f"✅ [DB查询] Token 有效 (长度: {len(api_key)})")
                                return api_key
                            else:
                                self.logger.warning("⚠️ [DB查询] Token 无效或为占位符")
                else:
                    self.logger.warning("⚠️ [DB查询] 配置中没有 data_source_configs")
            else:
                self.logger.warning("⚠️ [DB查询] 未找到激活的配置")

            self.logger.info("⚠️ [DB查询] 数据库中未找到有效的 Tushare Token")
        except Exception as e:
            self.logger.error(f"❌ [DB查询] 从数据库读取 Token 失败: {e}")
            traceback = importlib.import_module("traceback")
            self.logger.error(f"❌ [DB查询] 堆栈跟踪:\n{traceback.format_exc()}")

        return None

    def connect_sync(self) -> bool:
        """同步连接到Tushare"""
        if not TUSHARE_AVAILABLE:
            self.logger.error("❌ Tushare库不可用")
            return False

        # 测试连接超时时间（秒）- 只是测试连通性，不需要很长时间
        test_timeout = 10

        try:
            # 🔥 优先从数据库读取 Token
            self.logger.info("🔍 [步骤1] 开始从数据库读取 Tushare Token...")
            db_token = self._get_token_from_database()
            if db_token:
                self.logger.info(f"✅ [步骤1] 数据库中找到 Token (长度: {len(db_token)})")
            else:
                self.logger.info("⚠️ [步骤1] 数据库中未找到 Token")

            self.logger.info("🔍 [步骤2] 读取 .env 中的 Token...")
            env_token = self.config.get("token")
            if env_token:
                self.logger.info(f"✅ [步骤2] .env 中找到 Token (长度: {len(env_token)})")
            else:
                self.logger.info("⚠️ [步骤2] .env 中未找到 Token")

            # 尝试数据库 Token
            if db_token:
                try:
                    self.logger.info(f"🔄 [步骤3] 尝试使用数据库中的 Tushare Token (超时: {test_timeout}秒)...")
                    ts.set_token(db_token)
                    self.api = ts.pro_api()

                    # 测试连接 - 直接调用同步方法（不使用 asyncio.run）
                    try:
                        self.logger.info("🔄 [步骤3.1] 调用 stock_basic API 测试连接...")
                        test_data = self.api.stock_basic(list_status="L", limit=1)
                        self.logger.info(
                            f"✅ [步骤3.1] API 调用成功，返回数据: {len(test_data) if test_data is not None else 0} 条"
                        )
                    except Exception as e:
                        self.logger.warning(f"⚠️ [步骤3.1] 数据库 Token 测试失败: {e}，尝试降级到 .env 配置...")
                        test_data = None

                    if test_data is not None and not test_data.empty:
                        self.connected = True
                        self.token_source = "database"
                        self.logger.info("✅ [步骤3.2] Tushare连接成功 (Token来源: 数据库)")
                        return True
                    else:
                        self.logger.warning("⚠️ [步骤3.2] 数据库 Token 测试失败，尝试降级到 .env 配置...")
                except Exception as e:
                    self.logger.warning(f"⚠️ [步骤3] 数据库 Token 连接失败: {e}，尝试降级到 .env 配置...")

            # 降级到环境变量 Token
            if env_token:
                try:
                    self.logger.info(f"🔄 [步骤4] 尝试使用 .env 中的 Tushare Token (超时: {test_timeout}秒)...")
                    ts.set_token(env_token)
                    self.api = ts.pro_api()

                    # 测试连接 - 直接调用同步方法（不使用 asyncio.run）
                    try:
                        self.logger.info("🔄 [步骤4.1] 调用 stock_basic API 测试连接...")
                        test_data = self.api.stock_basic(list_status="L", limit=1)
                        self.logger.info(
                            f"✅ [步骤4.1] API 调用成功，返回数据: {len(test_data) if test_data is not None else 0} 条"
                        )
                    except Exception as e:
                        self.logger.error(f"❌ [步骤4.1] .env Token 测试失败: {e}")
                        return False

                    if test_data is not None and not test_data.empty:
                        self.connected = True
                        self.token_source = "env"
                        self.logger.info("✅ [步骤4.2] Tushare连接成功 (Token来源: .env 环境变量)")
                        return True
                    else:
                        self.logger.error("❌ [步骤4.2] .env Token 测试失败")
                        return False
                except Exception as e:
                    self.logger.error(f"❌ [步骤4] .env Token 连接失败: {e}")
                    return False

            # 两个都没有
            self.logger.error("❌ [步骤5] Tushare token未配置，请在 Web 后台或 .env 文件中配置 TUSHARE_TOKEN")
            return False

        except Exception as e:
            self.logger.error(f"❌ Tushare连接失败: {e}")
            return False

    async def connect(self) -> bool:
        """异步连接到Tushare"""
        if not TUSHARE_AVAILABLE:
            self.logger.error("❌ Tushare库不可用")
            return False

        # 测试连接超时时间（秒）- 只是测试连通性，不需要很长时间
        test_timeout = 10

        try:
            # 🔥 优先从数据库读取 Token
            db_token = self._get_token_from_database()
            env_token = self.config.get("token")

            # 尝试数据库 Token
            if db_token:
                try:
                    self.logger.info(f"🔄 尝试使用数据库中的 Tushare Token (超时: {test_timeout}秒)...")
                    ts.set_token(db_token)
                    self.api = ts.pro_api()

                    # 测试连接（异步）- 使用超时
                    try:
                        test_data = await asyncio.wait_for(
                            asyncio.to_thread(self.api.stock_basic, list_status="L", limit=1),
                            timeout=test_timeout,
                        )
                    except asyncio.TimeoutError:
                        self.logger.warning(f"⚠️ 数据库 Token 测试超时 ({test_timeout}秒)，尝试降级到 .env 配置...")
                        test_data = None

                    if test_data is not None and not test_data.empty:
                        self.connected = True
                        self.logger.info("✅ Tushare连接成功 (Token来源: 数据库)")
                        return True
                    else:
                        self.logger.warning("⚠️ 数据库 Token 测试失败，尝试降级到 .env 配置...")
                except Exception as e:
                    self.logger.warning(f"⚠️ 数据库 Token 连接失败: {e}，尝试降级到 .env 配置...")

            # 降级到环境变量 Token
            if env_token:
                try:
                    self.logger.info(f"🔄 尝试使用 .env 中的 Tushare Token (超时: {test_timeout}秒)...")
                    ts.set_token(env_token)
                    self.api = ts.pro_api()

                    # 测试连接（异步）- 使用超时
                    try:
                        test_data = await asyncio.wait_for(
                            asyncio.to_thread(self.api.stock_basic, list_status="L", limit=1),
                            timeout=test_timeout,
                        )
                    except asyncio.TimeoutError:
                        self.logger.error(f"❌ .env Token 测试超时 ({test_timeout}秒)")
                        return False

                    if test_data is not None and not test_data.empty:
                        self.connected = True
                        self.logger.info("✅ Tushare连接成功 (Token来源: .env 环境变量)")
                        return True
                    else:
                        self.logger.error("❌ .env Token 测试失败")
                        return False
                except Exception as e:
                    self.logger.error(f"❌ .env Token 连接失败: {e}")
                    return False

            # 两个都没有
            self.logger.error("❌ Tushare token未配置，请在 Web 后台或 .env 文件中配置 TUSHARE_TOKEN")
            return False

        except Exception as e:
            self.logger.error(f"❌ Tushare连接失败: {e}")
            return False

    def is_available(self) -> bool:
        """检查Tushare是否可用"""
        return TUSHARE_AVAILABLE and self.connected and self.api is not None

    def get_stock_list_sync(self, market: Optional[str] = None) -> Optional[pd.DataFrame]:
        """获取股票列表（同步版本）"""
        if not self.is_available():
            return None

        try:
            df = self.api.stock_basic(
                list_status="L",
                fields="ts_code,symbol,name,area,industry,market,exchange,list_date,is_hs",
            )
            if df is not None and not df.empty:
                self.logger.info(f"✅ 成功获取 {len(df)} 条股票数据")
                return df
            else:
                self.logger.warning("⚠️ Tushare API 返回空数据")
                return None
        except Exception as e:
            self.logger.error(f"❌ 获取股票列表失败: {e}")
            return None

    async def get_stock_list(self, market: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """获取股票列表（异步版本）"""
        if not self.is_available():
            return None

        try:
            # 构建查询参数
            params = {
                "list_status": "L",  # 只获取上市股票
                "fields": "ts_code,symbol,name,area,industry,market,exchange,list_date,is_hs",
            }

            if market:
                # 根据市场筛选
                if market == "CN":
                    params["exchange"] = "SSE,SZSE"  # 沪深交易所
                elif market == "HK":
                    return None  # Tushare港股需要单独处理
                elif market == "US":
                    return None  # Tushare不支持美股

            # 获取数据
            df = await asyncio.to_thread(self.api.stock_basic, **params)

            if df is None or df.empty:
                return None

            # 转换为标准格式
            stock_list = []
            for _, row in df.iterrows():
                stock_info = self.standardize_basic_info(row.to_dict())
                stock_list.append(stock_info)

            self.logger.info(f"✅ 获取股票列表: {len(stock_list)}只")
            return stock_list

        except Exception as e:
            self.logger.error(f"❌ 获取股票列表失败: {e}")
            return None

    async def get_stock_basic_info(
        self, symbol: Optional[str] = None
    ) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """获取股票基础信息"""
        if not self.is_available():
            return None

        try:
            if symbol:
                # 获取单个股票信息
                ts_code = self._normalize_ts_code(symbol)
                df = await asyncio.to_thread(
                    self.api.stock_basic,
                    ts_code=ts_code,
                    fields="ts_code,symbol,name,area,industry,market,exchange,list_date,is_hs,act_name,act_ent_type",
                )

                if df is None or df.empty:
                    return None

                return self.standardize_basic_info(df.iloc[0].to_dict())
            else:
                # 获取所有股票信息
                return await self.get_stock_list()

        except Exception as e:
            self.logger.error(f"❌ 获取股票基础信息失败 symbol={symbol}: {e}")
            return None

    async def get_stock_quotes(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取单只股票实时行情

        🔥 策略：使用 daily 接口获取最新一天的数据（不使用 rt_k 批量接口）
        - rt_k 接口是批量接口，单只股票调用浪费配额
        - daily 接口可以获取单只股票的最新日线数据，包含更多指标

        注意：此方法适合少量股票获取，大量股票建议使用 get_realtime_quotes_batch()
        """
        if not self.is_available():
            return None

        try:
            ts_code = self._normalize_ts_code(symbol)

            # 🔥 使用 daily 接口获取最新一天的数据（更节省配额）
            datetime = getattr(importlib.import_module("datetime"), "datetime")
            timedelta = getattr(importlib.import_module("datetime"), "timedelta")

            # 获取最近3天的数据（考虑周末和节假日）
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=3)).strftime("%Y%m%d")

            try:
                df = await asyncio.to_thread(
                    self.api.realtime_quote,
                    ts_code=ts_code,
                )
            except Exception as realtime_error:
                if self._is_rate_limit_error(str(realtime_error)):
                    raise
                self.logger.warning(f"⚠️ 实时行情接口失败，回退到daily接口 symbol={symbol}: {realtime_error}")
                df = await asyncio.to_thread(
                    self.api.daily,
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date,
                )

            if df is not None and not df.empty:
                # 取最新一天的数据
                row = df.iloc[0].to_dict()

                daily_basic = None
                try:
                    daily_basic = await asyncio.to_thread(
                        self.api.daily_basic,
                        ts_code=ts_code,
                        trade_date=row.get("trade_date"),
                    )
                except Exception:
                    daily_basic = None
                if daily_basic is not None and not daily_basic.empty:
                    row.update(daily_basic.iloc[0].to_dict())

                # 标准化字段
                quote_data = {
                    "ts_code": row.get("ts_code"),
                    "symbol": symbol,
                    "trade_date": row.get("trade_date"),
                    "open": row.get("open"),
                    "high": row.get("high"),
                    "low": row.get("low"),
                    "close": row.get("close"),  # 收盘价
                    "pre_close": row.get("pre_close"),
                    "change": row.get("change"),  # 涨跌额
                    "pct_chg": row.get("pct_chg"),  # 涨跌幅
                    "volume": row.get("volume", row.get("vol")),
                    "amount": row.get("amount"),
                    "pe": row.get("pe"),
                    "pb": row.get("pb"),
                    "turnover_rate": row.get("turnover_rate"),
                }

                return self.standardize_quotes(quote_data)

            return None

        except Exception as e:
            # 检查是否为限流错误
            if self._is_rate_limit_error(str(e)):
                self.logger.error(f"❌ 获取实时行情失败（限流） symbol={symbol}: {e}")
                raise  # 抛出限流错误，让上层处理

            self.logger.error(f"❌ 获取实时行情失败 symbol={symbol}: {e}")
            return None

    async def get_realtime_quotes_batch(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        批量获取全市场实时行情
        使用 rt_k 接口的通配符功能，一次性获取所有A股实时行情

        Returns:
            Dict[str, Dict]: {symbol: quote_data}
            例如: {'000001': {'close': 10.5, 'pct_chg': 1.2, ...}, ...}
        """
        if not self.is_available():
            return None

        try:
            # 使用通配符一次性获取全市场行情
            # 3*.SZ: 创业板  6*.SH: 上交所  0*.SZ: 深交所主板  9*.BJ: 北交所
            df = await asyncio.to_thread(self.api.rt_k, ts_code="3*.SZ,6*.SH,0*.SZ,9*.BJ")

            if df is None or df.empty:
                self.logger.warning("⚠️ rt_k 接口返回空数据")
                return None

            self.logger.info(f"✅ 获取到 {len(df)} 只股票的实时行情")

            # 🔥 获取当前日期（UTC+8）
            datetime = getattr(importlib.import_module("datetime"), "datetime")
            timezone = getattr(importlib.import_module("datetime"), "timezone")
            timedelta = getattr(importlib.import_module("datetime"), "timedelta")
            cn_tz = timezone(timedelta(hours=8))
            now_cn = datetime.now(cn_tz)
            trade_date = now_cn.strftime("%Y%m%d")  # 格式：20251114（与 Tushare 格式一致）

            # 转换为字典格式
            result = {}
            for _, row in df.iterrows():
                ts_code = row.get("ts_code")
                if not ts_code or "." not in ts_code:
                    continue

                # 提取6位代码
                symbol = ts_code.split(".")[0]

                # 构建行情数据
                quote_data = {
                    "ts_code": ts_code,
                    "symbol": symbol,
                    "name": row.get("name"),
                    "open": row.get("open"),
                    "high": row.get("high"),
                    "low": row.get("low"),
                    "close": row.get("close"),  # 当前价
                    "pre_close": row.get("pre_close"),
                    "volume": row.get("vol"),  # 成交量（股）
                    "amount": row.get("amount"),  # 成交额（元）
                    "num": row.get("num"),  # 成交笔数
                    "trade_date": trade_date,  # 🔥 添加交易日期字段
                }

                # 计算涨跌幅
                if quote_data.get("close") and quote_data.get("pre_close"):
                    try:
                        close = float(quote_data["close"])
                        pre_close = float(quote_data["pre_close"])
                        if pre_close > 0:
                            pct_chg = ((close - pre_close) / pre_close) * 100
                            quote_data["pct_chg"] = round(pct_chg, 2)
                            quote_data["change"] = round(close - pre_close, 2)
                    except (ValueError, TypeError):
                        pass

                result[symbol] = quote_data

            return result

        except Exception as e:
            # 检查是否为限流错误
            if self._is_rate_limit_error(str(e)):
                self.logger.error(f"❌ 批量获取实时行情失败（限流）: {e}")
                raise  # 抛出限流错误，让上层处理

            self.logger.error(f"❌ 批量获取实时行情失败: {e}")
            return None

    def _is_rate_limit_error(self, error_msg: str) -> bool:
        """检测是否为 API 限流错误"""
        rate_limit_keywords = [
            "每分钟最多访问",
            "每分钟最多",
            "rate limit",
            "too many requests",
            "访问频率",
            "请求过于频繁",
        ]
        error_msg_lower = error_msg.lower()
        return any(keyword in error_msg_lower for keyword in rate_limit_keywords)

    async def get_historical_data(
        self,
        symbol: str,
        start_date: Union[str, date],
        end_date: Optional[Union[str, date]] = None,
        period: str = "daily",
    ) -> Optional[pd.DataFrame]:
        """
        获取历史数据

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 数据周期 (daily/weekly/monthly)
        """
        if not self.is_available():
            return None

        try:
            ts_code = self._normalize_ts_code(symbol)

            # 格式化日期
            start_str = self._format_date(start_date)
            end_str = self._format_date(end_date) if end_date else datetime.now().strftime("%Y%m%d")

            # 🔧 使用 pro_bar 接口获取前复权数据（与同花顺一致）
            # 注意：Tushare 的 daily/weekly/monthly 接口不支持复权
            # 必须使用 ts.pro_bar() 函数并指定 adj='qfq' 参数

            # 周期映射
            freq_map = {"daily": "D", "weekly": "W", "monthly": "M"}
            freq = freq_map.get(period, "D")

            # 使用 ts.pro_bar() 函数获取前复权数据
            # 注意：pro_bar 是 tushare 模块的函数，不是 api 对象的方法
            df = await asyncio.to_thread(
                ts.pro_bar,
                ts_code=ts_code,
                api=self.api,  # 传入 api 对象
                start_date=start_str,
                end_date=end_str,
                freq=freq,
                adj="qfq",  # 前复权（与同花顺一致）
            )

            if df is None or df.empty:
                self.logger.warning(
                    f"⚠️ Tushare API 返回空数据: symbol={symbol}, ts_code={ts_code}, "
                    f"period={period}, start={start_str}, end={end_str}"
                )
                self.logger.warning(
                    "💡 可能原因: "
                    "1) 该股票在此期间无交易数据 "
                    "2) 日期范围不正确 "
                    "3) 股票代码格式错误 "
                    "4) Tushare API 限制或积分不足"
                )
                return None

            # 数据标准化
            df = self._standardize_historical_data(df)

            self.logger.info(f"✅ 获取{period}历史数据: {symbol} {len(df)}条记录 (前复权 qfq)")
            return df

        except Exception as e:
            traceback = importlib.import_module("traceback")
            error_details = traceback.format_exc()
            self.logger.error(
                f"❌ 获取历史数据失败 symbol={symbol}, period={period}\n"
                f"   参数: ts_code={ts_code if 'ts_code' in locals() else 'N/A'}, "
                f"start={start_str if 'start_str' in locals() else 'N/A'}, "
                f"end={end_str if 'end_str' in locals() else 'N/A'}\n"
                f"   错误类型: {type(e).__name__}\n"
                f"   错误信息: {str(e)}\n"
                f"   堆栈跟踪:\n{error_details}"
            )
            return None

    async def get_daily_basic(self, trade_date: str) -> Optional[pd.DataFrame]:
        """获取每日基础财务数据"""
        if not self.is_available():
            return None

        try:
            date_str = trade_date.replace("-", "")
            df = await asyncio.to_thread(
                self.api.daily_basic,
                trade_date=date_str,
                fields="ts_code,total_mv,circ_mv,pe,pb,turnover_rate,volume_ratio,pe_ttm,pb_mrq",
            )

            if df is not None and not df.empty:
                self.logger.info(f"✅ 获取每日基础数据: {trade_date} {len(df)}条记录")
                return df

            return None

        except Exception as e:
            self.logger.error(f"❌ 获取每日基础数据失败 trade_date={trade_date}: {e}")
            return None

    async def find_latest_trade_date(self) -> Optional[str]:
        """查找最新交易日期"""
        if not self.is_available():
            return None

        try:
            today = datetime.now()
            for delta in range(0, 10):  # 最多回溯10天
                check_date = (today - timedelta(days=delta)).strftime("%Y%m%d")

                try:
                    df = await asyncio.to_thread(
                        self.api.daily_basic,
                        trade_date=check_date,
                        fields="ts_code",
                        limit=1,
                    )

                    if df is not None and not df.empty:
                        formatted_date = f"{check_date[:4]}-{check_date[4:6]}-{check_date[6:8]}"
                        self.logger.info(f"✅ 找到最新交易日期: {formatted_date}")
                        return formatted_date

                except Exception:
                    continue

            return None

        except Exception as e:
            self.logger.error(f"❌ 查找最新交易日期失败: {e}")
            return None
