# ruff: noqa: F403,F405
from .common import *


class NewsWriteMixin:
    async def save_news_data(
        self,
        news_data: Union[Dict[str, Any], List[Dict[str, Any]]],
        data_source: str,
        market: str = "CN",
    ) -> int:
        """
        保存新闻数据

        Args:
            news_data: 新闻数据（单条或多条）
            data_source: 数据源标识
            market: 市场标识

        Returns:
            保存的记录数量
        """
        try:
            # 🔥 确保索引存在（第一次调用时创建）
            await self._ensure_indexes()

            collection = self._get_collection()
            now = datetime.utcnow()

            # 标准化数据
            if isinstance(news_data, dict):
                news_list = [news_data]
            else:
                news_list = news_data

            if not news_list:
                return 0

            # 准备批量操作
            operations = []
            postgres_documents = []

            for i, news in enumerate(news_list):
                # 标准化新闻数据
                standardized_news = self._standardize_news_data(
                    news, data_source, market, now
                )

                # 🔍 记录前3条数据的详细信息
                if i < 3:
                    self.logger.info(f"   📝 标准化后的新闻 {i + 1}:")
                    self.logger.info(f"      symbol: {standardized_news.get('symbol')}")
                    self.logger.info(
                        f"      title: {standardized_news.get('title', '')[:50]}..."
                    )
                    self.logger.info(
                        f"      publish_time: {standardized_news.get('publish_time')} (type: {type(standardized_news.get('publish_time'))})"
                    )
                    self.logger.info(
                        f"      url: {standardized_news.get('url', '')[:80]}..."
                    )

                # 使用URL、标题和发布时间作为唯一标识
                filter_query = {
                    "url": standardized_news["url"],
                    "title": standardized_news["title"],
                    "publish_time": standardized_news["publish_time"],
                }

                operations.append(
                    ReplaceOne(filter_query, standardized_news, upsert=True)
                )
                postgres_documents.append(standardized_news)

            # 执行批量操作
            if operations:
                result = await collection.bulk_write(operations)
                saved_count = result.upserted_count + result.modified_count
                await self._dual_write_news(postgres_documents)

                self.logger.info(
                    f"💾 新闻数据保存完成: {saved_count}条记录 (数据源: {data_source})"
                )
                return saved_count

            return 0

        except BulkWriteError as e:
            # 处理批量写入错误，但不完全失败
            write_errors = e.details.get("writeErrors", [])
            error_count = len(write_errors)
            self.logger.warning(f"⚠️ 部分新闻数据保存失败: {error_count}条错误")

            # 记录详细错误信息
            for i, error in enumerate(write_errors[:3], 1):  # 只记录前3个错误
                error_msg = error.get("errmsg", "Unknown error")
                error_code = error.get("code", "N/A")
                self.logger.warning(f"   错误 {i}: [Code {error_code}] {error_msg}")

            # 计算成功保存的数量
            success_count = len(operations) - error_count
            if success_count > 0:
                self.logger.info(f"💾 成功保存 {success_count} 条新闻数据")

            return success_count

        except Exception as e:
            self.logger.error(f"❌ 保存新闻数据失败: {e}")
            return 0

    def save_news_data_sync(
        self,
        news_data: Union[Dict[str, Any], List[Dict[str, Any]]],
        data_source: str,
        market: str = "CN",
    ) -> int:
        """
        保存新闻数据（同步版本）
        用于非异步上下文，使用同步的 PostgreSQL document store 客户端

        Args:
            news_data: 新闻数据（单条或多条）
            data_source: 数据源标识
            market: 市场标识

        Returns:
            保存的记录数量
        """
        try:
            get_postgres_db_sync = getattr(
                importlib.import_module("app.core.database"), "get_postgres_db_sync"
            )

            # 获取同步数据库连接
            db = get_postgres_db_sync()
            collection = db.stock_news
            now = datetime.utcnow()

            # 标准化数据
            if isinstance(news_data, dict):
                news_list = [news_data]
            else:
                news_list = news_data

            if not news_list:
                return 0

            # 准备批量操作
            operations = []

            self.logger.info(f"📝 开始标准化 {len(news_list)} 条新闻数据...")

            for i, news in enumerate(news_list, 1):
                # 标准化新闻数据
                standardized_news = self._standardize_news_data(
                    news, data_source, market, now
                )

                # 记录前3条新闻的详细信息
                if i <= 3:
                    self.logger.info(f"   📝 标准化后的新闻 {i}:")
                    self.logger.info(f"      symbol: {standardized_news.get('symbol')}")
                    self.logger.info(
                        f"      title: {standardized_news.get('title', '')[:50]}..."
                    )
                    publish_time = standardized_news.get("publish_time")
                    self.logger.info(
                        f"      publish_time: {publish_time} (type: {type(publish_time)})"
                    )
                    self.logger.info(
                        f"      url: {standardized_news.get('url', '')[:60]}..."
                    )

                # 使用URL+标题+发布时间作为唯一标识
                filter_query = {
                    "url": standardized_news.get("url"),
                    "title": standardized_news.get("title"),
                    "publish_time": standardized_news.get("publish_time"),
                }

                operations.append(
                    ReplaceOne(filter_query, standardized_news, upsert=True)
                )

            # 执行批量操作（同步方式）
            if operations:
                result = collection.bulk_write(operations)
                saved_count = result.upserted_count + result.modified_count

                self.logger.info(
                    f"💾 新闻数据保存完成: {saved_count}条记录 (数据源: {data_source})"
                )
                return saved_count

            return 0

        except BulkWriteError as e:
            # 处理批量写入错误，但不完全失败
            write_errors = e.details.get("writeErrors", [])
            error_count = len(write_errors)
            self.logger.warning(f"⚠️ 部分新闻数据保存失败: {error_count}条错误")

            # 记录详细错误信息
            for i, error in enumerate(write_errors[:3], 1):  # 只记录前3个错误
                error_msg = error.get("errmsg", "Unknown error")
                error_code = error.get("code", "N/A")
                self.logger.warning(f"   错误 {i}: [Code {error_code}] {error_msg}")

            # 计算成功保存的数量
            success_count = len(operations) - error_count
            if success_count > 0:
                self.logger.info(f"💾 成功保存 {success_count} 条新闻数据")

            return success_count

        except Exception as e:
            self.logger.error(f"❌ 保存新闻数据失败: {e}")
            traceback = importlib.import_module("traceback")

            self.logger.error(traceback.format_exc())
            return 0

    def _standardize_news_data(
        self, news_data: Dict[str, Any], data_source: str, market: str, now: datetime
    ) -> Dict[str, Any]:
        """标准化新闻数据"""

        # 提取基础信息
        symbol = news_data.get("symbol")
        symbols = news_data.get("symbols", [])

        # 如果有主要股票代码但symbols为空，添加到symbols中
        if symbol and symbol not in symbols:
            symbols = [symbol] + symbols

        # 标准化数据结构
        standardized = {
            # 基础信息
            "symbol": symbol,
            "full_symbol": self._get_full_symbol(symbol, market) if symbol else None,
            "market": market,
            "symbols": symbols,
            # 新闻内容
            "title": news_data.get("title", ""),
            "content": news_data.get("content", ""),
            "summary": news_data.get("summary", ""),
            "url": news_data.get("url", ""),
            "source": news_data.get("source", ""),
            "author": news_data.get("author", ""),
            # 时间信息
            "publish_time": self._parse_datetime(news_data.get("publish_time")),
            # 分类和标签
            "category": news_data.get("category", "general"),
            "sentiment": news_data.get("sentiment", "neutral"),
            "sentiment_score": self._safe_float(news_data.get("sentiment_score")),
            "keywords": news_data.get("keywords", []),
            "importance": news_data.get("importance", "medium"),
            # 注意：不包含 language 字段，避免与 PostgreSQL 文本索引冲突
            # 元数据
            "data_source": data_source,
            "created_at": now,
            "updated_at": now,
            "version": 1,
        }

        return standardized
