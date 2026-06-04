# ruff: noqa: F403,F405
from .common import *
from .models import NewsStats


class NewsStatsMixin:
    async def get_news_statistics(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> NewsStats:
        """
        获取新闻统计信息

        Args:
            symbol: 股票代码
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            新闻统计信息
        """
        try:
            collection = self._get_collection()

            # 构建匹配条件
            match_stage = {}

            if symbol:
                match_stage["symbol"] = symbol

            if start_time or end_time:
                time_query = {}
                if start_time:
                    time_query["$gte"] = start_time
                if end_time:
                    time_query["$lte"] = end_time
                match_stage["publish_time"] = time_query

            # 聚合管道
            pipeline = []

            if match_stage:
                pipeline.append({"$match": match_stage})

            pipeline.extend(
                [
                    {
                        "$group": {
                            "_id": None,
                            "total_count": {"$sum": 1},
                            "positive_count": {
                                "$sum": {
                                    "$cond": [{"$eq": ["$sentiment", "positive"]}, 1, 0]
                                }
                            },
                            "negative_count": {
                                "$sum": {
                                    "$cond": [{"$eq": ["$sentiment", "negative"]}, 1, 0]
                                }
                            },
                            "neutral_count": {
                                "$sum": {
                                    "$cond": [{"$eq": ["$sentiment", "neutral"]}, 1, 0]
                                }
                            },
                            "high_importance_count": {
                                "$sum": {
                                    "$cond": [{"$eq": ["$importance", "high"]}, 1, 0]
                                }
                            },
                            "medium_importance_count": {
                                "$sum": {
                                    "$cond": [{"$eq": ["$importance", "medium"]}, 1, 0]
                                }
                            },
                            "low_importance_count": {
                                "$sum": {
                                    "$cond": [{"$eq": ["$importance", "low"]}, 1, 0]
                                }
                            },
                            "categories": {"$push": "$category"},
                            "sources": {"$push": "$data_source"},
                        }
                    }
                ]
            )

            # 执行聚合
            result = await collection.aggregate(pipeline).to_list(length=1)

            if result:
                data = result[0]

                # 统计分类和来源
                categories = {}
                for cat in data.get("categories", []):
                    categories[cat] = categories.get(cat, 0) + 1

                sources = {}
                for src in data.get("sources", []):
                    sources[src] = sources.get(src, 0) + 1

                return NewsStats(
                    total_count=data.get("total_count", 0),
                    positive_count=data.get("positive_count", 0),
                    negative_count=data.get("negative_count", 0),
                    neutral_count=data.get("neutral_count", 0),
                    high_importance_count=data.get("high_importance_count", 0),
                    medium_importance_count=data.get("medium_importance_count", 0),
                    low_importance_count=data.get("low_importance_count", 0),
                    categories=categories,
                    sources=sources,
                )

            return NewsStats()

        except Exception as e:
            self.logger.error(f"❌ 获取新闻统计失败: {e}")
            return NewsStats()

    async def delete_old_news(self, days_to_keep: int = 90) -> int:
        """
        删除过期新闻

        Args:
            days_to_keep: 保留天数

        Returns:
            删除的记录数量
        """
        try:
            collection = self._get_collection()

            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            documents_to_delete = await collection.find(
                {"publish_time": {"$lt": cutoff_date}}
            ).to_list(length=None)

            result = await collection.delete_many(
                {"publish_time": {"$lt": cutoff_date}}
            )

            deleted_count = result.deleted_count
            if deleted_count:
                await self._dual_write_news_tombstones(documents_to_delete)
            self.logger.info(f"🗑️ 删除过期新闻: {deleted_count}条记录")

            return deleted_count

        except Exception as e:
            self.logger.error(f"❌ 删除过期新闻失败: {e}")
            return 0

    async def _dual_write_news(self, documents: List[Dict[str, Any]]) -> None:
        if not documents:
            return
        result = await dual_write_hot_documents("stock_news", documents)
        if result.status == "failed":
            self.logger.warning("⚠️ 新闻数据 PostgreSQL 双写失败: %s", result.reason)

    async def _dual_write_news_tombstones(
        self, documents: List[Dict[str, Any]]
    ) -> None:
        if not documents:
            return
        tombstones = [
            {**document, "deleted": True, "updated_at": datetime.utcnow()}
            for document in documents
        ]
        result = await dual_write_hot_documents("stock_news", tombstones)
        if result.status == "failed":
            self.logger.warning(
                "⚠️ 新闻数据 PostgreSQL tombstone 双写失败: %s", result.reason
            )
