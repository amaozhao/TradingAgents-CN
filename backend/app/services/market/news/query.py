# ruff: noqa: F403,F405
from .common import *
from .models import NewsQueryParams, convert_document_id_to_str


class NewsQueryMixin:
    def _get_full_symbol(self, symbol: str, market: str) -> Optional[str]:
        """获取完整股票代码"""
        if not symbol:
            return None

        if market == "CN":
            if len(symbol) == 6:
                if symbol.startswith(("60", "68")):
                    return f"{symbol}.SH"
                elif symbol.startswith(("00", "30")):
                    return f"{symbol}.SZ"

        return symbol

    def _parse_datetime(self, dt_value) -> Optional[datetime]:
        """解析日期时间"""
        if dt_value is None:
            return None

        if isinstance(dt_value, datetime):
            return dt_value

        if isinstance(dt_value, str):
            try:
                # 尝试多种日期格式
                formats = [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%dT%H:%M:%SZ",
                    "%Y-%m-%d",
                ]

                for fmt in formats:
                    try:
                        return datetime.strptime(dt_value, fmt)
                    except ValueError:
                        continue

                # 如果都失败了，返回当前时间
                self.logger.warning(f"⚠️ 无法解析日期时间: {dt_value}")
                return datetime.utcnow()

            except Exception:
                return datetime.utcnow()

        return datetime.utcnow()

    def _safe_float(self, value) -> Optional[float]:
        """安全转换为浮点数"""
        if value is None:
            return None

        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    async def query_news(self, params: NewsQueryParams) -> List[Dict[str, Any]]:
        """
        查询新闻数据

        Args:
            params: 查询参数

        Returns:
            新闻数据列表
        """
        try:
            if settings.POSTGRES_READ_ENABLED:
                postgres_results = await self._query_news_from_postgres(params)
                if postgres_results:
                    return postgres_results

            collection = self._get_collection()

            self.logger.info("🔍 [query_news] 开始查询新闻数据")
            self.logger.info(
                f"   参数: symbol={params.symbol}, start_time={params.start_time}, end_time={params.end_time}, limit={params.limit}"
            )

            # 构建查询条件
            query = {}

            if params.symbol:
                query["symbol"] = params.symbol
                self.logger.info(f"   添加查询条件: symbol={params.symbol}")

            if params.symbols:
                query["symbols"] = {"$in": params.symbols}
                self.logger.info(f"   添加查询条件: symbols in {params.symbols}")

            if params.start_time or params.end_time:
                time_query = {}
                if params.start_time:
                    time_query["$gte"] = params.start_time
                if params.end_time:
                    time_query["$lte"] = params.end_time
                query["publish_time"] = time_query
                self.logger.info(
                    f"   添加查询条件: publish_time between {params.start_time} and {params.end_time}"
                )

            if params.category:
                query["category"] = params.category
                self.logger.info(f"   添加查询条件: category={params.category}")

            if params.sentiment:
                query["sentiment"] = params.sentiment
                self.logger.info(f"   添加查询条件: sentiment={params.sentiment}")

            if params.importance:
                query["importance"] = params.importance
                self.logger.info(f"   添加查询条件: importance={params.importance}")

            if params.data_source:
                query["data_source"] = params.data_source
                self.logger.info(f"   添加查询条件: data_source={params.data_source}")

            if params.keywords:
                # 文本搜索
                query["$text"] = {"$search": " ".join(params.keywords)}
                self.logger.info(f"   添加查询条件: text search={params.keywords}")

            self.logger.info(f"   最终查询条件: {query}")

            # 先统计总数
            total_count = await collection.count_documents(query)
            self.logger.info(f"   数据库中符合条件的总记录数: {total_count}")

            # 执行查询
            cursor = collection.find(query)

            # 排序
            cursor = cursor.sort(params.sort_by, params.sort_order)
            self.logger.info(f"   排序: {params.sort_by} ({params.sort_order})")

            # 分页
            cursor = cursor.skip(params.skip).limit(params.limit)
            self.logger.info(f"   分页: skip={params.skip}, limit={params.limit}")

            # 获取结果
            results = await cursor.to_list(length=None)
            self.logger.info(f"   查询返回: {len(results)} 条记录")

            # 🔧 转换 DocumentId 为字符串，避免 JSON 序列化错误
            results = convert_document_id_to_str(results)

            if results:
                self.logger.info("   前3条预览:")
                for i, r in enumerate(results[:3], 1):
                    self.logger.info(
                        f"      {i}. symbol={r.get('symbol')}, title={r.get('title', 'N/A')[:50]}..., publish_time={r.get('publish_time')}"
                    )
            else:
                self.logger.warning("   ⚠️ 查询结果为空")

            self.logger.info(f"✅ [query_news] 查询完成，返回 {len(results)} 条记录")
            return cast(List[Dict[str, Any]], results)

        except Exception as e:
            self.logger.error(f"❌ 查询新闻数据失败: {e}", exc_info=True)
            return []

    async def _query_news_from_postgres(
        self, params: NewsQueryParams
    ) -> List[Dict[str, Any]]:
        try:
            query_news = getattr(importlib.import_module("app.db.news"), "query_news")
            get_session_factory = getattr(
                importlib.import_module("app.core.session"), "get_session_factory"
            )

            async with get_session_factory()() as session:
                return await query_news(session, params)
        except Exception as e:
            self.logger.warning(f"PostgreSQL新闻查询失败，回退PostgreSQL: {e}")
            return []

    async def get_latest_news(
        self, symbol: Optional[str] = None, limit: int = 10, hours_back: int = 24
    ) -> List[Dict[str, Any]]:
        """
        获取最新新闻

        Args:
            symbol: 股票代码，为空则获取所有新闻
            limit: 返回数量限制
            hours_back: 回溯小时数

        Returns:
            最新新闻列表
        """
        start_time = datetime.utcnow() - timedelta(hours=hours_back)

        params = NewsQueryParams(
            symbol=symbol,
            start_time=start_time,
            limit=limit,
            sort_by="publish_time",
            sort_order=-1,
        )

        return await self.query_news(params)
