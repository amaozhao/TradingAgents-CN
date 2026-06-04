"""
数据库连接管理模块
增强版本，支持连接池、健康检查和错误恢复
"""

import atexit
import importlib
import logging
from typing import Optional

from redis.asyncio import ConnectionPool, Redis
from sqlalchemy import text

from app.db.documentstore import (
    PostgresDocumentClient,
    PostgresDocumentDatabase,
    SyncPostgresDocumentClient,
    SyncPostgresDocumentDatabase,
    create_client,
    create_database,
    create_sync_client,
    create_sync_database,
)
from app.db.session import get_session_factory, init_postgres

from .config import settings

logger = logging.getLogger(__name__)

# 全局连接实例
postgres_client: Optional[PostgresDocumentClient] = None
postgres_db: Optional[PostgresDocumentDatabase] = None
redis_client: Optional[Redis] = None
redis_pool: Optional[ConnectionPool] = None

# 同步 PostgreSQL document store 连接（用于非异步上下文）
_sync_postgres_client: Optional[SyncPostgresDocumentClient] = None
_sync_postgres_db: Optional[SyncPostgresDocumentDatabase] = None


def close_sync_postgres_client() -> None:
    """Close the lazily-created synchronous PostgreSQL document-store client."""
    global _sync_postgres_client, _sync_postgres_db

    if _sync_postgres_client is not None:
        _sync_postgres_client.close()
        _sync_postgres_client = None
    _sync_postgres_db = None


atexit.register(close_sync_postgres_client)


class DatabaseManager:
    """数据库连接管理器"""

    def __init__(self):
        self.postgres_client: Optional[PostgresDocumentClient] = None
        self.postgres_db: Optional[PostgresDocumentDatabase] = None
        self.redis_client: Optional[Redis] = None
        self.redis_pool: Optional[ConnectionPool] = None
        self._postgres_healthy = False
        self._redis_healthy = False

    async def init_postgres_document_store(self):
        """初始化 PostgreSQL 文档存储。"""
        try:
            logger.info("🔄 正在初始化PostgreSQL文档存储...")
            await init_postgres()
            session_factory = get_session_factory()
            async with session_factory() as session:
                await session.execute(text("select 1"))

            self.postgres_client = create_client()
            self.postgres_db = create_database()
            self._postgres_healthy = True
            logger.info("✅ PostgreSQL文档存储初始化完成")

        except Exception as e:
            logger.error(f"❌ PostgreSQL文档存储初始化失败: {e}")
            self._postgres_healthy = False
            raise

    async def init_redis(self):
        """初始化Redis连接"""
        try:
            logger.info("🔄 正在初始化Redis连接...")

            # 创建Redis连接池
            self.redis_pool = ConnectionPool.from_url(
                settings.redis_url,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                retry_on_timeout=settings.REDIS_RETRY_ON_TIMEOUT,
                decode_responses=True,
                protocol=2,
                socket_connect_timeout=5,  # 5秒连接超时
                socket_timeout=10,  # 10秒套接字超时
            )

            # 创建Redis客户端
            self.redis_client = Redis(connection_pool=self.redis_pool)

            # 测试连接
            await self.redis_client.ping()
            self._redis_healthy = True

            logger.info("✅ Redis连接成功建立")
            logger.info(f"🔗 连接池大小: {settings.REDIS_MAX_CONNECTIONS}")

        except Exception as e:
            logger.error(f"❌ Redis连接失败: {e}")
            self._redis_healthy = False
            raise

    async def close_connections(self):
        """关闭所有数据库连接"""
        logger.info("🔄 正在关闭数据库连接...")

        # 关闭 PostgreSQL 文档客户端
        if self.postgres_client:
            try:
                self.postgres_client.close()
                self._postgres_healthy = False
                logger.info("✅ PostgreSQL文档存储客户端已关闭")
            except Exception as e:
                logger.error(f"❌ 关闭PostgreSQL文档存储客户端时出错: {e}")

        # 关闭Redis连接
        if self.redis_client:
            try:
                await self.redis_client.close()
                self._redis_healthy = False
                logger.info("✅ Redis连接已关闭")
            except Exception as e:
                logger.error(f"❌ 关闭Redis连接时出错: {e}")

        # 关闭Redis连接池
        if self.redis_pool:
            try:
                await self.redis_pool.disconnect()
                logger.info("✅ Redis连接池已关闭")
            except Exception as e:
                logger.error(f"❌ 关闭Redis连接池时出错: {e}")

    async def health_check(self) -> dict:
        """数据库健康检查"""
        health_status = {
            "postgres": {"status": "unknown", "details": None},
            "redis": {"status": "unknown", "details": None},
        }

        # 检查PostgreSQL
        try:
            if self.postgres_db:
                session_factory = get_session_factory()
                async with session_factory() as session:
                    await session.execute(text("select 1"))
                health_status["postgres"] = {
                    "status": "healthy",
                    "details": {"database": settings.POSTGRES_DB},
                }
                self._postgres_healthy = True
            else:
                health_status["postgres"]["status"] = "disconnected"
        except Exception as e:
            health_status["postgres"] = {
                "status": "unhealthy",
                "details": {"error": str(e)},
            }
            self._postgres_healthy = False

        # 检查Redis
        try:
            if self.redis_client:
                result = await self.redis_client.ping()
                health_status["redis"] = {
                    "status": "healthy",
                    "details": {"ping": result},
                }
                self._redis_healthy = True
            else:
                health_status["redis"]["status"] = "disconnected"
        except Exception as e:
            health_status["redis"] = {
                "status": "unhealthy",
                "details": {"error": str(e)},
            }
            self._redis_healthy = False

        return health_status

    @property
    def is_healthy(self) -> bool:
        """检查所有数据库连接是否健康"""
        return self._postgres_healthy and self._redis_healthy


# 全局数据库管理器实例
db_manager = DatabaseManager()


async def init_database():
    """初始化数据库连接"""
    global postgres_client, postgres_db, redis_client, redis_pool

    try:
        # 初始化PostgreSQL文档存储
        await db_manager.init_postgres_document_store()
        postgres_client = db_manager.postgres_client
        postgres_db = db_manager.postgres_db

        # 初始化Redis
        await db_manager.init_redis()
        redis_client = db_manager.redis_client
        redis_pool = db_manager.redis_pool

        # PostgreSQL现在是主存储，启动阶段必须已经初始化。

        logger.info("🎉 所有数据库连接初始化完成")

        # 🔥 初始化数据库视图和索引
        await init_database_views_and_indexes()

    except Exception as e:
        logger.error(f"💥 数据库初始化失败: {e}")
        raise


async def init_postgres_document_store_only():
    """Initialize only the PostgreSQL document store for tools."""
    global postgres_client, postgres_db

    await db_manager.init_postgres_document_store()
    postgres_client = db_manager.postgres_client
    postgres_db = db_manager.postgres_db


async def init_database_views_and_indexes():
    """初始化数据库视图和索引"""
    try:
        db = get_postgres_db()

        # 1. 创建股票筛选视图
        await create_stock_screening_view(db)

        # 2. 创建必要的索引
        await create_database_indexes(db)

        logger.info("✅ 数据库视图和索引初始化完成")

    except Exception as e:
        logger.warning(f"⚠️ 数据库视图和索引初始化失败: {e}")
        # 不抛出异常，允许应用继续启动


async def create_stock_screening_view(db):
    """创建股票筛选视图"""
    try:
        # 检查视图是否已存在
        collections = await db.list_collection_names()
        if "stock_screening_view" in collections:
            logger.info("📋 视图 stock_screening_view 已存在，跳过创建")
            return

        # 创建视图：将 stock_basic_info、market_quotes 和 stock_financial_data 关联
        pipeline = [
            # 第一步：关联实时行情数据 (market_quotes)
            {
                "$lookup": {
                    "from": "market_quotes",
                    "localField": "code",
                    "foreignField": "code",
                    "as": "quote_data",
                }
            },
            # 第二步：展开 quote_data 数组
            {"$unwind": {"path": "$quote_data", "preserveNullAndEmptyArrays": True}},
            # 第三步：关联财务数据 (stock_financial_data)
            {
                "$lookup": {
                    "from": "stock_financial_data",
                    "let": {"stock_code": "$code", "stock_source": "$source"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$code", "$$stock_code"]},
                                        {"$eq": ["$data_source", "$$stock_source"]},
                                    ]
                                }
                            }
                        },
                        {"$sort": {"report_period": -1}},
                        {"$limit": 1},
                    ],
                    "as": "financial_data",
                }
            },
            # 第四步：展开 financial_data 数组
            {
                "$unwind": {
                    "path": "$financial_data",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            # 第五步：重新组织字段结构
            {
                "$project": {
                    # 基础信息字段
                    "code": 1,
                    "name": 1,
                    "industry": 1,
                    "area": 1,
                    "market": 1,
                    "list_date": 1,
                    "source": 1,
                    # 市值信息
                    "total_mv": 1,
                    "circ_mv": 1,
                    # 估值指标
                    "pe": 1,
                    "pb": 1,
                    "pe_ttm": 1,
                    "pb_mrq": 1,
                    # 财务指标
                    "roe": "$financial_data.roe",
                    "roa": "$financial_data.roa",
                    "netprofit_margin": "$financial_data.netprofit_margin",
                    "gross_margin": "$financial_data.gross_margin",
                    "report_period": "$financial_data.report_period",
                    # 交易指标
                    "turnover_rate": 1,
                    "volume_ratio": 1,
                    # 实时行情数据
                    "close": "$quote_data.close",
                    "open": "$quote_data.open",
                    "high": "$quote_data.high",
                    "low": "$quote_data.low",
                    "pre_close": "$quote_data.pre_close",
                    "pct_chg": "$quote_data.pct_chg",
                    "amount": "$quote_data.amount",
                    "volume": "$quote_data.volume",
                    "trade_date": "$quote_data.trade_date",
                    # 时间戳
                    "updated_at": 1,
                    "quote_updated_at": "$quote_data.updated_at",
                    "financial_updated_at": "$financial_data.updated_at",
                }
            },
        ]

        # 创建视图
        await db.command(
            {
                "create": "stock_screening_view",
                "viewOn": "stock_basic_info",
                "pipeline": pipeline,
            }
        )

        logger.info("✅ 视图 stock_screening_view 创建成功")

    except Exception as e:
        logger.warning(f"⚠️ 创建视图失败: {e}")


async def create_database_indexes(db):
    """创建数据库索引"""
    try:
        # stock_basic_info 的索引
        basic_info = db["stock_basic_info"]
        await basic_info.create_index([("code", 1), ("source", 1)], unique=True)
        await basic_info.create_index([("industry", 1)])
        await basic_info.create_index([("total_mv", -1)])
        await basic_info.create_index([("pe", 1)])
        await basic_info.create_index([("pb", 1)])

        # market_quotes 的索引
        market_quotes = db["market_quotes"]
        await market_quotes.create_index([("code", 1)], unique=True)
        await market_quotes.create_index([("pct_chg", -1)])
        await market_quotes.create_index([("amount", -1)])
        await market_quotes.create_index([("updated_at", -1)])

        logger.info("✅ 数据库索引创建完成")

    except Exception as e:
        logger.warning(f"⚠️ 创建索引失败: {e}")


async def close_database():
    """关闭数据库连接"""
    global postgres_client, postgres_db, redis_client, redis_pool

    await db_manager.close_connections()
    await close_postgres_if_enabled()

    # 清空全局变量
    postgres_client = None
    postgres_db = None
    redis_client = None
    redis_pool = None


async def close_postgres_document_store_only():
    """Close only the PostgreSQL document-store client."""
    global postgres_client, postgres_db

    if db_manager.postgres_client:
        db_manager.postgres_client.close()
        db_manager.postgres_client = None
        db_manager.postgres_db = None
        db_manager._postgres_healthy = False
    postgres_client = None
    postgres_db = None


def postgres_runtime_enabled() -> bool:
    return True


async def init_postgres_if_enabled() -> None:
    if not postgres_runtime_enabled():
        return

    init_postgres = getattr(importlib.import_module("app.db.session"), "init_postgres")

    await init_postgres()


async def close_postgres_if_enabled() -> None:
    close_postgres = getattr(
        importlib.import_module("app.db.session"), "close_postgres"
    )

    await close_postgres()


def get_postgres_client() -> PostgresDocumentClient:
    """获取 PostgreSQL 文档客户端"""
    if postgres_client is None:
        raise RuntimeError("PostgreSQL文档客户端未初始化")
    return postgres_client


def get_postgres_db() -> PostgresDocumentDatabase:
    """获取 PostgreSQL 文档数据库实例"""
    if postgres_db is None:
        raise RuntimeError("PostgreSQL文档数据库未初始化")
    return postgres_db


def get_postgres_db_sync() -> SyncPostgresDocumentDatabase:
    """
    获取同步版本的 PostgreSQL 文档数据库实例
    用于非异步上下文（如普通函数调用）
    """
    global _sync_postgres_client, _sync_postgres_db

    if _sync_postgres_db is not None:
        return _sync_postgres_db

    if _sync_postgres_client is None:
        _sync_postgres_client = create_sync_client()

    _sync_postgres_db = create_sync_database()
    return _sync_postgres_db


def get_redis_client() -> Redis:
    """获取Redis客户端"""
    if redis_client is None:
        raise RuntimeError("Redis客户端未初始化")
    return redis_client


async def get_database_health() -> dict:
    """获取数据库健康状态"""
    return await db_manager.health_check()


# 兼容性别名
init_db = init_database
close_db = close_database


def get_database():
    """获取数据库实例"""
    if db_manager.postgres_db is None:
        raise RuntimeError("PostgreSQL文档数据库未初始化")
    return db_manager.postgres_db
