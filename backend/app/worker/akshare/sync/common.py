# ruff: noqa: F401,F403,F405,F821
class _AKShareSyncServiceMixin1:
    def __init__(self):
        self.provider: Any = None
        self.historical_service: Any = None  # 延迟初始化
        self.news_service: Any = None  # 延迟初始化
        self.db: Any = None
        self.batch_size = 100
        self.rate_limit_delay = 0.2  # AKShare建议的延迟

    @staticmethod
    def _as_dict(value: Any) -> Dict[str, Any]:
        if hasattr(value, "model_dump"):
            return cast(Dict[str, Any], value.model_dump())
        if hasattr(value, "dict"):
            return cast(Dict[str, Any], value.dict())
        return cast(Dict[str, Any], value)

    async def initialize(self):
        """初始化同步服务"""
        try:
            # 初始化数据库连接
            self.db = get_postgres_db()

            # 初始化历史数据服务
            self.historical_service = await get_historical_data_service()

            # 初始化新闻数据服务
            self.news_service = await get_news_data_service()

            # 初始化AKShare提供器（使用全局单例，确保monkey patch生效）
            self.provider = get_akshare_provider()

            # 测试连接
            if not await self.provider.test_connection():
                raise RuntimeError("❌ AKShare连接失败，无法启动同步服务")

            logger.info("✅ AKShare同步服务初始化完成")

        except Exception as e:
            logger.error(f"❌ AKShare同步服务初始化失败: {e}")
            raise

    async def sync_stock_basic_info(self, force_update: bool = False) -> Dict[str, Any]:
        """
        同步股票基础信息

        Args:
            force_update: 是否强制更新

        Returns:
            同步结果统计
        """
        logger.info("🔄 开始同步股票基础信息...")

        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            "start_time": utcnow_naive(),
            "end_time": None,
            "duration": 0,
            "errors": [],
        }

        try:
            # 1. 获取股票列表
            stock_list = await self.provider.get_stock_list()
            if not stock_list:
                logger.warning("⚠️ 未获取到股票列表")
                return stats

            stats["total_processed"] = len(stock_list)
            logger.info(f"📊 获取到 {len(stock_list)} 只股票信息")

            # 2. 批量处理
            for i in range(0, len(stock_list), self.batch_size):
                batch = stock_list[i : i + self.batch_size]
                batch_stats = await self._process_basic_info_batch(batch, force_update)

                # 更新统计
                stats["success_count"] += batch_stats["success_count"]
                stats["error_count"] += batch_stats["error_count"]
                stats["skipped_count"] += batch_stats["skipped_count"]
                stats["errors"].extend(batch_stats["errors"])

                # 进度日志
                progress = min(i + self.batch_size, len(stock_list))
                logger.info(
                    f"📈 基础信息同步进度: {progress}/{len(stock_list)} "
                    f"(成功: {stats['success_count']}, 错误: {stats['error_count']})"
                )

                # API限流
                if i + self.batch_size < len(stock_list):
                    await asyncio.sleep(self.rate_limit_delay)

            # 3. 完成统计
            stats["end_time"] = utcnow_naive()
            stats["duration"] = (
                stats["end_time"] - stats["start_time"]
            ).total_seconds()

            logger.info("🎉 股票基础信息同步完成！")
            logger.info(
                f"📊 总计: {stats['total_processed']}只, "
                f"成功: {stats['success_count']}, "
                f"错误: {stats['error_count']}, "
                f"跳过: {stats['skipped_count']}, "
                f"耗时: {stats['duration']:.2f}秒"
            )

            return stats

        except Exception as e:
            logger.error(f"❌ 股票基础信息同步失败: {e}")
            stats["errors"].append(
                {"error": str(e), "context": "sync_stock_basic_info"}
            )
            return stats

    async def _process_basic_info_batch(
        self, batch: List[Dict[str, Any]], force_update: bool
    ) -> Dict[str, Any]:
        """处理基础信息批次"""
        batch_stats = {
            "success_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            "errors": [],
        }

        for stock_info in batch:
            try:
                code = stock_info["code"]

                # 检查是否需要更新
                if not force_update:
                    existing = await self.db.stock_basic_info.find_one({"code": code})
                    if existing and self._is_data_fresh(
                        existing.get("updated_at"), hours=24
                    ):
                        batch_stats["skipped_count"] += 1
                        continue

                # 获取详细基础信息
                basic_info = await self.provider.get_stock_basic_info(code)

                if basic_info:
                    # 转换为字典格式
                    basic_data = self._as_dict(basic_info)

                    # 🔥 确保 source 字段存在
                    if "source" not in basic_data:
                        basic_data["source"] = "akshare"

                    if "code" not in basic_data:
                        basic_data["code"] = code

                    # 🔥 确保 symbol 字段存在
                    if "symbol" not in basic_data:
                        basic_data["symbol"] = code

                    # 更新到数据库（使用 code + source 联合查询）
                    try:
                        await self.db.stock_basic_info.update_one(
                            {"code": code, "source": "akshare"},
                            {"$set": basic_data},
                            upsert=True,
                        )
                        await dual_write_hot_document("stock_basic_info", basic_data)
                        batch_stats["success_count"] += 1
                    except Exception as e:
                        batch_stats["error_count"] += 1
                        batch_stats["errors"].append(
                            {
                                "code": code,
                                "error": f"数据库更新失败: {str(e)}",
                                "context": "update_stock_basic_info",
                            }
                        )
                else:
                    batch_stats["error_count"] += 1
                    batch_stats["errors"].append(
                        {
                            "code": code,
                            "error": "获取基础信息失败",
                            "context": "get_stock_basic_info",
                        }
                    )

            except Exception as e:
                batch_stats["error_count"] += 1
                batch_stats["errors"].append(
                    {
                        "code": stock_info.get("code", "unknown"),
                        "error": str(e),
                        "context": "_process_basic_info_batch",
                    }
                )

        return batch_stats

    def _is_data_fresh(self, updated_at: Any, hours: int = 24) -> bool:
        """检查数据是否新鲜"""
        if not updated_at:
            return False

        try:
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            elif isinstance(updated_at, datetime):
                pass
            else:
                return False

            # 转换为UTC时间进行比较
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=None)
            else:
                updated_at = updated_at.replace(tzinfo=None)

            now = utcnow_naive()
            time_diff = now - updated_at

            return time_diff.total_seconds() < (hours * 3600)

        except Exception as e:
            logger.debug(f"检查数据新鲜度失败: {e}")
            return False

    async def sync_realtime_quotes(
        self, symbols: Optional[List[str]] = None, force: bool = False
    ) -> Dict[str, Any]:
        """
        同步实时行情数据

        Args:
            symbols: 指定股票代码列表，为空则同步所有股票
            force: 是否强制执行（跳过交易时间检查），默认 False

        Returns:
            同步结果统计
        """
        # 🔥 如果指定了股票列表，记录日志
        if symbols:
            logger.info(
                f"🔄 开始同步指定股票的实时行情（共 {len(symbols)} 只）: {symbols}"
            )
        else:
            logger.info("🔄 开始同步全市场实时行情...")

        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "start_time": utcnow_naive(),
            "end_time": None,
            "duration": 0,
            "errors": [],
        }

        try:
            # 1. 确定要同步的股票列表
            if symbols is None:
                # 从数据库获取所有上市状态的股票代码（排除退市股票）
                basic_info_cursor = self.db.stock_basic_info.find(
                    {"list_status": "L"},  # 只获取上市状态的股票
                    {"code": 1},
                )
                symbols = [doc["code"] async for doc in basic_info_cursor]

            if not symbols:
                logger.warning("⚠️ 没有找到要同步的股票")
                return stats

            stats["total_processed"] = len(symbols)
            logger.info(f"📊 准备同步 {len(symbols)} 只股票的行情")

            # 🔥 优化：如果只同步1只股票，直接调用单个股票接口，不走批量接口
            if len(symbols) == 1:
                logger.info("📈 单个股票同步，直接使用 get_stock_quotes 接口")
                symbol = symbols[0]
                success = await self._get_and_save_quotes(symbol)
                if success:
                    stats["success_count"] = 1
                else:
                    stats["error_count"] = 1
                    stats["errors"].append(
                        {
                            "code": symbol,
                            "error": "获取行情失败",
                            "context": "sync_realtime_quotes_single",
                        }
                    )

                logger.info(
                    f"📈 行情同步进度: 1/1 (成功: {stats['success_count']}, 错误: {stats['error_count']})"
                )
            else:
                # 2. 批量同步：一次性获取全市场快照（避免多次调用接口被限流）
                logger.info("📡 获取全市场实时行情快照...")
                quotes_map = await self.provider.get_batch_stock_quotes(symbols)

                if not quotes_map:
                    logger.warning("⚠️ 获取全市场快照失败，回退到逐个获取模式")
                    # 回退到逐个获取模式
                    for i in range(0, len(symbols), self.batch_size):
                        batch = symbols[i : i + self.batch_size]
                        batch_stats = await self._process_quotes_batch_fallback(batch)

                        # 更新统计
                        stats["success_count"] += batch_stats["success_count"]
                        stats["error_count"] += batch_stats["error_count"]
                        stats["errors"].extend(batch_stats["errors"])

                        # 进度日志
                        progress = min(i + self.batch_size, len(symbols))
                        logger.info(
                            f"📈 行情同步进度: {progress}/{len(symbols)} "
                            f"(成功: {stats['success_count']}, 错误: {stats['error_count']})"
                        )

                        # API限流
                        if i + self.batch_size < len(symbols):
                            await asyncio.sleep(self.rate_limit_delay)
                else:
                    # 3. 使用获取到的全市场数据，分批保存到数据库
                    logger.info(
                        f"✅ 获取到 {len(quotes_map)} 只股票的行情数据，开始保存..."
                    )

                    for i in range(0, len(symbols), self.batch_size):
                        batch = symbols[i : i + self.batch_size]

                        # 从全市场数据中提取当前批次的数据并保存
                        for symbol in batch:
                            try:
                                quotes = quotes_map.get(symbol)
                                if quotes:
                                    # 转换为字典格式
                                    quotes_data = self._as_dict(quotes)

                                    # 确保 symbol 和 code 字段存在
                                    if "symbol" not in quotes_data:
                                        quotes_data["symbol"] = symbol
                                    if "code" not in quotes_data:
                                        quotes_data["code"] = symbol
                                    if "source" not in quotes_data:
                                        quotes_data["source"] = "akshare"

                                    # 更新到数据库
                                    await self.db.market_quotes.update_one(
                                        {"code": symbol},
                                        {"$set": quotes_data},
                                        upsert=True,
                                    )
                                    await dual_write_hot_document(
                                        "market_quotes", quotes_data
                                    )
                                    stats["success_count"] += 1
                                else:
                                    stats["error_count"] += 1
                                    stats["errors"].append(
                                        {
                                            "code": symbol,
                                            "error": "未找到行情数据",
                                            "context": "sync_realtime_quotes",
                                        }
                                    )
                            except Exception as e:
                                stats["error_count"] += 1
                                stats["errors"].append(
                                    {
                                        "code": symbol,
                                        "error": str(e),
                                        "context": "sync_realtime_quotes",
                                    }
                                )

                        # 进度日志
                        progress = min(i + self.batch_size, len(symbols))
                        logger.info(
                            f"📈 行情保存进度: {progress}/{len(symbols)} "
                            f"(成功: {stats['success_count']}, 错误: {stats['error_count']})"
                        )

            # 4. 完成统计
            stats["end_time"] = utcnow_naive()
            stats["duration"] = (
                stats["end_time"] - stats["start_time"]
            ).total_seconds()

            logger.info("🎉 实时行情同步完成！")
            logger.info(
                f"📊 总计: {stats['total_processed']}只, "
                f"成功: {stats['success_count']}, "
                f"错误: {stats['error_count']}, "
                f"耗时: {stats['duration']:.2f}秒"
            )

            return stats

        except Exception as e:
            logger.error(f"❌ 实时行情同步失败: {e}")
            stats["errors"].append({"error": str(e), "context": "sync_realtime_quotes"})
            return stats

    async def _process_quotes_batch(self, batch: List[str]) -> Dict[str, Any]:
        """处理行情批次 - 优化版：一次获取全市场快照"""
        batch_stats = {"success_count": 0, "error_count": 0, "errors": []}

        try:
            # 一次性获取全市场快照（避免频繁调用接口）
            logger.debug(f"📊 获取全市场快照以处理 {len(batch)} 只股票...")
            quotes_map = await self.provider.get_batch_stock_quotes(batch)

            if not quotes_map:
                logger.warning("⚠️ 获取全市场快照失败，回退到逐个获取")
                # 回退到原来的逐个获取方式
                return await self._process_quotes_batch_fallback(batch)

            # 批量保存到数据库
            for symbol in batch:
                try:
                    quotes = quotes_map.get(symbol)
                    if quotes:
                        # 转换为字典格式
                        quotes_data = self._as_dict(quotes)

                        # 确保 symbol 和 code 字段存在
                        if "symbol" not in quotes_data:
                            quotes_data["symbol"] = symbol
                        if "code" not in quotes_data:
                            quotes_data["code"] = symbol
                        if "source" not in quotes_data:
                            quotes_data["source"] = "akshare"

                        # 更新到数据库
                        await self.db.market_quotes.update_one(
                            {"code": symbol}, {"$set": quotes_data}, upsert=True
                        )
                        await dual_write_hot_document("market_quotes", quotes_data)
                        batch_stats["success_count"] += 1
                    else:
                        batch_stats["error_count"] += 1
                        batch_stats["errors"].append(
                            {
                                "code": symbol,
                                "error": "未找到行情数据",
                                "context": "_process_quotes_batch",
                            }
                        )
                except Exception as e:
                    batch_stats["error_count"] += 1
                    batch_stats["errors"].append(
                        {
                            "code": symbol,
                            "error": str(e),
                            "context": "_process_quotes_batch",
                        }
                    )

            return batch_stats

        except Exception as e:
            logger.error(f"❌ 批量处理行情失败: {e}")
            # 回退到原来的逐个获取方式
            return await self._process_quotes_batch_fallback(batch)

    async def _process_quotes_batch_fallback(self, batch: List[str]) -> Dict[str, Any]:
        """处理行情批次 - 回退方案：逐个获取"""
        batch_stats = {"success_count": 0, "error_count": 0, "errors": []}

        # 逐个获取行情数据（添加延迟避免频率限制）
        for symbol in batch:
            try:
                success = await self._get_and_save_quotes(symbol)
                if success:
                    batch_stats["success_count"] += 1
                else:
                    batch_stats["error_count"] += 1
                    batch_stats["errors"].append(
                        {
                            "code": symbol,
                            "error": "获取行情数据失败",
                            "context": "_process_quotes_batch_fallback",
                        }
                    )

                # 添加延迟避免频率限制
                await asyncio.sleep(0.1)

            except Exception as e:
                batch_stats["error_count"] += 1
                batch_stats["errors"].append(
                    {
                        "code": symbol,
                        "error": str(e),
                        "context": "_process_quotes_batch_fallback",
                    }
                )

        return batch_stats

    async def _get_and_save_quotes(self, symbol: str) -> bool:
        """获取并保存单个股票行情"""
        try:
            quotes = await self.provider.get_stock_quotes(symbol)
            if quotes:
                # 转换为字典格式
                quotes_data = self._as_dict(quotes)

                # 确保 symbol 字段存在
                if "symbol" not in quotes_data:
                    quotes_data["symbol"] = symbol
                if "code" not in quotes_data:
                    quotes_data["code"] = symbol
                if "source" not in quotes_data:
                    quotes_data["source"] = "akshare"

                # 🔥 打印即将保存到数据库的数据
                logger.info(f"💾 准备保存 {symbol} 行情到数据库:")
                logger.info(f"   - 最新价(price): {quotes_data.get('price')}")
                logger.info(f"   - 最高价(high): {quotes_data.get('high')}")
                logger.info(f"   - 最低价(low): {quotes_data.get('low')}")
                logger.info(f"   - 开盘价(open): {quotes_data.get('open')}")
                logger.info(f"   - 昨收价(pre_close): {quotes_data.get('pre_close')}")
                logger.info(f"   - 成交量(volume): {quotes_data.get('volume')}")
                logger.info(f"   - 成交额(amount): {quotes_data.get('amount')}")
                logger.info(
                    f"   - 涨跌幅(change_percent): {quotes_data.get('change_percent')}%"
                )

                # 更新到数据库
                result = await self.db.market_quotes.update_one(
                    {"code": symbol}, {"$set": quotes_data}, upsert=True
                )
                await dual_write_hot_document("market_quotes", quotes_data)

                logger.info(
                    f"✅ {symbol} 行情已保存到数据库 (matched={result.matched_count}, modified={result.modified_count}, upserted_id={result.upserted_id})"
                )
                return True
            return False
        except Exception as e:
            logger.error(f"❌ 获取 {symbol} 行情失败: {e}", exc_info=True)
            return False

    async def sync_historical_data(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        symbols: Optional[List[str]] = None,
        incremental: bool = True,
        period: str = "daily",
    ) -> Dict[str, Any]:
        """
        同步历史数据

        Args:
            start_date: 开始日期
            end_date: 结束日期
            symbols: 指定股票代码列表
            incremental: 是否增量同步
            period: 数据周期 (daily/weekly/monthly)

        Returns:
            同步结果统计
        """
        period_name = {"daily": "日线", "weekly": "周线", "monthly": "月线"}.get(
            period, "日线"
        )
        logger.info(f"🔄 开始同步{period_name}历史数据...")

        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "total_records": 0,
            "start_time": utcnow_naive(),
            "end_time": None,
            "duration": 0,
            "errors": [],
        }

        try:
            # 1. 确定全局结束日期
            if not end_date:
                end_date = datetime.now().strftime("%Y-%m-%d")

            # 2. 确定要同步的股票列表
            if symbols is None:
                basic_info_cursor = self.db.stock_basic_info.find({}, {"code": 1})
                symbols = [doc["code"] async for doc in basic_info_cursor]

            if not symbols:
                logger.warning("⚠️ 没有找到要同步的股票")
                return stats

            stats["total_processed"] = len(symbols)

            # 3. 确定全局起始日期（仅用于日志显示）
            global_start_date = start_date
            if not global_start_date:
                if incremental:
                    global_start_date = "各股票最后日期"
                else:
                    global_start_date = (datetime.now() - timedelta(days=365)).strftime(
                        "%Y-%m-%d"
                    )

            logger.info(
                f"📊 历史数据同步: 结束日期={end_date}, 股票数量={len(symbols)}, 模式={'增量' if incremental else '全量'}"
            )

            # 4. 批量处理
            for i in range(0, len(symbols), self.batch_size):
                batch = symbols[i : i + self.batch_size]
                batch_stats = await self._process_historical_batch(
                    batch, start_date, end_date, period, incremental
                )

                # 更新统计
                stats["success_count"] += batch_stats["success_count"]
                stats["error_count"] += batch_stats["error_count"]
                stats["total_records"] += batch_stats["total_records"]
                stats["errors"].extend(batch_stats["errors"])

                # 进度日志
                progress = min(i + self.batch_size, len(symbols))
                logger.info(
                    f"📈 历史数据同步进度: {progress}/{len(symbols)} "
                    f"(成功: {stats['success_count']}, 记录: {stats['total_records']})"
                )

                # API限流
                if i + self.batch_size < len(symbols):
                    await asyncio.sleep(self.rate_limit_delay)

            # 4. 完成统计
            stats["end_time"] = utcnow_naive()
            stats["duration"] = (
                stats["end_time"] - stats["start_time"]
            ).total_seconds()

            logger.info("🎉 历史数据同步完成！")
            logger.info(
                f"📊 总计: {stats['total_processed']}只股票, "
                f"成功: {stats['success_count']}, "
                f"记录: {stats['total_records']}条, "
                f"耗时: {stats['duration']:.2f}秒"
            )

            return stats

        except Exception as e:
            logger.error(f"❌ 历史数据同步失败: {e}")
            stats["errors"].append({"error": str(e), "context": "sync_historical_data"})
            return stats
