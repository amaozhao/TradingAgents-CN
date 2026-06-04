# ruff: noqa: F401,F403,F405,F821
class _TushareSyncServiceMixin2:
    async def sync_historical_data(
        self,
        symbols: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        incremental: bool = True,
        all_history: bool = False,
        period: str = "daily",
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        同步历史数据

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            incremental: 是否增量同步
            all_history: 是否同步所有历史数据
            period: 数据周期 (daily/weekly/monthly)
            job_id: 任务ID（用于进度跟踪）

        Returns:
            同步结果统计
        """
        period_name = {"daily": "日线", "weekly": "周线", "monthly": "月线"}.get(
            period, period
        )
        logger.info(f"🔄 开始同步{period_name}历史数据...")

        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "total_records": 0,
            "start_time": datetime.now(timezone.utc).replace(tzinfo=None),
            "errors": [],
        }

        try:
            # 1. 获取股票列表（排除退市股票）
            if symbols is None:
                # 查询所有A股股票（兼容不同的数据结构），排除退市股票
                # 优先使用 market_info.market，降级到 category 字段
                cursor = self.db.stock_basic_info.find(
                    {
                        "$and": [
                            {
                                "$or": [
                                    {"market_info.market": "CN"},  # 新数据结构
                                    {"category": "stock_cn"},  # 旧数据结构
                                    {
                                        "market": {
                                            "$in": [
                                                "主板",
                                                "创业板",
                                                "科创板",
                                                "北交所",
                                            ]
                                        }
                                    },  # 按市场类型
                                ]
                            },
                            # 排除退市股票
                            {
                                "$or": [
                                    {"status": {"$ne": "D"}},  # status 不是 D（退市）
                                    {
                                        "status": {"$exists": False}
                                    },  # 或者 status 字段不存在
                                ]
                            },
                        ]
                    },
                    {"code": 1},
                )
                symbols = [doc["code"] async for doc in cursor]
                logger.info(
                    f"📋 从 stock_basic_info 获取到 {len(symbols)} 只股票（已排除退市股票）"
                )

            stats["total_processed"] = len(symbols)

            # 2. 确定全局结束日期
            if not end_date:
                end_date = datetime.now().strftime("%Y-%m-%d")

            # 3. 确定全局起始日期（仅用于日志显示）
            global_start_date = start_date
            if not global_start_date:
                if all_history:
                    global_start_date = "1990-01-01"
                elif incremental:
                    global_start_date = "各股票最后日期"
                else:
                    global_start_date = (datetime.now() - timedelta(days=365)).strftime(
                        "%Y-%m-%d"
                    )

            logger.info(
                f"📊 历史数据同步: 结束日期={end_date}, 股票数量={len(symbols)}, 模式={'增量' if incremental else '全量'}"
            )

            # 4. 批量处理
            for i, symbol in enumerate(symbols):
                # 记录单个股票开始时间
                stock_start_time = datetime.now()

                try:
                    # 检查是否需要退出
                    if job_id and await self._should_stop(job_id):
                        logger.warning(f"⚠️ 任务 {job_id} 收到停止信号，正在退出...")
                        stats["stopped"] = True
                        break

                    # 速率限制
                    await self.rate_limiter.acquire()

                    # 确定该股票的起始日期
                    symbol_start_date = start_date
                    if not symbol_start_date:
                        if all_history:
                            symbol_start_date = "1990-01-01"
                        elif incremental:
                            # 增量同步：获取该股票的最后日期
                            symbol_start_date = await self._get_last_sync_date(symbol)
                            logger.debug(
                                f"📅 {symbol}: 从 {symbol_start_date} 开始同步"
                            )
                        else:
                            symbol_start_date = (
                                datetime.now() - timedelta(days=365)
                            ).strftime("%Y-%m-%d")

                    # 记录请求参数
                    logger.debug(
                        f"🔍 {symbol}: 请求{period_name}数据 "
                        f"start={symbol_start_date}, end={end_date}, period={period}"
                    )

                    # ⏱️ 性能监控：API 调用
                    api_start = datetime.now()
                    df = await self.provider.get_historical_data(
                        symbol, symbol_start_date, end_date, period=period
                    )
                    api_duration = (datetime.now() - api_start).total_seconds()

                    if df is not None and not df.empty:
                        # ⏱️ 性能监控：数据保存
                        save_start = datetime.now()
                        records_saved = await self._save_historical_data(
                            symbol, df, period=period
                        )
                        save_duration = (datetime.now() - save_start).total_seconds()

                        stats["success_count"] += 1
                        stats["total_records"] += records_saved

                        # 计算单个股票耗时
                        stock_duration = (
                            datetime.now() - stock_start_time
                        ).total_seconds()
                        logger.info(
                            f"✅ {symbol}: 保存 {records_saved} 条{period_name}记录，"
                            f"总耗时 {stock_duration:.2f}秒 "
                            f"(API: {api_duration:.2f}秒, 保存: {save_duration:.2f}秒)"
                        )
                    else:
                        stock_duration = (
                            datetime.now() - stock_start_time
                        ).total_seconds()
                        logger.warning(
                            f"⚠️ {symbol}: 无{period_name}数据 "
                            f"(start={symbol_start_date}, end={end_date})，耗时 {stock_duration:.2f}秒"
                        )

                    # 每个股票都更新进度
                    progress_percent = int(((i + 1) / len(symbols)) * 100)

                    # 更新任务进度
                    if job_id:
                        await self._update_progress(
                            job_id,
                            progress_percent,
                            f"正在同步 {symbol} ({i + 1}/{len(symbols)})",
                        )

                    # 每50个股票输出一次详细日志
                    if (i + 1) % 50 == 0 or (i + 1) == len(symbols):
                        logger.info(
                            f"📈 {period_name}数据同步进度: {i + 1}/{len(symbols)} ({progress_percent}%) "
                            f"(成功: {stats['success_count']}, 记录: {stats['total_records']})"
                        )

                        # 输出速率限制器统计
                        limiter_stats = self.rate_limiter.get_stats()
                        logger.info(
                            f"   速率限制: {limiter_stats['current_calls']}/{limiter_stats['max_calls']}次, "
                            f"等待次数: {limiter_stats['total_waits']}, "
                            f"总等待时间: {limiter_stats['total_wait_time']:.1f}秒"
                        )

                except Exception as e:
                    traceback = importlib.import_module("traceback")
                    error_details = traceback.format_exc()
                    stats["error_count"] += 1
                    stats["errors"].append(
                        {
                            "code": symbol,
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "context": f"sync_historical_data_{period}",
                            "traceback": error_details,
                        }
                    )
                    logger.error(
                        f"❌ {symbol} {period_name}数据同步失败\n"
                        f"   参数: start={symbol_start_date if 'symbol_start_date' in locals() else 'N/A'}, "
                        f"end={end_date}, period={period}\n"
                        f"   错误类型: {type(e).__name__}\n"
                        f"   错误信息: {str(e)}\n"
                        f"   堆栈跟踪:\n{error_details}"
                    )

            # 4. 完成统计
            stats["end_time"] = datetime.now(timezone.utc).replace(tzinfo=None)
            stats["duration"] = (
                stats["end_time"] - stats["start_time"]
            ).total_seconds()

            logger.info(
                f"✅ {period_name}数据同步完成: "
                f"股票 {stats['success_count']}/{stats['total_processed']}, "
                f"记录 {stats['total_records']} 条, "
                f"错误 {stats['error_count']} 个, "
                f"耗时 {stats['duration']:.2f} 秒"
            )

            return stats

        except Exception as e:
            traceback = importlib.import_module("traceback")
            error_details = traceback.format_exc()
            logger.error(
                f"❌ 历史数据同步失败（外层异常）\n"
                f"   错误类型: {type(e).__name__}\n"
                f"   错误信息: {str(e)}\n"
                f"   堆栈跟踪:\n{error_details}"
            )
            stats["errors"].append(
                {
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "context": "sync_historical_data",
                    "traceback": error_details,
                }
            )
            return stats

    async def _save_historical_data(
        self, symbol: str, df, period: str = "daily"
    ) -> int:
        """保存历史数据到数据库"""
        try:
            if self.historical_service is None:
                self.historical_service = await get_historical_data_service()

            # 使用统一历史数据服务保存（指定周期）
            saved_count = await self.historical_service.save_historical_data(
                symbol=symbol,
                data=df,
                data_source="tushare",
                market="CN",
                period=period,
            )

            return saved_count

        except Exception as e:
            logger.error(f"❌ 保存{period}数据失败 {symbol}: {e}")
            return 0

    async def _get_last_sync_date(self, symbol: Optional[str] = None) -> str:
        """
        获取最后同步日期

        Args:
            symbol: 股票代码，如果提供则返回该股票的最后日期+1天

        Returns:
            日期字符串 (YYYY-MM-DD)
        """
        try:
            if self.historical_service is None:
                self.historical_service = await get_historical_data_service()

            if symbol:
                # 获取特定股票的最新日期
                latest_date = await self.historical_service.get_latest_date(
                    symbol, "tushare"
                )
                if latest_date:
                    # 返回最后日期的下一天（避免重复同步）
                    try:
                        last_date_obj = datetime.strptime(latest_date, "%Y-%m-%d")
                        next_date = last_date_obj + timedelta(days=1)
                        return next_date.strftime("%Y-%m-%d")
                    except Exception:
                        # 如果日期格式不对，直接返回
                        return latest_date
                else:
                    # 🔥 没有历史数据时，从上市日期开始全量同步
                    stock_info = await self.db.stock_basic_info.find_one(
                        {"code": symbol}, {"list_date": 1}
                    )
                    if stock_info and stock_info.get("list_date"):
                        list_date = stock_info["list_date"]
                        # 处理不同的日期格式
                        if isinstance(list_date, str):
                            # 格式可能是 "20100101" 或 "2010-01-01"
                            if len(list_date) == 8 and list_date.isdigit():
                                return (
                                    f"{list_date[:4]}-{list_date[4:6]}-{list_date[6:]}"
                                )
                            else:
                                return list_date
                        else:
                            return list_date.strftime("%Y-%m-%d")

                    # 如果没有上市日期，从1990年开始
                    logger.warning(f"⚠️ {symbol}: 未找到上市日期，从1990-01-01开始同步")
                    return "1990-01-01"

            # 默认返回30天前（确保不漏数据）
            return (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        except Exception as e:
            logger.error(f"❌ 获取最后同步日期失败 {symbol}: {e}")
            # 出错时返回30天前，确保不漏数据
            return (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    async def sync_financial_data(
        self,
        symbols: Optional[List[str]] = None,
        limit: int = 20,
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        同步财务数据

        Args:
            symbols: 股票代码列表，None表示同步所有股票
            limit: 获取财报期数，默认20期（约5年数据）
            job_id: 任务ID（用于进度跟踪）
        """
        logger.info(f"🔄 开始同步财务数据 (获取最近 {limit} 期)...")

        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "start_time": datetime.now(timezone.utc).replace(tzinfo=None),
            "errors": [],
        }

        try:
            # 获取股票列表
            if symbols is None:
                cursor = self.db.stock_basic_info.find(
                    {
                        "$or": [
                            {"market_info.market": "CN"},  # 新数据结构
                            {"category": "stock_cn"},  # 旧数据结构
                            {
                                "market": {
                                    "$in": ["主板", "创业板", "科创板", "北交所"]
                                }
                            },  # 按市场类型
                        ]
                    },
                    {"code": 1},
                )
                symbols = [doc["code"] async for doc in cursor]
                logger.info(f"📋 从 stock_basic_info 获取到 {len(symbols)} 只股票")

            stats["total_processed"] = len(symbols)
            logger.info(f"📊 需要同步 {len(symbols)} 只股票财务数据")

            # 批量处理
            for i, symbol in enumerate(symbols):
                try:
                    # 速率限制
                    await self.rate_limiter.acquire()

                    # 获取财务数据（指定获取期数）
                    financial_data = await self.provider.get_financial_data(
                        symbol, limit=limit
                    )

                    if financial_data:
                        # 保存财务数据
                        success = await self._save_financial_data(
                            symbol, financial_data
                        )
                        if success:
                            stats["success_count"] += 1
                        else:
                            stats["error_count"] += 1
                    else:
                        logger.warning(f"⚠️ {symbol}: 无财务数据")

                    # 进度日志和进度跟踪
                    if (i + 1) % 20 == 0:
                        progress = int((i + 1) / len(symbols) * 100)
                        logger.info(
                            f"📈 财务数据同步进度: {i + 1}/{len(symbols)} ({progress}%) "
                            f"(成功: {stats['success_count']}, 错误: {stats['error_count']})"
                        )
                        # 输出速率限制器统计
                        limiter_stats = self.rate_limiter.get_stats()
                        logger.info(
                            f"   速率限制: {limiter_stats['current_calls']}/{limiter_stats['max_calls']}次"
                        )

                        # 更新任务进度
                        if job_id:
                            update_job_progress = getattr(
                                importlib.import_module("app.services.scheduler"),
                                "update_job_progress",
                            )
                            TaskCancelledException = getattr(
                                importlib.import_module("app.services.scheduler"),
                                "TaskCancelledException",
                            )
                            try:
                                await update_job_progress(
                                    job_id=job_id,
                                    progress=progress,
                                    message=f"正在同步 {symbol} 财务数据",
                                    current_item=symbol,
                                    total_items=len(symbols),
                                    processed_items=i + 1,
                                )
                            except TaskCancelledException:
                                # 任务被取消，记录并退出
                                logger.warning(
                                    f"⚠️ 财务数据同步任务被用户取消 (已处理 {i + 1}/{len(symbols)})"
                                )
                                stats["end_time"] = datetime.now(timezone.utc).replace(
                                    tzinfo=None
                                )
                                stats["duration"] = (
                                    stats["end_time"] - stats["start_time"]
                                ).total_seconds()
                                stats["cancelled"] = True
                                raise

                except Exception as e:
                    stats["error_count"] += 1
                    stats["errors"].append(
                        {
                            "code": symbol,
                            "error": str(e),
                            "context": "sync_financial_data",
                        }
                    )
                    logger.error(f"❌ {symbol} 财务数据同步失败: {e}")

            # 完成统计
            stats["end_time"] = datetime.now(timezone.utc).replace(tzinfo=None)
            stats["duration"] = (
                stats["end_time"] - stats["start_time"]
            ).total_seconds()

            logger.info(
                f"✅ 财务数据同步完成: "
                f"成功 {stats['success_count']}/{stats['total_processed']}, "
                f"错误 {stats['error_count']} 个, "
                f"耗时 {stats['duration']:.2f} 秒"
            )

            return stats

        except Exception as e:
            logger.error(f"❌ 财务数据同步失败: {e}")
            stats["errors"].append({"error": str(e), "context": "sync_financial_data"})
            return stats

    async def _save_financial_data(
        self, symbol: str, financial_data: Dict[str, Any]
    ) -> bool:
        """保存财务数据"""
        try:
            # 使用统一的财务数据服务
            get_financial_data_service = getattr(
                importlib.import_module("app.services.market.financial"),
                "get_financial_data_service",
            )

            financial_service = await get_financial_data_service()

            # 保存财务数据
            saved_count = await financial_service.save_financial_data(
                symbol=symbol,
                financial_data=financial_data,
                data_source="tushare",
                market="CN",
                report_period=str(financial_data.get("report_period") or ""),
                report_type=financial_data.get("report_type", "quarterly"),
            )

            return saved_count > 0

        except Exception as e:
            logger.error(f"❌ 保存 {symbol} 财务数据失败: {e}")
            return False

    def _is_data_fresh(self, updated_at: Any, hours: int = 24) -> bool:
        """检查数据是否新鲜"""
        if not updated_at:
            return False

        if isinstance(updated_at, str):
            try:
                updated_at = datetime.fromisoformat(
                    updated_at.replace("Z", "+00:00")
                ).replace(tzinfo=None)
            except ValueError:
                return False
        if not isinstance(updated_at, datetime):
            return False

        threshold = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            hours=hours
        )
        return updated_at > threshold

    async def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        try:
            # 统计各集合的数据量
            basic_info_count = await self.db.stock_basic_info.count_documents({})
            quotes_count = await self.db.market_quotes.count_documents({})

            # 获取最新更新时间
            latest_basic = await self.db.stock_basic_info.find_one(
                {}, sort=[("updated_at", -1)]
            )
            latest_quotes = await self.db.market_quotes.find_one(
                {}, sort=[("updated_at", -1)]
            )

            return {
                "provider_connected": self.provider.is_available(),
                "collections": {
                    "stock_basic_info": {
                        "count": basic_info_count,
                        "latest_update": latest_basic.get("updated_at")
                        if (latest_basic and isinstance(latest_basic, dict))
                        else None,
                    },
                    "market_quotes": {
                        "count": quotes_count,
                        "latest_update": latest_quotes.get("updated_at")
                        if (latest_quotes and isinstance(latest_quotes, dict))
                        else None,
                    },
                },
                "status_time": datetime.now(timezone.utc).replace(tzinfo=None),
            }

        except Exception as e:
            logger.error(f"❌ 获取同步状态失败: {e}")
            return {"error": str(e)}

    async def sync_news_data(
        self,
        symbols: Optional[List[str]] = None,
        hours_back: int = 24,
        max_news_per_stock: int = 20,
        force_update: bool = False,
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        同步新闻数据

        Args:
            symbols: 股票代码列表，为None时获取所有股票
            hours_back: 回溯小时数，默认24小时
            max_news_per_stock: 每只股票最大新闻数量
            force_update: 是否强制更新
            job_id: 任务ID（用于进度跟踪）

        Returns:
            同步结果统计
        """
        logger.info("🔄 开始同步新闻数据...")

        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "news_count": 0,
            "start_time": datetime.now(timezone.utc).replace(tzinfo=None),
            "errors": [],
        }

        try:
            # 1. 获取股票列表
            if symbols is None:
                stock_list = await self.stock_service.get_stock_list(
                    page=1, page_size=100000
                )
                symbols = [
                    stock["code"]
                    for stock in (self._as_dict(item) for item in stock_list)
                    if stock.get("code")
                ]

            if not symbols:
                logger.warning("⚠️ 没有找到需要同步新闻的股票")
                return stats

            stats["total_processed"] = len(symbols)
            logger.info(f"📊 需要同步 {len(symbols)} 只股票的新闻")

            # 2. 批量处理
            for i in range(0, len(symbols), self.batch_size):
                # 检查是否需要退出
                if job_id and await self._should_stop(job_id):
                    logger.warning(f"⚠️ 任务 {job_id} 收到停止信号，正在退出...")
                    stats["stopped"] = True
                    break

                batch = symbols[i : i + self.batch_size]
                batch_stats = await self._process_news_batch(
                    batch, hours_back, max_news_per_stock
                )

                # 更新统计
                stats["success_count"] += batch_stats["success_count"]
                stats["error_count"] += batch_stats["error_count"]
                stats["news_count"] += batch_stats["news_count"]
                stats["errors"].extend(batch_stats["errors"])

                # 进度日志和进度更新
                progress = min(i + self.batch_size, len(symbols))
                progress_percent = int((progress / len(symbols)) * 100)
                logger.info(
                    f"📈 新闻同步进度: {progress}/{len(symbols)} ({progress_percent}%) "
                    f"(成功: {stats['success_count']}, 新闻: {stats['news_count']})"
                )

                # 更新任务进度
                if job_id:
                    await self._update_progress(
                        job_id,
                        progress_percent,
                        f"已处理 {progress}/{len(symbols)} 只股票，获取 {stats['news_count']} 条新闻",
                    )

                # API限流
                if i + self.batch_size < len(symbols):
                    await asyncio.sleep(self.rate_limit_delay)

            # 3. 完成统计
            stats["end_time"] = datetime.now(timezone.utc).replace(tzinfo=None)
            stats["duration"] = (
                stats["end_time"] - stats["start_time"]
            ).total_seconds()

            logger.info(
                f"✅ 新闻数据同步完成: "
                f"总计 {stats['total_processed']} 只股票, "
                f"成功 {stats['success_count']} 只, "
                f"获取 {stats['news_count']} 条新闻, "
                f"错误 {stats['error_count']} 只, "
                f"耗时 {stats['duration']:.2f} 秒"
            )

            return stats

        except Exception as e:
            logger.error(f"❌ 新闻数据同步失败: {e}")
            stats["errors"].append({"error": str(e), "context": "sync_news_data"})
            return stats
