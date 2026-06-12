from .imports import (
    Any,
    Dict,
    List,
    Optional,
    asyncio,
    datetime,
    get_historical_data_service,
    importlib,
    logger,
    timedelta,
    utcnow_naive,
)

class _AKShareSyncServiceMixin2:
    async def _process_historical_batch(
        self,
        batch: List[str],
        start_date: Optional[str],
        end_date: str,
        period: str = "daily",
        incremental: bool = False,
    ) -> Dict[str, Any]:
        """处理历史数据批次"""
        batch_stats = {
            "success_count": 0,
            "error_count": 0,
            "total_records": 0,
            "errors": [],
        }

        for symbol in batch:
            try:
                # 确定该股票的起始日期
                symbol_start_date = start_date
                if not symbol_start_date:
                    if incremental:
                        # 增量同步：获取该股票的最后日期
                        symbol_start_date = await self._get_last_sync_date(symbol)
                        logger.debug(f"📅 {symbol}: 从 {symbol_start_date} 开始同步")
                    else:
                        # 全量同步：最近1年
                        symbol_start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

                # 获取历史数据
                hist_data = await self.provider.get_historical_data(symbol, symbol_start_date, end_date, period)

                if hist_data is not None and not hist_data.empty:
                    # 保存到统一历史数据集合
                    if self.historical_service is None:
                        self.historical_service = await get_historical_data_service()

                    saved_count = await self.historical_service.save_historical_data(
                        symbol=symbol,
                        data=hist_data,
                        data_source="akshare",
                        market="CN",
                        period=period,
                    )

                    batch_stats["success_count"] += 1
                    batch_stats["total_records"] += saved_count
                    logger.debug(f"✅ {symbol}历史数据同步成功: {saved_count}条记录")
                else:
                    batch_stats["error_count"] += 1
                    batch_stats["errors"].append({
                        "code": symbol,
                        "error": "历史数据为空",
                        "context": "_process_historical_batch",
                    })

            except Exception as e:
                batch_stats["error_count"] += 1
                batch_stats["errors"].append({
                    "code": symbol,
                    "error": str(e),
                    "context": "_process_historical_batch",
                })

        return batch_stats

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
                latest_date = await self.historical_service.get_latest_date(symbol, "akshare")
                if latest_date:
                    # 返回最后日期的下一天（避免重复同步）
                    try:
                        last_date_obj = datetime.strptime(latest_date, "%Y-%m-%d")
                        next_date = last_date_obj + timedelta(days=1)
                        return next_date.strftime("%Y-%m-%d")
                    except ValueError:
                        # 如果日期格式不对，直接返回
                        return latest_date
                else:
                    # 🔥 没有历史数据时，从上市日期开始全量同步
                    stock_info = await self.db.stock_basic_info.find_one({"code": symbol}, {"list_date": 1})
                    if stock_info and stock_info.get("list_date"):
                        list_date = stock_info["list_date"]
                        # 处理不同的日期格式
                        if isinstance(list_date, str):
                            # 格式可能是 "20100101" 或 "2010-01-01"
                            if len(list_date) == 8 and list_date.isdigit():
                                return f"{list_date[:4]}-{list_date[4:6]}-{list_date[6:]}"
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

    async def sync_financial_data(self, symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        同步财务数据

        Args:
            symbols: 指定股票代码列表

        Returns:
            同步结果统计
        """
        logger.info("🔄 开始同步财务数据...")

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
                basic_info_cursor = self.db.stock_basic_info.find(
                    {
                        "$or": [
                            {"market_info.market": "CN"},  # 新数据结构
                            {"category": "stock_cn"},  # 旧数据结构
                            {"market": {"$in": ["主板", "创业板", "科创板", "北交所"]}},  # 按市场类型
                        ]
                    },
                    {"code": 1},
                )
                symbols = [doc["code"] async for doc in basic_info_cursor]
                logger.info(f"📋 从 stock_basic_info 获取到 {len(symbols)} 只股票")

            if not symbols:
                logger.warning("⚠️ 没有找到要同步的股票")
                return stats

            stats["total_processed"] = len(symbols)
            logger.info(f"📊 准备同步 {len(symbols)} 只股票的财务数据")

            # 2. 批量处理
            for i in range(0, len(symbols), self.batch_size):
                batch = symbols[i : i + self.batch_size]
                batch_stats = await self._process_financial_batch(batch)

                # 更新统计
                stats["success_count"] += batch_stats["success_count"]
                stats["error_count"] += batch_stats["error_count"]
                stats["errors"].extend(batch_stats["errors"])

                # 进度日志
                progress = min(i + self.batch_size, len(symbols))
                logger.info(
                    f"📈 财务数据同步进度: {progress}/{len(symbols)} "
                    f"(成功: {stats['success_count']}, 错误: {stats['error_count']})"
                )

                # API限流
                if i + self.batch_size < len(symbols):
                    await asyncio.sleep(self.rate_limit_delay)

            # 3. 完成统计
            stats["end_time"] = utcnow_naive()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

            logger.info("🎉 财务数据同步完成！")
            logger.info(
                f"📊 总计: {stats['total_processed']}只股票, "
                f"成功: {stats['success_count']}, "
                f"错误: {stats['error_count']}, "
                f"耗时: {stats['duration']:.2f}秒"
            )

            return stats

        except Exception as e:
            logger.error(f"❌ 财务数据同步失败: {e}")
            stats["errors"].append({"error": str(e), "context": "sync_financial_data"})
            return stats

    async def _process_financial_batch(self, batch: List[str]) -> Dict[str, Any]:
        """处理财务数据批次"""
        batch_stats = {"success_count": 0, "error_count": 0, "errors": []}

        for symbol in batch:
            try:
                # 获取财务数据
                financial_data = await self.provider.get_financial_data(symbol)

                if financial_data:
                    # 使用统一的财务数据服务保存数据
                    success = await self._save_financial_data(symbol, financial_data)
                    if success:
                        batch_stats["success_count"] += 1
                        logger.debug(f"✅ {symbol}财务数据保存成功")
                    else:
                        batch_stats["error_count"] += 1
                        batch_stats["errors"].append({
                            "code": symbol,
                            "error": "财务数据保存失败",
                            "context": "_process_financial_batch",
                        })
                else:
                    batch_stats["error_count"] += 1
                    batch_stats["errors"].append({
                        "code": symbol,
                        "error": "财务数据为空",
                        "context": "_process_financial_batch",
                    })

            except Exception as e:
                batch_stats["error_count"] += 1
                batch_stats["errors"].append({
                    "code": symbol,
                    "error": str(e),
                    "context": "_process_financial_batch",
                })

        return batch_stats

    async def _save_financial_data(self, symbol: str, financial_data: Dict[str, Any]) -> bool:
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
                data_source="akshare",
                market="CN",
                report_type="quarterly",
            )

            return saved_count > 0

        except Exception as e:
            logger.error(f"❌ 保存 {symbol} 财务数据失败: {e}")
            return False

    async def run_status_check(self) -> Dict[str, Any]:
        """运行状态检查"""
        try:
            logger.info("🔍 开始AKShare状态检查...")

            # 检查提供器连接
            provider_connected = await self.provider.test_connection()

            # 检查数据库集合状态
            collections_status = {}

            # 检查基础信息集合
            basic_count = await self.db.stock_basic_info.count_documents({})
            latest_basic = await self.db.stock_basic_info.find_one({}, sort=[("updated_at", -1)])
            collections_status["stock_basic_info"] = {
                "count": basic_count,
                "latest_update": latest_basic.get("updated_at") if latest_basic else None,
            }

            # 检查行情数据集合
            quotes_count = await self.db.market_quotes.count_documents({})
            latest_quotes = await self.db.market_quotes.find_one({}, sort=[("updated_at", -1)])
            collections_status["market_quotes"] = {
                "count": quotes_count,
                "latest_update": latest_quotes.get("updated_at") if latest_quotes else None,
            }

            status_result = {
                "provider_connected": provider_connected,
                "collections": collections_status,
                "status_time": utcnow_naive(),
            }

            logger.info(f"✅ AKShare状态检查完成: {status_result}")
            return status_result

        except Exception as e:
            logger.error(f"❌ AKShare状态检查失败: {e}")
            return {
                "provider_connected": False,
                "error": str(e),
                "status_time": utcnow_naive(),
            }

    async def _get_favorite_stocks(self) -> List[str]:
        """
        获取所有用户的自选股列表（去重）
        注意：只获取最新的文档，避免获取历史旧数据

        Returns:
            自选股代码列表
        """
        try:
            favorite_codes = set()

            # 方法1：从 users 集合的 favorite_stocks 字段获取
            users_cursor = self.db.users.find(
                {"favorite_stocks": {"$exists": True, "$ne": []}},
                {"favorite_stocks.stock_code": 1, "_id": 0},
            )

            async for user in users_cursor:
                for fav in user.get("favorite_stocks", []):
                    code = fav.get("stock_code")
                    if code:
                        favorite_codes.add(code)

            # 方法2：从 user_favorites 集合获取（兼容旧数据结构）
            # 🔥 只获取最新的一个文档（按 updated_at 降序排序）
            latest_doc = await self.db.user_favorites.find_one(
                {"favorites": {"$exists": True, "$ne": []}},
                {"favorites.stock_code": 1, "_id": 0},
                sort=[("updated_at", -1)],  # 按更新时间降序，获取最新的
            )

            if latest_doc:
                logger.info("📌 从 user_favorites 获取最新文档的自选股")
                for fav in latest_doc.get("favorites", []):
                    code = fav.get("stock_code")
                    if code:
                        favorite_codes.add(code)

            result = sorted(list(favorite_codes))
            logger.info(f"📌 获取到 {len(result)} 只自选股")
            return result

        except Exception as e:
            logger.error(f"❌ 获取自选股列表失败: {e}")
            return []

    async def sync_news_data(
        self,
        symbols: Optional[List[str]] = None,
        max_news_per_stock: int = 20,
        force_update: bool = False,
        favorites_only: bool = True,
    ) -> Dict[str, Any]:
        """
        同步新闻数据

        Args:
            symbols: 股票代码列表，为None时根据favorites_only决定同步范围
            max_news_per_stock: 每只股票最大新闻数量
            force_update: 是否强制更新
            favorites_only: 是否只同步自选股（默认True）

        Returns:
            同步结果统计
        """
        logger.info("🔄 开始同步AKShare新闻数据...")

        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "news_count": 0,
            "start_time": utcnow_naive(),
            "favorites_only": favorites_only,
            "errors": [],
        }

        try:
            # 1. 获取股票列表
            if symbols is None:
                if favorites_only:
                    # 只同步自选股
                    symbols = await self._get_favorite_stocks()
                    logger.info(f"📌 只同步自选股，共 {len(symbols)} 只")
                else:
                    # 获取所有股票（不限制数据源）
                    stock_list = await self.db.stock_basic_info.find({}, {"code": 1, "_id": 0}).to_list(None)
                    symbols = [stock["code"] for stock in stock_list if stock.get("code")]
                    logger.info(f"📊 同步所有股票，共 {len(symbols)} 只")

            if not symbols:
                logger.warning("⚠️ 没有找到需要同步新闻的股票")
                return stats

            stats["total_processed"] = len(symbols)
            logger.info(f"📊 需要同步 {len(symbols)} 只股票的新闻")

            # 2. 批量处理
            for i in range(0, len(symbols), self.batch_size):
                batch = symbols[i : i + self.batch_size]
                batch_stats = await self._process_news_batch(batch, max_news_per_stock)

                # 更新统计
                stats["success_count"] += batch_stats["success_count"]
                stats["error_count"] += batch_stats["error_count"]
                stats["news_count"] += batch_stats["news_count"]
                stats["errors"].extend(batch_stats["errors"])

                # 进度日志
                progress = min(i + self.batch_size, len(symbols))
                logger.info(
                    f"📈 新闻同步进度: {progress}/{len(symbols)} "
                    f"(成功: {stats['success_count']}, 新闻: {stats['news_count']})"
                )

                # API限流
                if i + self.batch_size < len(symbols):
                    await asyncio.sleep(self.rate_limit_delay)

            # 3. 完成统计
            stats["end_time"] = utcnow_naive()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

            logger.info(
                f"✅ AKShare新闻数据同步完成: "
                f"总计 {stats['total_processed']} 只股票, "
                f"成功 {stats['success_count']} 只, "
                f"获取 {stats['news_count']} 条新闻, "
                f"错误 {stats['error_count']} 只, "
                f"耗时 {stats['duration']:.2f} 秒"
            )

            return stats

        except Exception as e:
            logger.error(f"❌ AKShare新闻数据同步失败: {e}")
            stats["errors"].append({"error": str(e), "context": "sync_news_data"})
            return stats

    async def _process_news_batch(self, batch: List[str], max_news_per_stock: int) -> Dict[str, Any]:
        """处理新闻批次"""
        batch_stats = {
            "success_count": 0,
            "error_count": 0,
            "news_count": 0,
            "errors": [],
        }

        for symbol in batch:
            try:
                # 从AKShare获取新闻数据
                news_data = await self.provider.get_stock_news(symbol=symbol, limit=max_news_per_stock)

                if news_data:
                    # 保存新闻数据
                    saved_count = await self.news_service.save_news_data(
                        news_data=news_data, data_source="akshare", market="CN"
                    )

                    batch_stats["success_count"] += 1
                    batch_stats["news_count"] += saved_count

                    logger.debug(f"✅ {symbol} 新闻同步成功: {saved_count}条")
                else:
                    logger.debug(f"⚠️ {symbol} 未获取到新闻数据")
                    batch_stats["success_count"] += 1  # 没有新闻也算成功

                # 🔥 API限流：成功后休眠
                await asyncio.sleep(0.2)

            except Exception as e:
                batch_stats["error_count"] += 1
                error_msg = f"{symbol}: {str(e)}"
                batch_stats["errors"].append(error_msg)
                logger.error(f"❌ {symbol} 新闻同步失败: {e}")

                # 🔥 失败后也要休眠，避免"失败雪崩"
                # 失败时休眠更长时间，给API服务器恢复的机会
                await asyncio.sleep(1.0)

        return batch_stats
