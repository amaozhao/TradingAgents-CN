#!/usr/bin/env python3
"""
PostgreSQL + Redis 数据库缓存管理器
提供高性能的股票数据缓存和持久化存储
"""

import hashlib
import importlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union
from zoneinfo import ZoneInfo

import pandas as pd

from app.core.config import settings
from app.db.store import create_sync_client
from trader.config.runtime import get_timezone_name

# 导入日志模块
from trader.utils.logging.manager import get_logger

logger = get_logger("agents")

POSTGRES_AVAILABLE = True

# Redis
try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("⚠️ redis 未安装，Redis功能不可用")


class DatabaseCacheManager:
    """PostgreSQL + Redis 数据库缓存管理器"""

    def __init__(
        self,
        postgres_url: Optional[str] = None,
        redis_url: Optional[str] = None,
        postgres_db: str = "trading_agents",
        redis_db: int = 0,
    ):
        """
        初始化数据库缓存管理器

        Args:
            postgres_url: PostgreSQL连接URL，默认使用配置文件端口
            redis_url: Redis连接URL，默认使用配置文件端口
            postgres_db: PostgreSQL数据库名
            redis_db: Redis数据库编号
        """
        self.postgres_url = postgres_url or settings.text_value(
            "POSTGRES_URL", settings.postgres_url
        )
        self.redis_url = redis_url or settings.text_value(
            "REDIS_URL", settings.redis_url
        )
        self.postgres_db_name = postgres_db
        self.redis_db = redis_db

        # 初始化连接
        self.postgres_client: Any = None
        self.postgres_db: Any = None
        self.redis_client: Any = None

        self._init_postgres()
        self._init_redis()

        logger.info("🗄️ 数据库缓存管理器初始化完成")
        logger.error(
            f"   PostgreSQL: {'✅ 已连接' if self.postgres_client else '❌ 未连接'}"
        )
        logger.error(f"   Redis: {'✅ 已连接' if self.redis_client else '❌ 未连接'}")

    def _init_postgres(self):
        """初始化PostgreSQL文档存储兼容连接"""
        if not POSTGRES_AVAILABLE:
            return

        try:
            self.postgres_client = create_sync_client()
            self.postgres_client.admin.command("ping")
            self.postgres_db = self.postgres_client.get_database(self.postgres_db_name)

            # 创建索引
            self._create_postgres_indexes()

            logger.info("✅ PostgreSQL文档存储缓存连接成功")

        except Exception as e:
            logger.error(f"❌ PostgreSQL文档存储缓存连接失败: {e}")
            self.postgres_client = None
            self.postgres_db = None

    def _init_redis(self):
        """初始化Redis连接"""
        if not REDIS_AVAILABLE:
            return

        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                db=self.redis_db,
                socket_timeout=5,
                socket_connect_timeout=5,
                decode_responses=True,
            )
            # 测试连接
            self.redis_client.ping()

            logger.info(f"✅ Redis连接成功: {self.redis_url}")

        except Exception as e:
            logger.error(f"❌ Redis连接失败: {e}")
            self.redis_client = None

    def _create_postgres_indexes(self):
        """创建PostgreSQL索引"""
        if self.postgres_db is None:
            return

        try:
            # 股票数据集合索引
            stock_collection = self.postgres_db.stock_data
            stock_collection.create_index(
                [("symbol", 1), ("data_source", 1), ("start_date", 1), ("end_date", 1)]
            )
            stock_collection.create_index([("created_at", 1)])

            # 新闻数据集合索引
            news_collection = self.postgres_db.news_data
            news_collection.create_index(
                [("symbol", 1), ("data_source", 1), ("date_range", 1)]
            )
            news_collection.create_index([("created_at", 1)])

            # 基本面数据集合索引
            fundamentals_collection = self.postgres_db.fundamentals_data
            fundamentals_collection.create_index(
                [("symbol", 1), ("data_source", 1), ("analysis_date", 1)]
            )
            fundamentals_collection.create_index([("created_at", 1)])

            logger.info("✅ PostgreSQL索引创建完成")

        except Exception as e:
            logger.error(f"⚠️ PostgreSQL索引创建失败: {e}")

    def _generate_cache_key(self, data_type: str, symbol: str, **kwargs) -> str:
        """生成缓存键"""
        params_str = f"{data_type}_{symbol}"
        for key, value in sorted(kwargs.items()):
            params_str += f"_{key}_{value}"

        cache_key = hashlib.md5(params_str.encode()).hexdigest()[:16]
        return f"{data_type}:{symbol}:{cache_key}"

    def save_stock_data(
        self,
        symbol: str,
        data: Union[pd.DataFrame, str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        data_source: str = "unknown",
        market_type: Optional[str] = None,
    ) -> str:
        """
        保存股票数据到PostgreSQL和Redis

        Args:
            symbol: 股票代码
            data: 股票数据
            start_date: 开始日期
            end_date: 结束日期
            data_source: 数据源
            market_type: 市场类型 (us/china)

        Returns:
            cache_key: 缓存键
        """
        cache_key = self._generate_cache_key(
            "stock",
            symbol,
            start_date=start_date,
            end_date=end_date,
            source=data_source,
        )

        # 自动推断市场类型
        if market_type is None:
            # 根据股票代码格式推断市场类型
            re = importlib.import_module("re")

            if re.match(r"^\d{6}$", symbol):  # 6位数字为A股
                market_type = "china"
            else:  # 其他格式为美股
                market_type = "us"

        # 准备文档数据
        doc = {
            "_id": cache_key,
            "symbol": symbol,
            "market_type": market_type,
            "data_type": "stock_data",
            "start_date": start_date,
            "end_date": end_date,
            "data_source": data_source,
            "created_at": datetime.now(ZoneInfo(get_timezone_name())),
            "updated_at": datetime.now(ZoneInfo(get_timezone_name())),
        }

        # 处理数据格式
        if isinstance(data, pd.DataFrame):
            doc["data"] = data.to_json(orient="records", date_format="iso")
            doc["data_format"] = "dataframe_json"
        else:
            doc["data"] = str(data)
            doc["data_format"] = "text"

        # 保存到PostgreSQL（持久化）
        if self.postgres_db is not None:
            try:
                collection = self.postgres_db.stock_data
                collection.replace_one({"_id": cache_key}, doc, upsert=True)
                logger.info(f"💾 股票数据已保存到PostgreSQL: {symbol} -> {cache_key}")
            except Exception as e:
                logger.error(f"⚠️ PostgreSQL保存失败: {e}")

        # 保存到Redis（快速缓存，6小时过期）
        if self.redis_client:
            try:
                redis_data = {
                    "data": doc["data"],
                    "data_format": doc["data_format"],
                    "symbol": symbol,
                    "data_source": data_source,
                    "created_at": doc["created_at"].isoformat(),
                }
                self.redis_client.setex(
                    cache_key,
                    6 * 3600,  # 6小时过期
                    json.dumps(redis_data, ensure_ascii=False),
                )
                logger.info(f"⚡ 股票数据已缓存到Redis: {symbol} -> {cache_key}")
            except Exception as e:
                logger.error(f"⚠️ Redis缓存失败: {e}")

        return cache_key

    def load_stock_data(self, cache_key: str) -> Optional[Union[pd.DataFrame, str]]:
        """从Redis或PostgreSQL加载股票数据"""

        # 首先尝试从Redis加载（更快）
        if self.redis_client:
            try:
                redis_data = self.redis_client.get(cache_key)
                if redis_data:
                    data_dict = json.loads(redis_data)
                    logger.info(f"⚡ 从Redis加载数据: {cache_key}")

                    if data_dict["data_format"] == "dataframe_json":
                        return pd.read_json(data_dict["data"], orient="records")
                    else:
                        return data_dict["data"]
            except Exception as e:
                logger.error(f"⚠️ Redis加载失败: {e}")

        # 如果Redis没有，从PostgreSQL加载
        if self.postgres_db is not None:
            try:
                collection = self.postgres_db.stock_data
                doc = collection.find_one({"_id": cache_key})

                if doc:
                    logger.info(f"💾 从PostgreSQL加载数据: {cache_key}")

                    # 同时更新到Redis缓存
                    if self.redis_client:
                        try:
                            redis_data = {
                                "data": doc["data"],
                                "data_format": doc["data_format"],
                                "symbol": doc["symbol"],
                                "data_source": doc["data_source"],
                                "created_at": doc["created_at"].isoformat(),
                            }
                            self.redis_client.setex(
                                cache_key,
                                6 * 3600,
                                json.dumps(redis_data, ensure_ascii=False),
                            )
                            logger.info("⚡ 数据已同步到Redis缓存")
                        except Exception as e:
                            logger.error(f"⚠️ Redis同步失败: {e}")

                    if doc["data_format"] == "dataframe_json":
                        return pd.read_json(doc["data"], orient="records")
                    else:
                        return doc["data"]

            except Exception as e:
                logger.error(f"⚠️ PostgreSQL加载失败: {e}")

        return None

    def find_cached_stock_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        data_source: Optional[str] = None,
        max_age_hours: int = 6,
    ) -> Optional[str]:
        """查找匹配的缓存数据"""

        # 生成精确匹配的缓存键
        exact_key = self._generate_cache_key(
            "stock",
            symbol,
            start_date=start_date,
            end_date=end_date,
            source=data_source,
        )

        # 检查Redis中是否有精确匹配
        if self.redis_client and self.redis_client.exists(exact_key):
            logger.info(f"⚡ Redis中找到精确匹配: {symbol} -> {exact_key}")
            return exact_key

        # 检查PostgreSQL中的匹配项
        if self.postgres_db is not None:
            try:
                collection = self.postgres_db.stock_data
                cutoff_time = datetime.now(ZoneInfo(get_timezone_name())) - timedelta(
                    hours=max_age_hours
                )

                query = {"symbol": symbol, "created_at": {"$gte": cutoff_time}}

                if data_source:
                    query["data_source"] = data_source
                if start_date:
                    query["start_date"] = start_date
                if end_date:
                    query["end_date"] = end_date

                doc = collection.find_one(query, sort=[("created_at", -1)])

                if doc:
                    cache_key = doc["_id"]
                    logger.info(f"💾 PostgreSQL中找到匹配: {symbol} -> {cache_key}")
                    return cache_key

            except Exception as e:
                logger.error(f"⚠️ PostgreSQL查询失败: {e}")

        logger.error(f"❌ 未找到有效缓存: {symbol}")
        return None

    def save_news_data(
        self,
        symbol: str,
        news_data: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        data_source: str = "unknown",
    ) -> str:
        """保存新闻数据到PostgreSQL和Redis"""
        cache_key = self._generate_cache_key(
            "news", symbol, start_date=start_date, end_date=end_date, source=data_source
        )

        doc = {
            "_id": cache_key,
            "symbol": symbol,
            "data_type": "news_data",
            "date_range": f"{start_date}_{end_date}",
            "start_date": start_date,
            "end_date": end_date,
            "data_source": data_source,
            "data": news_data,
            "created_at": datetime.now(ZoneInfo(get_timezone_name())),
            "updated_at": datetime.now(ZoneInfo(get_timezone_name())),
        }

        # 保存到PostgreSQL
        if self.postgres_db is not None:
            try:
                collection = self.postgres_db.news_data
                collection.replace_one({"_id": cache_key}, doc, upsert=True)
                logger.info(f"📰 新闻数据已保存到PostgreSQL: {symbol} -> {cache_key}")
            except Exception as e:
                logger.error(f"⚠️ PostgreSQL保存失败: {e}")

        # 保存到Redis（24小时过期）
        if self.redis_client:
            try:
                redis_data = {
                    "data": news_data,
                    "symbol": symbol,
                    "data_source": data_source,
                    "created_at": doc["created_at"].isoformat(),
                }
                self.redis_client.setex(
                    cache_key,
                    24 * 3600,  # 24小时过期
                    json.dumps(redis_data, ensure_ascii=False),
                )
                logger.info(f"⚡ 新闻数据已缓存到Redis: {symbol} -> {cache_key}")
            except Exception as e:
                logger.error(f"⚠️ Redis缓存失败: {e}")

        return cache_key

    def save_fundamentals_data(
        self,
        symbol: str,
        fundamentals_data: str,
        analysis_date: Optional[str] = None,
        data_source: str = "unknown",
    ) -> str:
        """保存基本面数据到PostgreSQL和Redis"""
        if not analysis_date:
            analysis_date = datetime.now(ZoneInfo(get_timezone_name())).strftime(
                "%Y-%m-%d"
            )

        cache_key = self._generate_cache_key(
            "fundamentals", symbol, date=analysis_date, source=data_source
        )

        doc = {
            "_id": cache_key,
            "symbol": symbol,
            "data_type": "fundamentals_data",
            "analysis_date": analysis_date,
            "data_source": data_source,
            "data": fundamentals_data,
            "created_at": datetime.now(ZoneInfo(get_timezone_name())),
            "updated_at": datetime.now(ZoneInfo(get_timezone_name())),
        }

        # 保存到PostgreSQL
        if self.postgres_db is not None:
            try:
                collection = self.postgres_db.fundamentals_data
                collection.replace_one({"_id": cache_key}, doc, upsert=True)
                logger.info(f"💼 基本面数据已保存到PostgreSQL: {symbol} -> {cache_key}")
            except Exception as e:
                logger.error(f"⚠️ PostgreSQL保存失败: {e}")

        # 保存到Redis（24小时过期）
        if self.redis_client:
            try:
                redis_data = {
                    "data": fundamentals_data,
                    "symbol": symbol,
                    "data_source": data_source,
                    "analysis_date": analysis_date,
                    "created_at": doc["created_at"].isoformat(),
                }
                self.redis_client.setex(
                    cache_key,
                    24 * 3600,  # 24小时过期
                    json.dumps(redis_data, ensure_ascii=False),
                )
                logger.info(f"⚡ 基本面数据已缓存到Redis: {symbol} -> {cache_key}")
            except Exception as e:
                logger.error(f"⚠️ Redis缓存失败: {e}")

        return cache_key

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        # 标准统计格式（与 file_cache 保持一致）
        stats: Dict[str, Any] = {
            "total_files": 0,
            "stock_data_count": 0,
            "news_count": 0,
            "fundamentals_count": 0,
            "total_size": 0,  # 字节
            "total_size_mb": 0,  # MB
            "skipped_count": 0,
        }

        # 详细的后端信息
        backend_info = {
            "postgres": {"available": self.postgres_db is not None, "collections": {}},
            "redis": {
                "available": self.redis_client is not None,
                "keys": 0,
                "memory_usage": "N/A",
            },
        }

        # PostgreSQL统计
        total_size_bytes = 0
        if self.postgres_db is not None:
            try:
                for collection_name in ["stock_data", "news_data", "fundamentals_data"]:
                    collection = self.postgres_db[collection_name]
                    count = collection.count_documents({})
                    size = self.postgres_db.command("collStats", collection_name).get(
                        "size", 0
                    )
                    backend_info["postgres"]["collections"][collection_name] = {
                        "count": count,
                        "size_mb": round(size / (1024 * 1024), 2),
                    }

                    # 累加到标准统计
                    total_size_bytes += size
                    stats["total_files"] += count

                    # 按类型分类
                    if collection_name == "stock_data":
                        stats["stock_data_count"] += count
                    elif collection_name == "news_data":
                        stats["news_count"] += count
                    elif collection_name == "fundamentals_data":
                        stats["fundamentals_count"] += count

            except Exception as e:
                logger.error(f"⚠️ PostgreSQL统计获取失败: {e}")

        # Redis统计
        if self.redis_client:
            try:
                info = self.redis_client.info()
                backend_info["redis"]["keys"] = info.get("db0", {}).get("keys", 0)
                backend_info["redis"]["memory_usage"] = (
                    f"{info.get('used_memory_human', 'N/A')}"
                )
            except Exception as e:
                logger.error(f"⚠️ Redis统计获取失败: {e}")

        # 设置总大小
        stats["total_size"] = total_size_bytes
        stats["total_size_mb"] = round(total_size_bytes / (1024 * 1024), 2)

        # 添加后端详细信息
        stats["backend_info"] = backend_info

        return stats

    def clear_old_cache(self, max_age_days: int = 7):
        """清理过期缓存"""
        cutoff_time = datetime.now(ZoneInfo(get_timezone_name())) - timedelta(
            days=max_age_days
        )
        cleared_count = 0

        # 清理PostgreSQL
        if self.postgres_db is not None:
            try:
                for collection_name in ["stock_data", "news_data", "fundamentals_data"]:
                    collection = self.postgres_db[collection_name]
                    result = collection.delete_many(
                        {"created_at": {"$lt": cutoff_time}}
                    )
                    cleared_count += result.deleted_count
                    logger.info(
                        f"🧹 PostgreSQL {collection_name} 清理了 {result.deleted_count} 条记录"
                    )
            except Exception as e:
                logger.error(f"⚠️ PostgreSQL清理失败: {e}")

        # Redis会自动过期，不需要手动清理
        logger.info(f"🧹 总共清理了 {cleared_count} 条过期记录")
        return cleared_count

    def close(self):
        """关闭数据库连接"""
        if self.postgres_client:
            self.postgres_client.close()
            logger.info("🔒 PostgreSQL连接已关闭")

        if self.redis_client:
            self.redis_client.close()
            logger.info("🔒 Redis连接已关闭")


# 全局数据库缓存实例
_db_cache_instance = None


def get_db_cache() -> DatabaseCacheManager:
    """获取全局数据库缓存实例"""
    global _db_cache_instance
    if _db_cache_instance is None:
        _db_cache_instance = DatabaseCacheManager()
    return _db_cache_instance
