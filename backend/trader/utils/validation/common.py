# ruff: noqa: F401,F403,F405,F821
class _StockDataPreparerMixin1:
    def __init__(self, default_period_days: int = 30):
        self.timeout_seconds = 15  # 数据获取超时时间
        self.default_period_days = default_period_days  # 默认历史数据时长（天）

    def prepare_stock_data(
        self,
        stock_code: str,
        market_type: str = "auto",
        period_days: Optional[int] = None,
        analysis_date: Optional[str] = None,
    ) -> StockDataPreparationResult:
        """
        预获取和验证股票数据

        Args:
            stock_code: 股票代码
            market_type: 市场类型 ("A股", "港股", "美股", "auto")
            period_days: 历史数据时长（天），默认使用类初始化时的值
            analysis_date: 分析日期，默认为今天

        Returns:
            StockDataPreparationResult: 数据准备结果
        """
        if period_days is None:
            period_days = self.default_period_days

        if analysis_date is None:
            analysis_date = datetime.now().strftime("%Y-%m-%d")

        logger.info(
            f"📊 [数据准备] 开始准备股票数据: {stock_code} (市场: {market_type}, 时长: {period_days}天)"
        )

        # 1. 基本格式验证
        format_result = self._validate_format(stock_code, market_type)
        if not format_result.is_valid:
            return format_result

        # 2. 自动检测市场类型
        if market_type == "auto":
            market_type = self._detect_market_type(stock_code)
            logger.debug(f"📊 [数据准备] 自动检测市场类型: {market_type}")

        # 3. 预获取数据并验证
        return self._prepare_data_by_market(
            stock_code, market_type, period_days, analysis_date
        )

    def _validate_format(
        self, stock_code: str, market_type: str
    ) -> StockDataPreparationResult:
        """验证股票代码格式"""
        stock_code = stock_code.strip()

        if not stock_code:
            return StockDataPreparationResult(
                is_valid=False,
                stock_code=stock_code,
                error_message="股票代码不能为空",
                suggestion="请输入有效的股票代码",
            )

        if len(stock_code) > 10:
            return StockDataPreparationResult(
                is_valid=False,
                stock_code=stock_code,
                error_message="股票代码长度不能超过10个字符",
                suggestion="请检查股票代码格式",
            )

        # 根据市场类型验证格式
        if market_type == "A股":
            if not re.match(r"^\d{6}$", stock_code):
                return StockDataPreparationResult(
                    is_valid=False,
                    stock_code=stock_code,
                    market_type="A股",
                    error_message="A股代码格式错误，应为6位数字",
                    suggestion="请输入6位数字的A股代码，如：000001、600519",
                )
        elif market_type == "港股":
            stock_code_upper = stock_code.upper()
            hk_format = re.match(r"^\d{4,5}\.HK$", stock_code_upper)
            digit_format = re.match(r"^\d{4,5}$", stock_code)

            if not (hk_format or digit_format):
                return StockDataPreparationResult(
                    is_valid=False,
                    stock_code=stock_code,
                    market_type="港股",
                    error_message="港股代码格式错误",
                    suggestion="请输入4-5位数字.HK格式（如：0700.HK）或4-5位数字（如：0700）",
                )
        elif market_type == "美股":
            if not re.match(r"^[A-Z]{1,5}$", stock_code.upper()):
                return StockDataPreparationResult(
                    is_valid=False,
                    stock_code=stock_code,
                    market_type="美股",
                    error_message="美股代码格式错误，应为1-5位字母",
                    suggestion="请输入1-5位字母的美股代码，如：AAPL、TSLA",
                )

        return StockDataPreparationResult(
            is_valid=True, stock_code=stock_code, market_type=market_type
        )

    def _detect_market_type(self, stock_code: str) -> str:
        """自动检测市场类型"""
        stock_code = stock_code.strip().upper()

        # A股：6位数字
        if re.match(r"^\d{6}$", stock_code):
            return "A股"

        # 港股：4-5位数字.HK 或 纯4-5位数字
        if re.match(r"^\d{4,5}\.HK$", stock_code) or re.match(r"^\d{4,5}$", stock_code):
            return "港股"

        # 美股：1-5位字母
        if re.match(r"^[A-Z]{1,5}$", stock_code):
            return "美股"

        return "未知"

    def _get_hk_network_limitation_suggestion(self) -> str:
        """获取港股网络限制的详细建议"""
        suggestions = [
            "🌐 港股数据获取受到网络API限制，这是常见的临时问题",
            "",
            "💡 解决方案：",
            "1. 等待5-10分钟后重试（API限制通常会自动解除）",
            "2. 检查网络连接是否稳定",
            "3. 如果是知名港股（如腾讯0700.HK、阿里9988.HK），代码格式通常正确",
            "4. 可以尝试使用其他时间段进行分析",
            "",
            "📋 常见港股代码格式：",
            "• 腾讯控股：0700.HK",
            "• 阿里巴巴：9988.HK",
            "• 美团：3690.HK",
            "• 小米集团：1810.HK",
            "",
            "⏰ 建议稍后重试，或联系技术支持获取帮助",
        ]
        return "\n".join(suggestions)

    def _missing_history_suggestion(
        self,
        *,
        has_basic_info: bool,
        stock_code: str,
        analysis_date: Optional[str],
    ) -> str:
        if has_basic_info:
            date_hint = f"分析日期 {analysis_date} 附近" if analysis_date else "分析日期附近"
            return (
                f"{date_hint}没有可用交易数据。该股票可能处于停牌、退市、终止上市、换股合并"
                "或长期无交易状态；请改用仍在交易的承继/相关证券代码，或把分析日期调整到"
                "该股票仍有交易记录的历史日期。"
            )
        return "请检查网络连接或数据源配置，或稍后重试"

    def _extract_hk_stock_name(self, stock_info, stock_code: str) -> str:
        """从港股信息中提取股票名称，支持多种格式"""
        if not stock_info:
            return "未知"

        # 处理不同类型的返回值
        if isinstance(stock_info, dict):
            # 如果是字典，尝试从常见字段提取名称
            name_fields = [
                "name",
                "longName",
                "shortName",
                "companyName",
                "公司名称",
                "股票名称",
            ]
            for field in name_fields:
                if field in stock_info and stock_info[field]:
                    name = str(stock_info[field]).strip()
                    if name and name != "未知":
                        return name

            # 如果字典包含有效信息但没有名称字段，使用股票代码
            if len(stock_info) > 0:
                return stock_code
            return "未知"

        # 转换为字符串处理
        stock_info_str = str(stock_info)

        # 方法1: 标准格式 "公司名称: XXX"
        if "公司名称:" in stock_info_str:
            lines = stock_info_str.split("\n")
            for line in lines:
                if "公司名称:" in line:
                    name = line.split(":")[1].strip()
                    if name and name != "未知":
                        return name

        # 方法2: Yahoo Finance格式检测
        # 日志显示: "✅ Yahoo Finance成功获取港股信息: 0700.HK -> TENCENT"
        if "Yahoo Finance成功获取港股信息" in stock_info_str:
            # 从日志中提取名称
            if " -> " in stock_info_str:
                parts = stock_info_str.split(" -> ")
                if len(parts) > 1:
                    name = parts[-1].strip()
                    if name and name != "未知":
                        return name

        # 方法3: 检查是否包含常见的公司名称关键词
        company_indicators = [
            "Limited",
            "Ltd",
            "Corporation",
            "Corp",
            "Inc",
            "Group",
            "Holdings",
            "Company",
            "Co",
            "集团",
            "控股",
            "有限公司",
        ]

        lines = stock_info_str.split("\n")
        for line in lines:
            line = line.strip()
            if any(indicator in line for indicator in company_indicators):
                # 尝试提取公司名称
                if ":" in line:
                    potential_name = line.split(":")[-1].strip()
                    if potential_name and len(potential_name) > 2:
                        return potential_name
                elif len(line) > 2 and len(line) < 100:  # 合理的公司名称长度
                    return line

        # 方法4: 如果信息看起来有效但无法解析名称，使用股票代码
        if len(stock_info_str) > 50 and "❌" not in stock_info_str:
            # 信息看起来有效，但无法解析名称，使用代码作为名称
            return stock_code

        return "未知"

    def _prepare_data_by_market(
        self, stock_code: str, market_type: str, period_days: int, analysis_date: str
    ) -> StockDataPreparationResult:
        """根据市场类型预获取数据"""
        logger.debug(f"📊 [数据准备] 开始为{market_type}股票{stock_code}准备数据")

        try:
            if market_type == "A股":
                return self._prepare_china_stock_data(
                    stock_code, period_days, analysis_date
                )
            elif market_type == "港股":
                return self._prepare_hk_stock_data(
                    stock_code, period_days, analysis_date
                )
            elif market_type == "美股":
                return self._prepare_us_stock_data(
                    stock_code, period_days, analysis_date
                )
            else:
                return StockDataPreparationResult(
                    is_valid=False,
                    stock_code=stock_code,
                    market_type=market_type,
                    error_message=f"不支持的市场类型: {market_type}",
                    suggestion="请选择支持的市场类型：A股、港股、美股",
                )
        except Exception as e:
            logger.error(f"❌ [数据准备] 数据准备异常: {e}")
            return StockDataPreparationResult(
                is_valid=False,
                stock_code=stock_code,
                market_type=market_type,
                error_message=f"数据准备过程中发生错误: {str(e)}",
                suggestion="请检查网络连接或稍后重试",
            )

    async def _prepare_data_by_market_async(
        self, stock_code: str, market_type: str, period_days: int, analysis_date: str
    ) -> StockDataPreparationResult:
        """根据市场类型预获取数据（异步版本）"""
        logger.debug(f"📊 [数据准备-异步] 开始为{market_type}股票{stock_code}准备数据")

        try:
            if market_type == "A股":
                return await self._prepare_china_stock_data_async(
                    stock_code, period_days, analysis_date
                )
            elif market_type == "港股":
                return self._prepare_hk_stock_data(
                    stock_code, period_days, analysis_date
                )
            elif market_type == "美股":
                return self._prepare_us_stock_data(
                    stock_code, period_days, analysis_date
                )
            else:
                return StockDataPreparationResult(
                    is_valid=False,
                    stock_code=stock_code,
                    market_type=market_type,
                    error_message=f"不支持的市场类型: {market_type}",
                    suggestion="请选择支持的市场类型：A股、港股、美股",
                )
        except Exception as e:
            logger.error(f"❌ [数据准备-异步] 数据准备异常: {e}")
            return StockDataPreparationResult(
                is_valid=False,
                stock_code=stock_code,
                market_type=market_type,
                error_message=f"数据准备过程中发生错误: {str(e)}",
                suggestion="请检查网络连接或稍后重试",
            )

    def _prepare_china_stock_data(
        self, stock_code: str, period_days: int, analysis_date: str
    ) -> StockDataPreparationResult:
        """预获取A股数据，包含数据库检查和自动同步"""
        logger.info(f"📊 [A股数据] 开始准备{stock_code}的数据 (时长: {period_days}天)")

        # 计算日期范围（使用扩展后的日期范围，与get_china_stock_data_unified保持一致）
        end_date = datetime.strptime(analysis_date, "%Y-%m-%d")

        # 获取配置的回溯天数（与get_china_stock_data_unified保持一致）
        settings = getattr(importlib.import_module("app.core.config"), "settings")
        lookback_days = getattr(settings, "MARKET_ANALYST_LOOKBACK_DAYS", 365)

        # 使用扩展后的日期范围进行数据检查和同步
        extended_start_date = end_date - timedelta(days=lookback_days)
        extended_start_date_str = extended_start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        logger.info(
            f"📅 [A股数据] 实际数据范围: {extended_start_date_str} 到 {end_date_str} ({lookback_days}天)"
        )

        has_historical_data = False
        has_basic_info = False
        stock_name = "未知"
        cache_status = ""

        try:
            # 1. 检查数据库中的数据是否存在和最新
            logger.debug(f"📊 [A股数据] 检查数据库中{stock_code}的数据...")
            db_check_result = self._check_database_data(
                stock_code, extended_start_date_str, end_date_str
            )

            # 2. 如果数据不存在或不是最新，自动触发同步
            if not db_check_result["has_data"] or not db_check_result["is_latest"]:
                logger.warning(
                    f"⚠️ [A股数据] 数据库数据不完整: {db_check_result['message']}"
                )
                logger.info(f"🔄 [A股数据] 自动触发数据同步: {stock_code}")

                # 使用扩展后的日期范围进行同步
                sync_result = self._trigger_data_sync_sync(
                    stock_code, extended_start_date_str, end_date_str
                )
                if sync_result["success"]:
                    logger.info(f"✅ [A股数据] 数据同步成功: {sync_result['message']}")
                    cache_status += "数据已同步; "
                else:
                    logger.warning(
                        f"⚠️ [A股数据] 数据同步失败: {sync_result['message']}"
                    )
                    # 继续尝试从API获取数据
            else:
                logger.info(
                    f"✅ [A股数据] 数据库数据检查通过: {db_check_result['message']}"
                )
                cache_status += "数据库数据最新; "

            # 3. 获取基本信息
            logger.debug(f"📊 [A股数据] 获取{stock_code}基本信息...")
            get_china_stock_info_unified = getattr(
                importlib.import_module("trader.flows.interface"),
                "get_china_stock_info_unified",
            )

            stock_info = get_china_stock_info_unified(stock_code)

            if stock_info and "❌" not in stock_info and "未能获取" not in stock_info:
                # 解析股票名称
                if "股票名称:" in stock_info:
                    lines = stock_info.split("\n")
                    for line in lines:
                        if "股票名称:" in line:
                            stock_name = line.split(":")[1].strip()
                            break

                # 检查是否为有效的股票名称
                if stock_name != "未知" and not stock_name.startswith(
                    f"股票{stock_code}"
                ):
                    has_basic_info = True
                    logger.info(
                        f"✅ [A股数据] 基本信息获取成功: {stock_code} - {stock_name}"
                    )
                    cache_status += "基本信息已缓存; "
                else:
                    logger.warning(f"⚠️ [A股数据] 基本信息无效: {stock_code}")
                    return StockDataPreparationResult(
                        is_valid=False,
                        stock_code=stock_code,
                        market_type="A股",
                        error_message=f"股票代码 {stock_code} 不存在或信息无效",
                        suggestion="请检查股票代码是否正确，或确认该股票是否已上市",
                    )
            else:
                logger.warning(f"⚠️ [A股数据] 无法获取基本信息: {stock_code}")
                return StockDataPreparationResult(
                    is_valid=False,
                    stock_code=stock_code,
                    market_type="A股",
                    error_message=f"无法获取股票 {stock_code} 的基本信息",
                    suggestion="请检查股票代码是否正确，或确认该股票是否已上市",
                )

            # 4. 获取历史数据（使用扩展后的日期范围）
            logger.debug(
                f"📊 [A股数据] 获取{stock_code}历史数据 ({extended_start_date_str} 到 {end_date_str})..."
            )
            get_china_stock_data_unified = getattr(
                importlib.import_module("trader.flows.interface"),
                "get_china_stock_data_unified",
            )

            historical_data = get_china_stock_data_unified(
                stock_code, extended_start_date_str, end_date_str
            )

            if (
                historical_data
                and "❌" not in historical_data
                and "获取失败" not in historical_data
            ):
                # 更宽松的数据有效性检查
                data_indicators = [
                    "开盘价",
                    "收盘价",
                    "最高价",
                    "最低价",
                    "成交量",
                    "open",
                    "close",
                    "high",
                    "low",
                    "volume",
                    "日期",
                    "date",
                    "时间",
                    "time",
                ]

                has_valid_data = (
                    len(historical_data) > 50  # 降低长度要求
                    and any(
                        indicator in historical_data for indicator in data_indicators
                    )
                )

                if has_valid_data:
                    has_historical_data = True
                    logger.info(
                        f"✅ [A股数据] 历史数据获取成功: {stock_code} ({lookback_days}天)"
                    )
                    cache_status += f"历史数据已缓存({lookback_days}天); "
                else:
                    logger.warning(f"⚠️ [A股数据] 历史数据无效: {stock_code}")
                    logger.debug(
                        f"🔍 [A股数据] 数据内容预览: {historical_data[:200]}..."
                    )
                    return StockDataPreparationResult(
                        is_valid=False,
                        stock_code=stock_code,
                        market_type="A股",
                        stock_name=stock_name,
                        has_basic_info=has_basic_info,
                        error_message=f"股票 {stock_code} 的历史数据无效或不足",
                        suggestion="该股票可能为新上市股票或数据源暂时不可用，请稍后重试",
                    )
            else:
                logger.warning(f"⚠️ [A股数据] 无法获取历史数据: {stock_code}")
                return StockDataPreparationResult(
                    is_valid=False,
                    stock_code=stock_code,
                    market_type="A股",
                    stock_name=stock_name,
                    has_basic_info=has_basic_info,
                    error_message=f"无法获取股票 {stock_code} 的历史数据",
                    suggestion=self._missing_history_suggestion(
                        has_basic_info=has_basic_info,
                        stock_code=stock_code,
                        analysis_date=analysis_date,
                    ),
                )

            # 5. 数据准备成功
            logger.info(f"🎉 [A股数据] 数据准备完成: {stock_code} - {stock_name}")
            return StockDataPreparationResult(
                is_valid=True,
                stock_code=stock_code,
                market_type="A股",
                stock_name=stock_name,
                has_historical_data=has_historical_data,
                has_basic_info=has_basic_info,
                data_period_days=lookback_days,  # 使用实际的数据天数
                cache_status=cache_status.rstrip("; "),
            )

        except Exception as e:
            logger.error(f"❌ [A股数据] 数据准备失败: {e}")
            traceback = importlib.import_module("traceback")
            logger.debug(f"详细错误: {traceback.format_exc()}")
            return StockDataPreparationResult(
                is_valid=False,
                stock_code=stock_code,
                market_type="A股",
                stock_name=stock_name,
                has_basic_info=has_basic_info,
                has_historical_data=has_historical_data,
                error_message=f"数据准备失败: {str(e)}",
                suggestion="请检查网络连接或数据源配置",
            )

    async def _prepare_china_stock_data_async(
        self, stock_code: str, period_days: int, analysis_date: str
    ) -> StockDataPreparationResult:
        """预获取A股数据（异步版本），包含数据库检查和自动同步"""
        logger.info(
            f"📊 [A股数据-异步] 开始准备{stock_code}的数据 (时长: {period_days}天)"
        )

        # 计算日期范围
        end_date = datetime.strptime(analysis_date, "%Y-%m-%d")
        settings = getattr(importlib.import_module("app.core.config"), "settings")
        lookback_days = getattr(settings, "MARKET_ANALYST_LOOKBACK_DAYS", 365)
        extended_start_date = end_date - timedelta(days=lookback_days)
        extended_start_date_str = extended_start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        logger.info(
            f"📅 [A股数据-异步] 实际数据范围: {extended_start_date_str} 到 {end_date_str} ({lookback_days}天)"
        )

        has_historical_data = False
        has_basic_info = False
        stock_name = "未知"
        cache_status = ""

        try:
            # 1. 检查数据库中的数据是否存在和最新
            logger.debug(f"📊 [A股数据-异步] 检查数据库中{stock_code}的数据...")
            db_check_result = self._check_database_data(
                stock_code, extended_start_date_str, end_date_str
            )

            # 2. 如果数据不存在或不是最新，自动触发同步（使用异步方法）
            if not db_check_result["has_data"] or not db_check_result["is_latest"]:
                logger.warning(
                    f"⚠️ [A股数据-异步] 数据库数据不完整: {db_check_result['message']}"
                )
                logger.info(f"🔄 [A股数据-异步] 自动触发数据同步: {stock_code}")

                # 🔥 使用异步方法同步数据
                sync_result = await self._trigger_data_sync_async(
                    stock_code, extended_start_date_str, end_date_str
                )
                if sync_result["success"]:
                    logger.info(
                        f"✅ [A股数据-异步] 数据同步成功: {sync_result['message']}"
                    )
                    cache_status += "数据已同步; "
                else:
                    logger.warning(
                        f"⚠️ [A股数据-异步] 数据同步失败: {sync_result['message']}"
                    )
            else:
                logger.info(
                    f"✅ [A股数据-异步] 数据库数据检查通过: {db_check_result['message']}"
                )
                cache_status += "数据库数据最新; "

            # 3. 获取基本信息（同步操作）
            logger.debug(f"📊 [A股数据-异步] 获取{stock_code}基本信息...")
            get_china_stock_info_unified = getattr(
                importlib.import_module("trader.flows.interface"),
                "get_china_stock_info_unified",
            )
            stock_info = get_china_stock_info_unified(stock_code)

            if stock_info and "❌" not in stock_info and "未能获取" not in stock_info:
                if "股票名称:" in stock_info:
                    lines = stock_info.split("\n")
                    for line in lines:
                        if "股票名称:" in line:
                            stock_name = line.split(":")[1].strip()
                            break

                if stock_name != "未知" and not stock_name.startswith(
                    f"股票{stock_code}"
                ):
                    has_basic_info = True
                    logger.info(
                        f"✅ [A股数据-异步] 基本信息获取成功: {stock_code} - {stock_name}"
                    )
                    cache_status += "基本信息已缓存; "

            # 4. 获取历史数据（同步操作）
            logger.debug(f"📊 [A股数据-异步] 获取{stock_code}历史数据...")
            get_china_stock_data_unified = getattr(
                importlib.import_module("trader.flows.interface"),
                "get_china_stock_data_unified",
            )
            historical_data = get_china_stock_data_unified(
                stock_code, extended_start_date_str, end_date_str
            )

            if (
                historical_data
                and "❌" not in historical_data
                and "获取失败" not in historical_data
            ):
                data_indicators = ["开盘价", "收盘价", "最高价", "最低价", "成交量"]
                has_valid_data = len(historical_data) > 50 and any(
                    indicator in historical_data for indicator in data_indicators
                )

                if has_valid_data:
                    has_historical_data = True
                    logger.info(f"✅ [A股数据-异步] 历史数据获取成功: {stock_code}")
                    cache_status += f"历史数据已缓存({lookback_days}天); "
                else:
                    return StockDataPreparationResult(
                        is_valid=False,
                        stock_code=stock_code,
                        market_type="A股",
                        stock_name=stock_name,
                        has_basic_info=has_basic_info,
                        error_message=f"股票 {stock_code} 的历史数据无效或不足",
                        suggestion="该股票可能为新上市股票或数据源暂时不可用，请稍后重试",
                    )
            else:
                return StockDataPreparationResult(
                    is_valid=False,
                    stock_code=stock_code,
                    market_type="A股",
                    stock_name=stock_name,
                    has_basic_info=has_basic_info,
                    error_message=f"无法获取股票 {stock_code} 的历史数据",
                    suggestion=self._missing_history_suggestion(
                        has_basic_info=has_basic_info,
                        stock_code=stock_code,
                        analysis_date=analysis_date,
                    ),
                )

            # 5. 数据准备成功
            logger.info(f"🎉 [A股数据-异步] 数据准备完成: {stock_code} - {stock_name}")
            return StockDataPreparationResult(
                is_valid=True,
                stock_code=stock_code,
                market_type="A股",
                stock_name=stock_name,
                has_historical_data=has_historical_data,
                has_basic_info=has_basic_info,
                data_period_days=lookback_days,
                cache_status=cache_status.rstrip("; "),
            )

        except Exception as e:
            logger.error(f"❌ [A股数据-异步] 数据准备失败: {e}")
            traceback = importlib.import_module("traceback")
            logger.debug(f"详细错误: {traceback.format_exc()}")
            return StockDataPreparationResult(
                is_valid=False,
                stock_code=stock_code,
                market_type="A股",
                stock_name=stock_name,
                has_basic_info=has_basic_info,
                has_historical_data=has_historical_data,
                error_message=f"数据准备失败: {str(e)}",
                suggestion="请检查网络连接或数据源配置",
            )
