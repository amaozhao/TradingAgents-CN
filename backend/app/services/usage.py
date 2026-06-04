"""
使用统计服务
管理模型使用记录和成本统计
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.database import get_postgres_db
from app.db.dual import dual_write_hot_document, dual_write_hot_documents
from app.models.config import UsageRecord, UsageStatistics

logger = logging.getLogger("app.services.usage")


class UsageStatisticsService:
    """使用统计服务"""

    def __init__(self):
        # 使用 trading_agents 的集合名称
        self.collection_name = "token_usage"

    async def add_usage_record(self, record: UsageRecord) -> bool:
        """添加使用记录"""
        try:
            db = get_postgres_db()
            collection = db[self.collection_name]

            record_dict = record.model_dump(exclude={"id"})
            result = await collection.insert_one(record_dict)
            record_dict["_id"] = result.inserted_id
            await self._dual_write_usage(record_dict)

            logger.info(f"✅ 添加使用记录成功: {record.provider}/{record.model_name}")
            return True
        except Exception as e:
            logger.error(f"❌ 添加使用记录失败: {e}")
            return False

    async def get_usage_records(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[UsageRecord]:
        """获取使用记录"""
        try:
            db = get_postgres_db()
            collection = db[self.collection_name]

            # 构建查询条件
            query = {}
            if provider:
                query["provider"] = provider
            if model_name:
                query["model_name"] = model_name
            if start_date or end_date:
                query["timestamp"] = {}
                if start_date:
                    query["timestamp"]["$gte"] = start_date.isoformat()
                if end_date:
                    query["timestamp"]["$lte"] = end_date.isoformat()

            # 查询记录
            cursor = collection.find(query).sort("timestamp", -1).limit(limit)
            records = []

            async for doc in cursor:
                doc["id"] = str(doc.pop("_id"))
                records.append(UsageRecord(**doc))

            logger.info(f"✅ 获取使用记录成功: {len(records)} 条")
            return records
        except Exception as e:
            logger.error(f"❌ 获取使用记录失败: {e}")
            return []

    async def get_usage_statistics(
        self,
        days: int = 7,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> UsageStatistics:
        """获取使用统计"""
        try:
            db = get_postgres_db()
            collection = db[self.collection_name]

            # 计算时间范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # 构建查询条件
            query: Dict[str, Any] = {
                "timestamp": {
                    "$gte": start_date.isoformat(),
                    "$lte": end_date.isoformat(),
                }
            }
            if provider:
                query["provider"] = provider
            if model_name:
                query["model_name"] = model_name

            # 获取所有记录
            cursor = collection.find(query)
            records = []
            async for doc in cursor:
                records.append(doc)

            # 统计数据
            stats = UsageStatistics()
            stats.total_requests = len(records)

            # 按货币统计成本
            cost_by_currency = defaultdict(float)

            by_provider = defaultdict(
                lambda: {
                    "requests": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost": 0.0,
                    "cost_by_currency": defaultdict(float),
                }
            )
            by_model = defaultdict(
                lambda: {
                    "requests": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost": 0.0,
                    "cost_by_currency": defaultdict(float),
                }
            )
            by_date = defaultdict(
                lambda: {
                    "requests": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost": 0.0,
                    "cost_by_currency": defaultdict(float),
                }
            )

            for record in records:
                cost = record.get("cost", 0.0)
                currency = record.get("currency", "CNY")

                # 总计
                stats.total_input_tokens += record.get("input_tokens", 0)
                stats.total_output_tokens += record.get("output_tokens", 0)
                stats.total_cost += cost  # 保留向后兼容
                cost_by_currency[currency] += cost

                # 按供应商统计
                provider_key = record.get("provider", "unknown")
                by_provider[provider_key]["requests"] += 1
                by_provider[provider_key]["input_tokens"] += record.get(
                    "input_tokens", 0
                )
                by_provider[provider_key]["output_tokens"] += record.get(
                    "output_tokens", 0
                )
                by_provider[provider_key]["cost"] += cost
                by_provider[provider_key]["cost_by_currency"][currency] += cost

                # 按模型统计
                model_key = f"{record.get('provider', 'unknown')}/{record.get('model_name', 'unknown')}"
                by_model[model_key]["requests"] += 1
                by_model[model_key]["input_tokens"] += record.get("input_tokens", 0)
                by_model[model_key]["output_tokens"] += record.get("output_tokens", 0)
                by_model[model_key]["cost"] += cost
                by_model[model_key]["cost_by_currency"][currency] += cost

                # 按日期统计
                timestamp = record.get("timestamp", "")
                if timestamp:
                    date_key = timestamp[:10]  # YYYY-MM-DD
                    by_date[date_key]["requests"] += 1
                    by_date[date_key]["input_tokens"] += record.get("input_tokens", 0)
                    by_date[date_key]["output_tokens"] += record.get("output_tokens", 0)
                    by_date[date_key]["cost"] += cost
                    by_date[date_key]["cost_by_currency"][currency] += cost

            # 转换 defaultdict 为普通 dict（包括嵌套的 cost_by_currency）
            stats.cost_by_currency = dict(cost_by_currency)
            stats.by_provider = {
                k: {**v, "cost_by_currency": dict(v["cost_by_currency"])}
                for k, v in by_provider.items()
            }
            stats.by_model = {
                k: {**v, "cost_by_currency": dict(v["cost_by_currency"])}
                for k, v in by_model.items()
            }
            stats.by_date = {
                k: {**v, "cost_by_currency": dict(v["cost_by_currency"])}
                for k, v in by_date.items()
            }

            logger.info(f"✅ 获取使用统计成功: {stats.total_requests} 条记录")
            return stats
        except Exception as e:
            logger.error(f"❌ 获取使用统计失败: {e}")
            return UsageStatistics()

    async def get_cost_by_provider(self, days: int = 7) -> Dict[str, float]:
        """获取按供应商的成本统计"""
        stats = await self.get_usage_statistics(days=days)
        return {provider: data["cost"] for provider, data in stats.by_provider.items()}

    async def get_cost_by_model(self, days: int = 7) -> Dict[str, float]:
        """获取按模型的成本统计"""
        stats = await self.get_usage_statistics(days=days)
        return {model: data["cost"] for model, data in stats.by_model.items()}

    async def get_daily_cost(self, days: int = 7) -> Dict[str, float]:
        """获取每日成本统计"""
        stats = await self.get_usage_statistics(days=days)
        return {date: data["cost"] for date, data in stats.by_date.items()}

    async def delete_old_records(self, days: int = 90) -> int:
        """删除旧记录"""
        try:
            db = get_postgres_db()
            collection = db[self.collection_name]

            # 计算截止日期
            cutoff_date = datetime.now() - timedelta(days=days)
            records_to_delete = await collection.find(
                {"timestamp": {"$lt": cutoff_date.isoformat()}}
            ).to_list(length=None)

            # 删除旧记录
            result = await collection.delete_many(
                {"timestamp": {"$lt": cutoff_date.isoformat()}}
            )

            deleted_count = result.deleted_count
            if deleted_count:
                await self._dual_write_usage_tombstones(records_to_delete)
            logger.info(f"✅ 删除旧记录成功: {deleted_count} 条")
            return deleted_count
        except Exception as e:
            logger.error(f"❌ 删除旧记录失败: {e}")
            return 0

    async def _dual_write_usage(self, document: Dict[str, Any]) -> None:
        result = await dual_write_hot_document(self.collection_name, document)
        if result.status == "failed":
            logger.warning("⚠️ 使用统计 PostgreSQL 双写失败: %s", result.reason)

    async def _dual_write_usage_tombstones(
        self, documents: List[Dict[str, Any]]
    ) -> None:
        if not documents:
            return
        result = await dual_write_hot_documents(
            self.collection_name,
            [
                {**document, "deleted": True, "updated_at": datetime.now()}
                for document in documents
            ],
        )
        if result.status == "failed":
            logger.warning(
                "⚠️ 使用统计 PostgreSQL tombstone 双写失败: %s", result.reason
            )


# 创建全局实例
usage_statistics_service = UsageStatisticsService()
