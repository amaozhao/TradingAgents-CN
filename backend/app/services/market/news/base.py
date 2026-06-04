# ruff: noqa: F403,F405
from .common import *


class NewsBaseMixin:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._db = None
        self._collection = None
        self._indexes_ensured = False

    async def _ensure_indexes(self):
        """确保必要的索引存在"""
        if self._indexes_ensured:
            return

        try:
            collection = self._get_collection()
            self.logger.info("📊 检查并创建新闻数据索引...")

            # 1. 唯一索引：防止重复新闻（URL+标题+发布时间）
            await collection.create_index(
                [("url", 1), ("title", 1), ("publish_time", 1)],
                unique=True,
                name="url_title_time_unique",
                background=True,
            )

            # 2. 股票代码索引（查询单只股票的新闻）
            await collection.create_index(
                [("symbol", 1)], name="symbol_index", background=True
            )

            # 3. 多股票代码索引（查询涉及多只股票的新闻）
            await collection.create_index(
                [("symbols", 1)], name="symbols_index", background=True
            )

            # 4. 发布时间索引（按时间范围查询）
            await collection.create_index(
                [("publish_time", -1)], name="publish_time_desc", background=True
            )

            # 5. 复合索引：股票代码+发布时间（常用查询）
            await collection.create_index(
                [("symbol", 1), ("publish_time", -1)],
                name="symbol_time_index",
                background=True,
            )

            # 6. 数据源索引（按数据源筛选）
            await collection.create_index(
                [("data_source", 1)], name="data_source_index", background=True
            )

            # 7. 分类索引（按新闻类别筛选）
            await collection.create_index(
                [("category", 1)], name="category_index", background=True
            )

            # 8. 情感索引（按情感筛选）
            await collection.create_index(
                [("sentiment", 1)], name="sentiment_index", background=True
            )

            # 9. 重要性索引（按重要性筛选）
            await collection.create_index(
                [("importance", 1)], name="importance_index", background=True
            )

            # 10. 更新时间索引（数据维护）
            await collection.create_index(
                [("updated_at", -1)], name="updated_at_index", background=True
            )

            self._indexes_ensured = True
            self.logger.info("✅ 新闻数据索引检查完成")
        except Exception as e:
            # 索引创建失败不应该阻止服务启动
            self.logger.warning(f"⚠️ 创建索引时出现警告（可能已存在）: {e}")

    def _get_collection(self):
        """获取新闻数据集合"""
        if self._collection is None:
            self._db = get_database()
            self._collection = self._db.stock_news
        return self._collection
