from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .imports import (
        Any,
        Dict,
        List,
        Optional,
        TushareProvider,
        asyncio,
        cast,
        datetime,
        get_historical_data_service,
        get_news_data_service,
        get_postgres_db,
        get_stock_data_service,
        get_tushare_rate_limiter,
        importlib,
        inspect,
        logger,
        settings,
        timezone,
    )

class _TushareSyncServiceMixin1:
    def __init__(self):
        self.provider = TushareProvider()
        self.stock_service = get_stock_data_service()
        self.historical_service: Any = None  # 延迟初始化
        self.news_service: Any = None  # 延迟初始化
        self.db: Any = get_postgres_db()
        self.settings = settings
        self.provider_available = False

        # 同步配置
        self.batch_size = 100  # 批量处理大小
        self.rate_limit_delay = 0.1  # API调用间隔(秒) - 已弃用，使用rate_limiter
        self.max_retries = 3  # 最大重试次数

        # 速率限制器（从环境变量读取配置）
        tushare_tier = getattr(settings, "TUSHARE_TIER", "standard")  # free/basic/standard/premium/vip
        safety_margin = float(getattr(settings, "TUSHARE_RATE_LIMIT_SAFETY_MARGIN", "0.8"))
        self.rate_limiter = get_tushare_rate_limiter(tier=tushare_tier, safety_margin=safety_margin)

    @staticmethod
    def _as_dict(value: Any) -> Dict[str, Any]:
        if hasattr(value, "model_dump"):
            return cast(Dict[str, Any], value.model_dump())
        if hasattr(value, "dict"):
            return cast(Dict[str, Any], value.dict())
        return cast(Dict[str, Any], value)

    async def initialize(self):
        """初始化同步服务"""
        success = await self.provider.connect()
        self.provider_available = bool(success)
        if not self.provider_available:
            logger.warning("⚠️ Tushare连接失败，Tushare实时批量同步将跳过；少量股票仍可使用 AKShare 免费源路径")

        # 初始化历史数据服务
        try:
            self.historical_service = await get_historical_data_service()
        except Exception as e:
            logger.warning(f"⚠️ 历史数据服务初始化失败，后续按需重试: {e}")
            self.historical_service = None

        # 初始化新闻数据服务
        try:
            self.news_service = await get_news_data_service()
        except Exception as e:
            logger.warning(f"⚠️ 新闻数据服务初始化失败，后续按需重试: {e}")
            self.news_service = None

        logger.info("✅ Tushare同步服务初始化完成")

    async def sync_stock_basic_info(self, force_update: bool = False, job_id: Optional[str] = None) -> Dict[str, Any]:
        """
        同步股票基础信息

        Args:
            force_update: 是否强制更新所有数据
            job_id: 任务ID（用于进度跟踪）

        Returns:
            同步结果统计
        """
        logger.info("🔄 开始同步股票基础信息...")

        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            "start_time": datetime.now(timezone.utc).replace(tzinfo=None),
            "errors": [],
        }

        try:
            # 1. 从Tushare获取股票列表
            stock_list = await self.provider.get_stock_list(market="CN")
            if not stock_list:
                logger.error("❌ 无法获取股票列表")
                return stats

            stats["total_processed"] = len(stock_list)
            logger.info(f"📊 获取到 {len(stock_list)} 只股票信息")

            # 2. 批量处理
            for i in range(0, len(stock_list), self.batch_size):
                # 检查是否需要退出
                if job_id and await self._should_stop(job_id):
                    logger.warning(f"⚠️ 任务 {job_id} 收到停止信号，正在退出...")
                    stats["stopped"] = True
                    break

                batch = stock_list[i : i + self.batch_size]
                batch_stats = await self._process_basic_info_batch(batch, force_update)

                # 更新统计
                stats["success_count"] += batch_stats["success_count"]
                stats["error_count"] += batch_stats["error_count"]
                stats["skipped_count"] += batch_stats["skipped_count"]
                stats["errors"].extend(batch_stats["errors"])

                # 进度日志和进度更新
                progress = min(i + self.batch_size, len(stock_list))
                progress_percent = int((progress / len(stock_list)) * 100)
                logger.info(
                    f"📈 基础信息同步进度: {progress}/{len(stock_list)} ({progress_percent}%) "
                    f"(成功: {stats['success_count']}, 错误: {stats['error_count']})"
                )

                # 更新任务进度
                if job_id:
                    await self._update_progress(
                        job_id,
                        progress_percent,
                        f"已处理 {progress}/{len(stock_list)} 只股票",
                    )

                # API限流
                if i + self.batch_size < len(stock_list):
                    await asyncio.sleep(self.rate_limit_delay)

            # 3. 完成统计
            stats["end_time"] = datetime.now(timezone.utc).replace(tzinfo=None)
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

            logger.info(
                f"✅ 股票基础信息同步完成: "
                f"总计 {stats['total_processed']} 只, "
                f"成功 {stats['success_count']} 只, "
                f"错误 {stats['error_count']} 只, "
                f"跳过 {stats['skipped_count']} 只, "
                f"耗时 {stats['duration']:.2f} 秒"
            )

            return stats

        except Exception as e:
            logger.error(f"❌ 股票基础信息同步失败: {e}")
            stats["errors"].append({"error": str(e), "context": "sync_stock_basic_info"})
            return stats

    async def _process_basic_info_batch(self, batch: List[Dict[str, Any]], force_update: bool) -> Dict[str, Any]:
        """处理基础信息批次"""
        batch_stats = {
            "success_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            "errors": [],
        }

        for stock_info in batch:
            try:
                # 🔥 先转换为字典格式（如果是Pydantic模型）
                stock_data = self._as_dict(stock_info)

                code = stock_data["code"]

                # 检查是否需要更新
                if not force_update:
                    existing = await self.stock_service.get_stock_basic_info(code)
                    if existing:
                        # 🔥 existing 也可能是 Pydantic 模型，需要安全获取属性
                        existing_dict = self._as_dict(existing)
                        if self._is_data_fresh(existing_dict.get("updated_at"), hours=24):
                            batch_stats["skipped_count"] += 1
                            continue

                # 更新到数据库（指定数据源为 tushare）
                success = await self.stock_service.update_stock_basic_info(code, stock_data, source="tushare")
                if success:
                    batch_stats["success_count"] += 1
                else:
                    batch_stats["error_count"] += 1
                    batch_stats["errors"].append({
                        "code": code,
                        "error": "数据库更新失败",
                        "context": "update_stock_basic_info",
                    })

            except Exception as e:
                batch_stats["error_count"] += 1
                # 🔥 安全获取 code（处理 Pydantic 模型和字典）
                try:
                    stock_item: Any = stock_info
                    if hasattr(stock_item, "code"):
                        code = stock_item.code
                    else:
                        code = self._as_dict(stock_item).get("code", "unknown")
                except Exception:
                    code = "unknown"

                batch_stats["errors"].append({
                    "code": code,
                    "error": str(e),
                    "context": "_process_basic_info_batch",
                })

        return batch_stats

    async def sync_realtime_quotes(self, symbols: Optional[List[str]] = None, force: bool = False) -> Dict[str, Any]:
        """
        同步实时行情数据

        策略：
        - 如果指定了少量股票（≤10只），自动切换到 AKShare 接口（避免浪费 Tushare rt_k 配额）
        - 如果指定了大量股票或全市场，使用 Tushare 批量接口一次性获取

        Args:
            symbols: 指定股票代码列表，为空则同步所有股票；如果指定了股票列表，则只保存这些股票的数据
            force: 是否强制执行（跳过交易时间检查），默认 False

        Returns:
            同步结果统计
        """
        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "start_time": datetime.now(timezone.utc).replace(tzinfo=None),
            "errors": [],
            "stopped_by_rate_limit": False,
            "skipped_non_trading_time": False,
            "switched_to_akshare": False,  # 是否切换到 AKShare
            "skipped_tushare_unavailable": False,
        }

        try:
            # 检查是否在交易时间（手动同步时可以跳过检查）
            if not force and not self._is_trading_time() and not self.settings.DEBUG:
                logger.info("⏸️ 当前不在交易时间，跳过实时行情同步（使用 force=True 可强制执行）")
                stats["skipped_non_trading_time"] = True
                return stats
            elif not force and not self._is_trading_time():
                logger.info("⏸️ 当前不在交易时间；DEBUG 模式继续执行实时行情同步")

            # 🔥 策略选择：少量股票切换到 AKShare，大量股票或全市场用 Tushare 批量接口
            USE_AKSHARE_THRESHOLD = 10  # 少于等于10只股票时切换到 AKShare

            if symbols and len(symbols) <= USE_AKSHARE_THRESHOLD:
                # 🔥 自动切换到 AKShare（避免浪费 Tushare rt_k 配额，每小时只能调用2次）
                logger.info(
                    f"💡 股票数量 ≤{USE_AKSHARE_THRESHOLD} 只，自动切换到 AKShare 接口"
                    f"（避免浪费 Tushare rt_k 配额，每小时只能调用2次）"
                )
                logger.info(f"🎯 使用 AKShare 同步 {len(symbols)} 只股票的实时行情: {symbols}")

                # 调用 AKShare 服务
                get_akshare_sync_service = getattr(
                    importlib.import_module("app.worker.akshare.sync"),
                    "get_akshare_sync_service",
                )
                akshare_service = await get_akshare_sync_service()

                if not akshare_service:
                    logger.error("❌ AKShare 服务不可用，回退到 Tushare 批量接口")
                    # 回退到 Tushare 批量接口
                    quotes_map = await self.provider.get_realtime_quotes_batch()
                    if quotes_map and symbols:
                        quotes_map = {symbol: quotes_map[symbol] for symbol in symbols if symbol in quotes_map}
                else:
                    # 使用 AKShare 同步
                    akshare_result = await akshare_service.sync_realtime_quotes(symbols=symbols, force=force)
                    stats["switched_to_akshare"] = True
                    stats["success_count"] = akshare_result.get("success_count", 0)
                    stats["error_count"] = akshare_result.get("error_count", 0)
                    stats["total_processed"] = akshare_result.get("total_processed", 0)
                    stats["errors"] = akshare_result.get("errors", [])
                    stats["end_time"] = datetime.now(timezone.utc).replace(tzinfo=None)
                    stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

                    logger.info(
                        f"✅ AKShare 实时行情同步完成: "
                        f"总计 {stats['total_processed']} 只, "
                        f"成功 {stats['success_count']} 只, "
                        f"错误 {stats['error_count']} 只, "
                        f"耗时 {stats['duration']:.2f} 秒"
                    )
                    return stats
            else:
                if not self.provider_available:
                    logger.warning("⚠️ Tushare不可用，跳过需要 rt_k 的实时行情同步")
                    stats["skipped_tushare_unavailable"] = True
                    stats["end_time"] = datetime.now(timezone.utc).replace(tzinfo=None)
                    stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
                    return stats

                # 使用 Tushare 批量接口一次性获取全市场行情
                if symbols:
                    logger.info(f"📊 使用 Tushare 批量接口同步 {len(symbols)} 只股票的实时行情（从全市场数据中筛选）")
                else:
                    logger.info("📊 使用 Tushare 批量接口同步全市场实时行情...")

                logger.info("📡 调用 rt_k 批量接口获取全市场实时行情...")
                batch_fetch = getattr(self.provider, "get_realtime_quotes_batch", None)
                if not callable(batch_fetch):
                    return await self._sync_realtime_quotes_by_batches(symbols, stats)

                batch_result = batch_fetch()
                if inspect.isawaitable(batch_result):
                    quotes_map = await batch_result
                elif isinstance(batch_result, dict):
                    quotes_map = batch_result
                else:
                    return await self._sync_realtime_quotes_by_batches(symbols, stats)

                if not quotes_map:
                    logger.warning("⚠️ 未获取到实时行情数据")
                    return stats

                logger.info(f"✅ 获取到 {len(quotes_map)} 只股票的实时行情")

                # 🔥 如果指定了股票列表，只处理这些股票
                if symbols:
                    # 过滤出指定的股票
                    filtered_quotes_map = {symbol: quotes_map[symbol] for symbol in symbols if symbol in quotes_map}

                    # 检查是否有股票未找到
                    missing_symbols = [s for s in symbols if s not in quotes_map]
                    if missing_symbols:
                        logger.warning(f"⚠️ 以下股票未在实时行情中找到: {missing_symbols}")

                    quotes_map = filtered_quotes_map
                    logger.info(f"🔍 过滤后保留 {len(quotes_map)} 只指定股票的行情")

            if not quotes_map:
                logger.warning("⚠️ 未获取到任何实时行情数据")
                return stats

            stats["total_processed"] = len(quotes_map)

            # 批量保存到数据库
            success_count = 0
            error_count = 0

            for symbol, quote_data in quotes_map.items():
                try:
                    # 保存到数据库
                    result = await self.stock_service.update_market_quotes(symbol, quote_data)
                    if result:
                        success_count += 1
                    else:
                        error_count += 1
                        stats["errors"].append({
                            "code": symbol,
                            "error": "更新数据库失败",
                            "context": "sync_realtime_quotes",
                        })
                except Exception as e:
                    error_count += 1
                    stats["errors"].append({
                        "code": symbol,
                        "error": str(e),
                        "context": "sync_realtime_quotes",
                    })

            stats["success_count"] = success_count
            stats["error_count"] = error_count

            # 完成统计
            stats["end_time"] = datetime.now(timezone.utc).replace(tzinfo=None)
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

            logger.info(
                f"✅ 实时行情同步完成: "
                f"总计 {stats['total_processed']} 只, "
                f"成功 {stats['success_count']} 只, "
                f"错误 {stats['error_count']} 只, "
                f"耗时 {stats['duration']:.2f} 秒"
            )

            return stats

        except Exception as e:
            # 检查是否为限流错误
            error_msg = str(e)
            if self._is_rate_limit_error(error_msg):
                stats["stopped_by_rate_limit"] = True
                logger.error(f"❌ 实时行情同步失败（API限流）: {e}")
            else:
                logger.error(f"❌ 实时行情同步失败: {e}")

            stats["errors"].append({"error": str(e), "context": "sync_realtime_quotes"})
            return stats

    async def _load_stock_symbols_for_quotes(self) -> List[str]:
        cursor = self.db.stock_basic_info.find({}, {"code": 1})
        return [doc["code"] async for doc in cursor]

    async def _sync_realtime_quotes_by_batches(
        self, symbols: Optional[List[str]], stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """旧版兼容路径：从 stock_basic_info 取代码后逐批调用 _process_quotes_batch。"""
        if symbols is None:
            symbols = await self._load_stock_symbols_for_quotes()
            logger.info(f"📋 从 stock_basic_info 获取到 {len(symbols)} 只股票")

        stats["total_processed"] = len(symbols)

        for i in range(0, len(symbols), self.batch_size):
            batch = symbols[i : i + self.batch_size]
            batch_stats = await self._process_quotes_batch(batch)
            stats["success_count"] += batch_stats["success_count"]
            stats["error_count"] += batch_stats["error_count"]
            stats["errors"].extend(batch_stats["errors"])
            if batch_stats.get("rate_limit_hit"):
                stats["stopped_by_rate_limit"] = True
                break

        stats["end_time"] = datetime.now(timezone.utc).replace(tzinfo=None)
        stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
        return stats

    async def _process_quotes_batch(self, batch: List[str]) -> Dict[str, Any]:
        """处理行情批次"""
        batch_stats = {
            "success_count": 0,
            "error_count": 0,
            "errors": [],
            "rate_limit_hit": False,
        }

        # 并发获取行情数据
        tasks = []
        for symbol in batch:
            task = self._get_and_save_quotes(symbol)
            tasks.append(task)

        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计结果
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_msg = str(result)
                batch_stats["error_count"] += 1
                batch_stats["errors"].append({
                    "code": batch[i],
                    "error": error_msg,
                    "context": "_process_quotes_batch",
                })

                # 检测 API 限流错误
                if self._is_rate_limit_error(error_msg):
                    batch_stats["rate_limit_hit"] = True
                    logger.warning(f"⚠️ 检测到 API 限流错误: {error_msg}")

            elif result:
                batch_stats["success_count"] += 1
            else:
                batch_stats["error_count"] += 1
                batch_stats["errors"].append({
                    "code": batch[i],
                    "error": "获取行情数据失败",
                    "context": "_process_quotes_batch",
                })

        return batch_stats

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

    def _is_trading_time(self) -> bool:
        """
        判断当前是否在交易时间
        A股交易时间：
        - 周一到周五（排除节假日）
        - 上午：9:30-11:30
        - 下午：13:00-15:00

        注意：此方法不检查节假日，仅检查时间段
        """
        datetime = getattr(importlib.import_module("datetime"), "datetime")
        pytz = importlib.import_module("pytz")

        # 使用上海时区
        tz = pytz.timezone("Asia/Shanghai")
        now = datetime.now(tz)

        # 检查是否是周末
        if now.weekday() >= 5:  # 5=周六, 6=周日
            return False

        # 检查时间段
        current_time = now.time()

        # 上午交易时间：9:30-11:30
        morning_start = datetime.strptime("09:30", "%H:%M").time()
        morning_end = datetime.strptime("11:30", "%H:%M").time()

        # 下午交易时间：13:00-15:00
        afternoon_start = datetime.strptime("13:00", "%H:%M").time()
        afternoon_end = datetime.strptime("15:00", "%H:%M").time()

        # 判断是否在交易时间段内
        is_morning = morning_start <= current_time <= morning_end
        is_afternoon = afternoon_start <= current_time <= afternoon_end

        return is_morning or is_afternoon

    async def _get_and_save_quotes(self, symbol: str) -> bool:
        """获取并保存单个股票行情"""
        try:
            quotes = await self.provider.get_stock_quotes(symbol)
            if quotes:
                # 转换为字典格式（如果是Pydantic模型）
                quotes_data = self._as_dict(quotes)

                return await self.stock_service.update_market_quotes(symbol, quotes_data)
            return False
        except Exception as e:
            error_msg = str(e)
            # 检测限流错误，直接抛出让上层处理
            if self._is_rate_limit_error(error_msg):
                logger.error(f"❌ 获取 {symbol} 行情失败（限流）: {e}")
                raise  # 抛出限流错误
            logger.error(f"❌ 获取 {symbol} 行情失败: {e}")
            return False
