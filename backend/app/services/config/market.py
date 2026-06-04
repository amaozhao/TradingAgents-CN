# ruff: noqa: F403,F405
from .common import *


class MarketCategoryMixin:
    # ==================== 市场分类管理 ====================

    async def get_market_categories(self) -> List[MarketCategory]:
        """获取所有市场分类"""
        try:
            db = await self._get_db()
            categories_collection = db.market_categories

            categories_data = await categories_collection.find({}).to_list(length=None)
            categories = [MarketCategory(**data) for data in categories_data]

            # 如果没有分类，创建默认分类
            if not categories:
                categories = await self._create_default_market_categories()

            # 按排序顺序排列
            categories.sort(key=lambda x: x.sort_order)
            return categories
        except Exception as e:
            print(f"❌ 获取市场分类失败: {e}")
            return []

    async def _create_default_market_categories(self) -> List[MarketCategory]:
        """创建默认市场分类"""
        default_categories = [
            MarketCategory(
                id="a_shares",
                name="a_shares",
                display_name="A股",
                description="中国A股市场数据源",
                enabled=True,
                sort_order=1,
            ),
            MarketCategory(
                id="us_stocks",
                name="us_stocks",
                display_name="美股",
                description="美国股票市场数据源",
                enabled=True,
                sort_order=2,
            ),
            MarketCategory(
                id="hk_stocks",
                name="hk_stocks",
                display_name="港股",
                description="香港股票市场数据源",
                enabled=True,
                sort_order=3,
            ),
            MarketCategory(
                id="crypto",
                name="crypto",
                display_name="数字货币",
                description="数字货币市场数据源",
                enabled=True,
                sort_order=4,
            ),
            MarketCategory(
                id="futures",
                name="futures",
                display_name="期货",
                description="期货市场数据源",
                enabled=True,
                sort_order=5,
            ),
        ]

        # 保存到数据库
        db = await self._get_db()
        categories_collection = db.market_categories

        for category in default_categories:
            document = category.model_dump()
            await categories_collection.insert_one(document)
            await self._dual_write_config_document("market_categories", document)

        return default_categories

    async def add_market_category(self, category: MarketCategory) -> bool:
        """添加市场分类"""
        try:
            db = await self._get_db()
            categories_collection = db.market_categories

            # 检查ID是否已存在
            existing = await categories_collection.find_one({"id": category.id})
            if existing:
                return False

            document = category.model_dump()
            await categories_collection.insert_one(document)
            await self._dual_write_config_document("market_categories", document)
            return True
        except Exception as e:
            print(f"❌ 添加市场分类失败: {e}")
            return False

    async def update_market_category(
        self, category_id: str, updates: Dict[str, Any]
    ) -> bool:
        """更新市场分类"""
        try:
            db = await self._get_db()
            categories_collection = db.market_categories

            updates["updated_at"] = now_tz()
            result = await categories_collection.update_one(
                {"id": category_id}, {"$set": updates}
            )
            if result.modified_count > 0:
                await self._dual_write_config_document(
                    "market_categories", {"id": category_id, **updates}
                )
            return result.modified_count > 0
        except Exception as e:
            print(f"❌ 更新市场分类失败: {e}")
            return False

    async def delete_market_category(self, category_id: str) -> bool:
        """删除市场分类"""
        try:
            db = await self._get_db()
            categories_collection = db.market_categories
            groupings_collection = db.datasource_groupings

            # 检查是否有数据源使用此分类
            groupings_count = await groupings_collection.count_documents(
                {"market_category_id": category_id}
            )
            if groupings_count > 0:
                return False

            result = await categories_collection.delete_one({"id": category_id})
            if result.deleted_count > 0:
                await self._dual_write_config_tombstone(
                    "market_categories", {"id": category_id}
                )
            return result.deleted_count > 0
        except Exception as e:
            print(f"❌ 删除市场分类失败: {e}")
            return False
