from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .imports import (
        Dict,
        StockDataPreparationResult,
        datetime,
        importlib,
        logger,
        timedelta,
    )

class _StockDataPreparerMixin2:
    def _check_database_data(self, stock_code: str, start_date: str, end_date: str) -> Dict:
        """
        检查数据库中的数据是否存在和最新

        Returns:
            Dict: {
                "has_data": bool,  # 是否有数据
                "is_latest": bool,  # 是否最新（包含最近交易日）
                "record_count": int,  # 记录数
                "latest_date": str,  # 最新数据日期
                "message": str  # 检查结果消息
            }
        """
        try:
            get_postgres_cache_adapter = getattr(
                importlib.import_module("trader.flows.cache.postgres"),
                "get_postgres_cache_adapter",
            )

            adapter = get_postgres_cache_adapter()
            if not adapter.use_app_cache or adapter.db is None:
                return {
                    "has_data": False,
                    "is_latest": False,
                    "record_count": 0,
                    "latest_date": None,
                    "message": "PostgreSQL缓存未启用",
                }

            # 查询数据库中的历史数据
            df = adapter.get_historical_data(stock_code, start_date, end_date)

            if df is None or df.empty:
                return {
                    "has_data": False,
                    "is_latest": False,
                    "record_count": 0,
                    "latest_date": None,
                    "message": "数据库中没有数据",
                }

            # 检查数据量
            record_count = len(df)

            # 获取最新数据日期
            if "trade_date" in df.columns:
                latest_date = df["trade_date"].max()
            elif "date" in df.columns:
                latest_date = df["date"].max()
            else:
                latest_date = None

            today = datetime.now()

            # 获取最近的交易日（考虑周末）
            recent_trade_date = today
            for i in range(5):  # 最多回溯5天
                check_date = today - timedelta(days=i)
                if check_date.weekday() < 5:  # 周一到周五
                    recent_trade_date = check_date
                    break

            recent_trade_date_str = recent_trade_date.strftime("%Y-%m-%d")

            # 判断数据是否最新（允许1天的延迟）
            is_latest = False
            if latest_date is not None:
                latest_date_str = str(latest_date)[:10]  # 取前10个字符 YYYY-MM-DD
                latest_dt = datetime.strptime(latest_date_str, "%Y-%m-%d")
                days_diff = (recent_trade_date - latest_dt).days
                is_latest = days_diff <= 1  # 允许1天延迟

            message = f"找到{record_count}条记录，最新日期: {latest_date}"
            if not is_latest:
                message += f"（需要更新到{recent_trade_date_str}）"

            return {
                "has_data": True,
                "is_latest": is_latest,
                "record_count": record_count,
                "latest_date": str(latest_date) if latest_date is not None else None,
                "message": message,
            }

        except Exception as e:
            logger.error(f"❌ [数据检查] 检查数据库数据失败: {e}")
            return {
                "has_data": False,
                "is_latest": False,
                "record_count": 0,
                "latest_date": None,
                "message": f"检查失败: {str(e)}",
            }

    def _trigger_data_sync_sync(self, stock_code: str, start_date: str, end_date: str) -> Dict:
        """
        触发数据同步（同步包装器）
        在同步上下文中调用异步同步方法

        🔥 兼容 asyncio.to_thread() 调用：
        - 如果在 asyncio.to_thread() 创建的线程中运行，创建新的事件循环
        - 避免 "attached to a different loop" 错误
        """
        asyncio = importlib.import_module("asyncio")

        try:
            # 🔥 检测是否有正在运行的事件循环
            # 如果有，说明我们在 asyncio.to_thread() 创建的线程中，需要创建新的事件循环
            try:
                asyncio.get_running_loop()
                # 有正在运行的循环，说明在异步上下文中，不能使用 run_until_complete
                # 创建新的事件循环在新线程中运行
                logger.info("🔍 [数据同步] 检测到正在运行的事件循环，创建新事件循环")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(self._trigger_data_sync_async(stock_code, start_date, end_date))
                finally:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                    loop.run_until_complete(loop.shutdown_default_executor())
                    loop.close()
                    asyncio.set_event_loop(None)
            except RuntimeError:
                # 没有正在运行的循环，可以安全地获取或创建事件循环
                created_loop = False
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        created_loop = True
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    created_loop = True

                # 调用异步方法
                try:
                    return loop.run_until_complete(self._trigger_data_sync_async(stock_code, start_date, end_date))
                finally:
                    if created_loop:
                        loop.run_until_complete(loop.shutdown_asyncgens())
                        loop.run_until_complete(loop.shutdown_default_executor())
                        loop.close()
                        asyncio.set_event_loop(None)
        except Exception as e:
            logger.error(f"❌ [数据同步] 同步包装器失败: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"同步失败: {str(e)}",
                "synced_records": 0,
                "data_source": None,
            }

    async def _trigger_data_sync_async(self, stock_code: str, start_date: str, end_date: str) -> Dict:
        """
        触发数据同步（异步版本，根据数据库配置的数据源优先级）
        同步内容包括：历史数据、财务数据、实时行情

        Returns:
            Dict: {
                "success": bool,
                "message": str,
                "synced_records": int,
                "data_source": str,  # 使用的数据源
                "historical_records": int,  # 历史数据记录数
                "financial_synced": bool,  # 财务数据是否同步成功
                "realtime_synced": bool  # 实时行情是否同步成功
            }
        """
        try:
            logger.info(f"🔄 [数据同步] 开始同步{stock_code}的数据（历史+财务+实时）...")

            # 1. 从数据库获取数据源优先级
            priority_order = self._get_data_source_priority_for_sync(stock_code)
            logger.info(f"📊 [数据同步] 数据源优先级: {priority_order}")

            # 2. 按优先级尝试同步
            last_error = None
            for data_source in priority_order:
                try:
                    logger.info(f"🔄 [数据同步] 尝试使用数据源: {data_source}")

                    # BaoStock 不支持单个股票同步，跳过
                    if data_source == "baostock":
                        logger.warning("⚠️ [数据同步] BaoStock不支持单个股票同步，跳过")
                        last_error = f"{data_source}: 不支持单个股票同步"
                        continue

                    # 根据数据源获取对应的同步服务
                    if data_source == "tushare":
                        get_tushare_sync_service = getattr(
                            importlib.import_module("app.worker.tushare.sync"),
                            "get_tushare_sync_service",
                        )
                        service = await get_tushare_sync_service()
                    elif data_source == "akshare":
                        get_akshare_sync_service = getattr(
                            importlib.import_module("app.worker.akshare.sync"),
                            "get_akshare_sync_service",
                        )
                        service = await get_akshare_sync_service()
                    else:
                        logger.warning(f"⚠️ [数据同步] 不支持的数据源: {data_source}")
                        continue

                    # 初始化结果统计
                    historical_records = 0
                    financial_synced = False
                    realtime_synced = False

                    # 2.1 同步历史数据
                    logger.info("📊 [数据同步] 同步历史数据...")
                    hist_result = await service.sync_historical_data(
                        symbols=[stock_code],
                        start_date=start_date,
                        end_date=end_date,
                        incremental=False,  # 全量同步
                    )

                    if hist_result.get("success_count", 0) > 0:
                        historical_records = hist_result.get("total_records", 0)
                        logger.info(f"✅ [数据同步] 历史数据同步成功: {historical_records}条")
                    else:
                        errors = hist_result.get("errors", [])
                        error_msg = errors[0].get("error", "未知错误") if errors else "同步失败"
                        logger.warning(f"⚠️ [数据同步] 历史数据同步失败: {error_msg}")

                    # 2.2 同步财务数据
                    logger.info("📊 [数据同步] 同步财务数据...")
                    try:
                        fin_result = await service.sync_financial_data(
                            symbols=[stock_code],
                        )

                        if fin_result.get("success_count", 0) > 0:
                            financial_synced = True
                            logger.info("✅ [数据同步] 财务数据同步成功")
                        else:
                            logger.warning("⚠️ [数据同步] 财务数据同步失败")
                    except Exception as e:
                        logger.warning(f"⚠️ [数据同步] 财务数据同步异常: {e}")

                    # 2.3 同步实时行情
                    logger.info("📊 [数据同步] 同步实时行情...")
                    try:
                        # 对于单个股票，AKShare更适合获取实时行情
                        if data_source == "tushare":
                            # Tushare的实时行情接口有限制，改用AKShare
                            get_akshare_sync_service = getattr(
                                importlib.import_module("app.worker.akshare.sync"),
                                "get_akshare_sync_service",
                            )
                            realtime_service = await get_akshare_sync_service()
                        else:
                            realtime_service = service

                        rt_result = await realtime_service.sync_realtime_quotes(
                            symbols=[stock_code],
                            force=True,  # 强制执行，跳过交易时间检查
                        )

                        if rt_result.get("success_count", 0) > 0:
                            realtime_synced = True
                            logger.info("✅ [数据同步] 实时行情同步成功")
                        else:
                            logger.warning("⚠️ [数据同步] 实时行情同步失败")
                    except Exception as e:
                        logger.warning(f"⚠️ [数据同步] 实时行情同步异常: {e}")

                    # 检查同步结果（至少历史数据要成功）
                    if historical_records > 0:
                        message = f"使用{data_source}同步成功: 历史{historical_records}条"
                        if financial_synced:
                            message += ", 财务数据✓"
                        if realtime_synced:
                            message += ", 实时行情✓"

                        logger.info(f"✅ [数据同步] {message}")
                        return {
                            "success": True,
                            "message": message,
                            "synced_records": historical_records,
                            "data_source": data_source,
                            "historical_records": historical_records,
                            "financial_synced": financial_synced,
                            "realtime_synced": realtime_synced,
                        }
                    else:
                        last_error = f"{data_source}: 历史数据同步失败"
                        logger.warning(f"⚠️ [数据同步] {data_source}同步失败: 历史数据为空")
                        # 继续尝试下一个数据源

                except Exception as e:
                    last_error = f"{data_source}: {str(e)}"
                    logger.warning(f"⚠️ [数据同步] {data_source}同步异常: {e}")
                    traceback = importlib.import_module("traceback")
                    logger.debug(f"详细错误: {traceback.format_exc()}")
                    # 继续尝试下一个数据源
                    continue

            # 所有数据源都失败
            message = f"所有数据源同步失败，最后错误: {last_error}"
            logger.error(f"❌ [数据同步] {message}")
            return {
                "success": False,
                "message": message,
                "synced_records": 0,
                "data_source": None,
                "historical_records": 0,
                "financial_synced": False,
                "realtime_synced": False,
            }

        except Exception as e:
            logger.error(f"❌ [数据同步] 同步数据失败: {e}")
            traceback = importlib.import_module("traceback")
            logger.debug(f"详细错误: {traceback.format_exc()}")
            return {
                "success": False,
                "message": f"同步失败: {str(e)}",
                "synced_records": 0,
                "data_source": None,
                "historical_records": 0,
                "financial_synced": False,
                "realtime_synced": False,
            }

    def _get_data_source_priority_for_sync(self, stock_code: str) -> list:
        """
        获取数据源优先级（用于同步）

        Returns:
            list: 数据源列表，按优先级排序 ['tushare', 'akshare', 'baostock']
        """
        try:
            get_postgres_cache_adapter = getattr(
                importlib.import_module("trader.flows.cache.postgres"),
                "get_postgres_cache_adapter",
            )

            adapter = get_postgres_cache_adapter()
            if adapter.use_app_cache and adapter.db is not None:
                # 使用 PostgreSQL 适配器的方法获取优先级
                priority_order = adapter._get_data_source_priority(stock_code)
                logger.info(f"✅ [数据源优先级] 从数据库获取: {priority_order}")
                return priority_order
            else:
                logger.warning("⚠️ [数据源优先级] PostgreSQL未启用，使用默认顺序")
                return ["tushare", "akshare", "baostock"]

        except Exception as e:
            logger.error(f"❌ [数据源优先级] 获取失败: {e}")
            # 返回默认顺序
            return ["tushare", "akshare", "baostock"]

    def _prepare_hk_stock_data(
        self, stock_code: str, period_days: int, analysis_date: str
    ) -> StockDataPreparationResult:
        """预获取港股数据"""
        logger.info(f"📊 [港股数据] 开始准备{stock_code}的数据 (时长: {period_days}天)")

        # 标准化港股代码格式
        if not stock_code.upper().endswith(".HK"):
            # 移除前导0，然后补齐到4位
            clean_code = stock_code.lstrip("0") or "0"  # 如果全是0，保留一个0
            formatted_code = f"{clean_code.zfill(4)}.HK"
            logger.debug(f"🔍 [港股数据] 代码格式化: {stock_code} → {formatted_code}")
        else:
            formatted_code = stock_code.upper()

        # 计算日期范围
        end_date = datetime.strptime(analysis_date, "%Y-%m-%d")
        start_date = end_date - timedelta(days=period_days)
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        logger.debug(f"📅 [港股数据] 日期范围: {start_date_str} → {end_date_str}")

        has_historical_data = False
        has_basic_info = False
        stock_name = "未知"
        cache_status = ""

        try:
            # 1. 获取基本信息
            logger.debug(f"📊 [港股数据] 获取{formatted_code}基本信息...")
            get_hk_stock_info_unified = getattr(
                importlib.import_module("trader.flows.interface"),
                "get_hk_stock_info_unified",
            )

            stock_info = get_hk_stock_info_unified(formatted_code)

            if stock_info and "❌" not in stock_info and "未找到" not in stock_info:
                # 解析股票名称 - 支持多种格式
                stock_name = self._extract_hk_stock_name(stock_info, formatted_code)

                if stock_name and stock_name != "未知":
                    has_basic_info = True
                    logger.info(f"✅ [港股数据] 基本信息获取成功: {formatted_code} - {stock_name}")
                    cache_status += "基本信息已缓存; "
                else:
                    logger.warning(f"⚠️ [港股数据] 基本信息无效: {formatted_code}")
                    logger.debug(f"🔍 [港股数据] 信息内容: {stock_info[:200]}...")
                    return StockDataPreparationResult(
                        is_valid=False,
                        stock_code=formatted_code,
                        market_type="港股",
                        error_message=f"港股代码 {formatted_code} 不存在或信息无效",
                        suggestion="请检查港股代码是否正确，格式如：0700.HK",
                    )
            else:
                # 检查是否为网络限制问题
                network_error_indicators = [
                    "Too Many Requests",
                    "Rate limited",
                    "Connection aborted",
                    "Remote end closed connection",
                    "网络连接",
                    "超时",
                    "限制",
                ]

                is_network_issue = any(indicator in str(stock_info) for indicator in network_error_indicators)

                if is_network_issue:
                    logger.warning(f"🌐 [港股数据] 网络限制影响: {formatted_code}")
                    return StockDataPreparationResult(
                        is_valid=False,
                        stock_code=formatted_code,
                        market_type="港股",
                        error_message="港股数据获取受到网络限制影响",
                        suggestion=self._get_hk_network_limitation_suggestion(),
                    )
                else:
                    logger.warning(f"⚠️ [港股数据] 无法获取基本信息: {formatted_code}")
                    return StockDataPreparationResult(
                        is_valid=False,
                        stock_code=formatted_code,
                        market_type="港股",
                        error_message=f"港股代码 {formatted_code} 可能不存在或数据源暂时不可用",
                        suggestion="请检查港股代码是否正确，格式如：0700.HK，或稍后重试",
                    )

            # 2. 获取历史数据
            logger.debug(f"📊 [港股数据] 获取{formatted_code}历史数据 ({start_date_str} 到 {end_date_str})...")
            get_hk_stock_data_unified = getattr(
                importlib.import_module("trader.flows.interface"),
                "get_hk_stock_data_unified",
            )

            historical_data = get_hk_stock_data_unified(formatted_code, start_date_str, end_date_str)

            if historical_data and "❌" not in historical_data and "获取失败" not in historical_data:
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
                    and any(indicator in historical_data for indicator in data_indicators)
                )

                if has_valid_data:
                    has_historical_data = True
                    logger.info(f"✅ [港股数据] 历史数据获取成功: {formatted_code} ({period_days}天)")
                    cache_status += f"历史数据已缓存({period_days}天); "
                else:
                    logger.warning(f"⚠️ [港股数据] 历史数据无效: {formatted_code}")
                    logger.debug(f"🔍 [港股数据] 数据内容预览: {historical_data[:200]}...")
                    return StockDataPreparationResult(
                        is_valid=False,
                        stock_code=formatted_code,
                        market_type="港股",
                        stock_name=stock_name,
                        has_basic_info=has_basic_info,
                        error_message=f"港股 {formatted_code} 的历史数据无效或不足",
                        suggestion="该股票可能为新上市股票或数据源暂时不可用，请稍后重试",
                    )
            else:
                # 检查是否为网络限制问题
                network_error_indicators = [
                    "Too Many Requests",
                    "Rate limited",
                    "Connection aborted",
                    "Remote end closed connection",
                    "网络连接",
                    "超时",
                    "限制",
                ]

                is_network_issue = any(indicator in str(historical_data) for indicator in network_error_indicators)

                if is_network_issue:
                    logger.warning(f"🌐 [港股数据] 历史数据获取受网络限制: {formatted_code}")
                    return StockDataPreparationResult(
                        is_valid=False,
                        stock_code=formatted_code,
                        market_type="港股",
                        stock_name=stock_name,
                        has_basic_info=has_basic_info,
                        error_message="港股历史数据获取受到网络限制影响",
                        suggestion=self._get_hk_network_limitation_suggestion(),
                    )
                else:
                    logger.warning(f"⚠️ [港股数据] 无法获取历史数据: {formatted_code}")
                    return StockDataPreparationResult(
                        is_valid=False,
                        stock_code=formatted_code,
                        market_type="港股",
                        stock_name=stock_name,
                        has_basic_info=has_basic_info,
                        error_message=f"无法获取港股 {formatted_code} 的历史数据",
                        suggestion="数据源可能暂时不可用，请稍后重试或联系技术支持",
                    )

            # 3. 数据准备成功
            logger.info(f"🎉 [港股数据] 数据准备完成: {formatted_code} - {stock_name}")
            return StockDataPreparationResult(
                is_valid=True,
                stock_code=formatted_code,
                market_type="港股",
                stock_name=stock_name,
                has_historical_data=has_historical_data,
                has_basic_info=has_basic_info,
                data_period_days=period_days,
                cache_status=cache_status.rstrip("; "),
            )

        except Exception as e:
            logger.error(f"❌ [港股数据] 数据准备失败: {e}")
            return StockDataPreparationResult(
                is_valid=False,
                stock_code=formatted_code,
                market_type="港股",
                stock_name=stock_name,
                has_basic_info=has_basic_info,
                has_historical_data=has_historical_data,
                error_message=f"数据准备失败: {str(e)}",
                suggestion="请检查网络连接或数据源配置",
            )

    def _prepare_us_stock_data(
        self, stock_code: str, period_days: int, analysis_date: str
    ) -> StockDataPreparationResult:
        """预获取美股数据"""
        logger.info(f"📊 [美股数据] 开始准备{stock_code}的数据 (时长: {period_days}天)")

        # 标准化美股代码格式
        formatted_code = stock_code.upper()

        # 计算日期范围
        end_date = datetime.strptime(analysis_date, "%Y-%m-%d")
        start_date = end_date - timedelta(days=period_days)
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        logger.debug(f"📅 [美股数据] 日期范围: {start_date_str} → {end_date_str}")

        has_historical_data = False
        has_basic_info = False
        stock_name = formatted_code  # 美股通常使用代码作为名称
        cache_status = ""

        try:
            # 1. 获取历史数据（美股通常直接通过历史数据验证股票是否存在）
            logger.debug(f"📊 [美股数据] 获取{formatted_code}历史数据 ({start_date_str} 到 {end_date_str})...")

            # 导入美股数据提供器（支持新旧路径）
            try:
                OptimizedUSDataProvider = getattr(
                    importlib.import_module("trader.flows.providers.us"),
                    "OptimizedUSDataProvider",
                )
                provider = OptimizedUSDataProvider()
                historical_data = provider.get_stock_data(formatted_code, start_date_str, end_date_str)
            except ImportError:
                get_us_stock_data_cached = getattr(
                    importlib.import_module("trader.flows.providers.us.optimized"),
                    "get_us_stock_data_cached",
                )
                historical_data = get_us_stock_data_cached(formatted_code, start_date_str, end_date_str)

            if (
                historical_data
                and "❌" not in historical_data
                and "错误" not in historical_data
                and "无法获取" not in historical_data
            ):
                # 更宽松的数据有效性检查
                data_indicators = [
                    "开盘价",
                    "收盘价",
                    "最高价",
                    "最低价",
                    "成交量",
                    "Open",
                    "Close",
                    "High",
                    "Low",
                    "Volume",
                    "日期",
                    "Date",
                    "时间",
                    "Time",
                ]

                has_valid_data = (
                    len(historical_data) > 50  # 降低长度要求
                    and any(indicator in historical_data for indicator in data_indicators)
                )

                if has_valid_data:
                    has_historical_data = True
                    has_basic_info = True  # 美股通常不单独获取基本信息
                    logger.info(f"✅ [美股数据] 历史数据获取成功: {formatted_code} ({period_days}天)")
                    cache_status = f"历史数据已缓存({period_days}天)"

                    # 数据准备成功
                    logger.info(f"🎉 [美股数据] 数据准备完成: {formatted_code}")
                    return StockDataPreparationResult(
                        is_valid=True,
                        stock_code=formatted_code,
                        market_type="美股",
                        stock_name=stock_name,
                        has_historical_data=has_historical_data,
                        has_basic_info=has_basic_info,
                        data_period_days=period_days,
                        cache_status=cache_status,
                    )
                else:
                    logger.warning(f"⚠️ [美股数据] 历史数据无效: {formatted_code}")
                    logger.debug(f"🔍 [美股数据] 数据内容预览: {historical_data[:200]}...")
                    return StockDataPreparationResult(
                        is_valid=False,
                        stock_code=formatted_code,
                        market_type="美股",
                        error_message=f"美股 {formatted_code} 的历史数据无效或不足",
                        suggestion="该股票可能为新上市股票或数据源暂时不可用，请稍后重试",
                    )
            else:
                logger.warning(f"⚠️ [美股数据] 无法获取历史数据: {formatted_code}")
                return StockDataPreparationResult(
                    is_valid=False,
                    stock_code=formatted_code,
                    market_type="美股",
                    error_message=f"美股代码 {formatted_code} 不存在或无法获取数据",
                    suggestion="请检查美股代码是否正确，如：AAPL、TSLA、MSFT",
                )

        except Exception as e:
            logger.error(f"❌ [美股数据] 数据准备失败: {e}")
            return StockDataPreparationResult(
                is_valid=False,
                stock_code=formatted_code,
                market_type="美股",
                error_message=f"数据准备失败: {str(e)}",
                suggestion="请检查网络连接或数据源配置",
            )
