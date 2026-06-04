# ruff: noqa: F403,F405
from .common import *


class DataSourceGroupingMixin:
    # ==================== 数据源分组管理 ====================

    async def get_datasource_groupings(self) -> List[DataSourceGrouping]:
        """获取所有数据源分组关系"""
        try:
            db = await self._get_db()
            groupings_collection = db.datasource_groupings

            groupings_data = await groupings_collection.find({}).to_list(length=None)
            return [DataSourceGrouping(**data) for data in groupings_data]
        except Exception as e:
            print(f"❌ 获取数据源分组关系失败: {e}")
            return []

    async def add_datasource_to_category(self, grouping: DataSourceGrouping) -> bool:
        """将数据源添加到分类"""
        try:
            db = await self._get_db()
            groupings_collection = db.datasource_groupings

            # 检查是否已存在
            existing = await groupings_collection.find_one(
                {
                    "data_source_name": grouping.data_source_name,
                    "market_category_id": grouping.market_category_id,
                }
            )
            if existing:
                return False

            document = grouping.model_dump()
            await groupings_collection.insert_one(document)
            await self._dual_write_config_document("datasource_groupings", document)
            return True
        except Exception as e:
            print(f"❌ 添加数据源到分类失败: {e}")
            return False

    async def remove_datasource_from_category(
        self, data_source_name: str, category_id: str
    ) -> bool:
        """从分类中移除数据源"""
        try:
            db = await self._get_db()
            groupings_collection = db.datasource_groupings

            result = await groupings_collection.delete_one(
                {
                    "data_source_name": data_source_name,
                    "market_category_id": category_id,
                }
            )
            if result.deleted_count > 0:
                await self._dual_write_config_tombstone(
                    "datasource_groupings",
                    {
                        "data_source_name": data_source_name,
                        "market_category_id": category_id,
                    },
                )
            return result.deleted_count > 0
        except Exception as e:
            print(f"❌ 从分类中移除数据源失败: {e}")
            return False

    async def update_datasource_grouping(
        self, data_source_name: str, category_id: str, updates: Dict[str, Any]
    ) -> bool:
        """更新数据源分组关系

        🔥 重要：同时更新 datasource_groupings 和 system_configs 两个集合
        - datasource_groupings: 用于前端展示和管理
        - system_configs.data_source_configs: 用于实际数据获取时的优先级判断
        """
        try:
            db = await self._get_db()
            groupings_collection = db.datasource_groupings
            config_collection = db.system_configs

            # 1. 更新 datasource_groupings 集合
            updates["updated_at"] = now_tz()
            result = await groupings_collection.update_one(
                {
                    "data_source_name": data_source_name,
                    "market_category_id": category_id,
                },
                {"$set": updates},
            )
            if result.modified_count > 0:
                await self._dual_write_config_document(
                    "datasource_groupings",
                    {
                        "data_source_name": data_source_name,
                        "market_category_id": category_id,
                        **updates,
                    },
                )

            # 2. 🔥 如果更新了优先级，同步更新 system_configs 集合
            if "priority" in updates and result.modified_count > 0:
                # 获取当前激活的配置
                config_data = await config_collection.find_one(
                    {"is_active": True}, sort=[("version", -1)]
                )

                if config_data:
                    data_source_configs = config_data.get("data_source_configs", [])

                    # 查找并更新对应的数据源配置
                    # 注意：data_source_name 可能是 "AKShare"，而 config 中的 name 也是 "AKShare"
                    # 但是 type 字段是小写的 "akshare"
                    updated = False
                    for ds_config in data_source_configs:
                        # 尝试匹配 name 字段（优先）或 type 字段
                        if (
                            ds_config.get("name") == data_source_name
                            or ds_config.get("type") == data_source_name.lower()
                        ):
                            ds_config["priority"] = updates["priority"]
                            updated = True
                            logger.info(
                                f"✅ [优先级同步] 更新 system_configs 中的数据源: {data_source_name}, 新优先级: {updates['priority']}"
                            )
                            break

                    if updated:
                        # 更新配置版本
                        version = config_data.get("version", 0)
                        await config_collection.update_one(
                            {"_id": config_data["_id"]},
                            {
                                "$set": {
                                    "data_source_configs": data_source_configs,
                                    "version": version + 1,
                                    "updated_at": now_tz(),
                                }
                            },
                        )
                        await self._dual_write_config_document(
                            "system_configs",
                            {
                                **config_data,
                                "data_source_configs": data_source_configs,
                                "version": version + 1,
                                "updated_at": now_tz(),
                            },
                        )
                        logger.info(
                            f"✅ [优先级同步] system_configs 版本更新: {version} -> {version + 1}"
                        )
                    else:
                        logger.warning(
                            f"⚠️ [优先级同步] 未找到匹配的数据源配置: {data_source_name}"
                        )

            return result.modified_count > 0
        except Exception as e:
            logger.error(f"❌ 更新数据源分组关系失败: {e}")
            return False

    async def update_category_datasource_order(
        self, category_id: str, ordered_sources: List[Dict[str, Any]]
    ) -> bool:
        """更新分类中数据源的排序

        🔥 重要：同时更新 datasource_groupings 和 system_configs 两个集合
        - datasource_groupings: 用于前端展示和管理
        - system_configs.data_source_configs: 用于实际数据获取时的优先级判断
        """
        try:
            db = await self._get_db()
            groupings_collection = db.datasource_groupings
            config_collection = db.system_configs

            # 1. 批量更新 datasource_groupings 集合中的优先级
            for item in ordered_sources:
                await groupings_collection.update_one(
                    {
                        "data_source_name": item["name"],
                        "market_category_id": category_id,
                    },
                    {"$set": {"priority": item["priority"], "updated_at": now_tz()}},
                )
                await self._dual_write_config_document(
                    "datasource_groupings",
                    {
                        "data_source_name": item["name"],
                        "market_category_id": category_id,
                        "priority": item["priority"],
                        "updated_at": now_tz(),
                    },
                )

            # 2. 🔥 同步更新 system_configs 集合中的 data_source_configs
            # 获取当前激活的配置
            config_data = await config_collection.find_one(
                {"is_active": True}, sort=[("version", -1)]
            )

            if config_data:
                # 构建数据源名称到优先级的映射
                priority_map = {
                    item["name"]: item["priority"] for item in ordered_sources
                }

                # 更新 data_source_configs 中对应数据源的优先级
                data_source_configs = config_data.get("data_source_configs", [])
                updated = False

                for ds_config in data_source_configs:
                    ds_name = ds_config.get("name")
                    if ds_name in priority_map:
                        ds_config["priority"] = priority_map[ds_name]
                        updated = True
                        print(
                            f"📊 [优先级同步] 更新数据源 {ds_name} 的优先级为 {priority_map[ds_name]}"
                        )

                # 如果有更新，保存回数据库
                if updated:
                    await config_collection.update_one(
                        {"_id": config_data["_id"]},
                        {
                            "$set": {
                                "data_source_configs": data_source_configs,
                                "updated_at": now_tz(),
                                "version": config_data.get("version", 0) + 1,
                            }
                        },
                    )
                    await self._dual_write_config_document(
                        "system_configs",
                        {
                            **config_data,
                            "data_source_configs": data_source_configs,
                            "updated_at": now_tz(),
                            "version": config_data.get("version", 0) + 1,
                        },
                    )
                    print(
                        f"✅ [优先级同步] 已同步更新 system_configs 集合，新版本: {config_data.get('version', 0) + 1}"
                    )
                else:
                    print("⚠️ [优先级同步] 没有找到需要更新的数据源配置")
            else:
                print("⚠️ [优先级同步] 未找到激活的系统配置")

            return True
        except Exception as e:
            print(f"❌ 更新分类数据源排序失败: {e}")
            traceback = importlib.import_module("traceback")
            traceback.print_exc()
            return False
