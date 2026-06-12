from .common import (
    DataSourceConfig,
    DataSourceType,
    DatabaseConfig,
    DatabaseType,
    LLMConfig,
    ModelProvider,
    Optional,
    SystemConfig,
    importlib,
    now_tz,
    unified_config,
)


class SystemConfigMixin:
    async def get_system_config(self) -> Optional[SystemConfig]:
        """获取系统配置 - 优先从数据库获取最新数据"""
        try:
            # 直接从数据库获取最新配置，避免缓存问题
            db = await self._get_db()
            config_collection = db.system_configs

            config_data = await config_collection.find_one(
                {"is_active": True}, sort=[("version", -1)]
            )

            if config_data:
                print(
                    f"📊 从数据库获取配置，版本: {config_data.get('version', 0)}, LLM配置数量: {len(config_data.get('llm_configs', []))}"
                )
                return SystemConfig(**config_data)

            # 如果没有配置，创建默认配置
            print("⚠️ 数据库中没有配置，创建默认配置")
            return await self._create_default_config()

        except Exception as e:
            print(f"❌ 从数据库获取配置失败: {e}")

            # 作为最后的回退，尝试从统一配置管理器获取
            try:
                unified_system_config = await unified_config.get_unified_system_config()
                if unified_system_config:
                    print("🔄 回退到统一配置管理器")
                    return unified_system_config
            except Exception as e2:
                print(f"从统一配置获取也失败: {e2}")

            return None

    async def _create_default_config(self) -> SystemConfig:
        """创建默认系统配置"""
        default_config = SystemConfig(
            config_name="默认配置",
            config_type="system",
            llm_configs=[
                LLMConfig(
                    provider=ModelProvider.OPENAI,
                    model_name="gpt-3.5-turbo",
                    api_key="your-openai-api-key",
                    api_base="https://api.openai.com/v1",
                    max_tokens=4000,
                    temperature=0.7,
                    enabled=False,
                    description="OpenAI GPT-3.5 Turbo模型",
                ),
                LLMConfig(
                    provider=ModelProvider.ZHIPU,
                    model_name="glm-4",
                    api_key="your-zhipu-api-key",
                    api_base="https://open.bigmodel.cn/api/paas/v4",
                    max_tokens=4000,
                    temperature=0.7,
                    enabled=True,
                    description="智谱AI GLM-4模型（推荐）",
                ),
                LLMConfig(
                    provider=ModelProvider.QWEN,
                    model_name="qwen-turbo",
                    api_key="your-qwen-api-key",
                    api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
                    max_tokens=4000,
                    temperature=0.7,
                    enabled=False,
                    description="阿里云通义千问模型",
                ),
            ],
            default_llm="glm-4",
            data_source_configs=[
                DataSourceConfig(
                    name="AKShare",
                    type=DataSourceType.AKSHARE,
                    endpoint="https://akshare.akfamily.xyz",
                    timeout=30,
                    rate_limit=100,
                    enabled=True,
                    priority=1,
                    description="AKShare开源金融数据接口",
                ),
                DataSourceConfig(
                    name="BaoStock",
                    type=DataSourceType.BAOSTOCK,
                    endpoint="http://baostock.com",
                    timeout=30,
                    rate_limit=60,
                    enabled=True,
                    priority=0,
                    description="BaoStock免费A股数据接口",
                ),
                DataSourceConfig(
                    name="Tushare",
                    type=DataSourceType.TUSHARE,
                    api_key="your-tushare-token",
                    endpoint="http://api.tushare.pro",
                    timeout=30,
                    rate_limit=200,
                    enabled=False,
                    priority=2,
                    description="Tushare专业金融数据接口",
                ),
            ],
            default_data_source="AKShare",
            database_configs=[
                DatabaseConfig(
                    name="PostgreSQL主库",
                    type=DatabaseType.POSTGRESQL,
                    host="localhost",
                    port=5432,
                    database="trading_agents_cn",
                    enabled=True,
                    description="PostgreSQL主数据库",
                ),
                DatabaseConfig(
                    name="Redis缓存",
                    type=DatabaseType.REDIS,
                    host="localhost",
                    port=6379,
                    database="0",
                    enabled=True,
                    description="Redis缓存数据库",
                ),
            ],
            system_settings={
                "max_concurrent_tasks": 3,
                "default_analysis_timeout": 300,
                "enable_cache": True,
                "cache_ttl": 3600,
                "log_level": "INFO",
                "enable_monitoring": True,
                # Worker/Queue intervals
                "worker_heartbeat_interval_seconds": 30,
                "queue_poll_interval_seconds": 1.0,
                "queue_cleanup_interval_seconds": 60.0,
                # SSE intervals
                "sse_poll_timeout_seconds": 1.0,
                "sse_heartbeat_interval_seconds": 10,
                "sse_task_max_idle_seconds": 300,
                "sse_batch_poll_interval_seconds": 2.0,
                "sse_batch_max_idle_seconds": 600,
                # analysis runtime intervals (optional; DB-managed)
                "ta_hk_min_request_interval_seconds": 2.0,
                "ta_hk_timeout_seconds": 60,
                "ta_hk_max_retries": 3,
                "ta_hk_rate_limit_wait_seconds": 60,
                "ta_hk_cache_ttl_seconds": 86400,
                # 新增：分析引擎数据来源策略
                # 是否优先从 app 缓存(PostgreSQL 文档集合 stock_basic_info / market_quotes) 读取
                "ta_use_app_cache": False,
                "ta_china_min_api_interval_seconds": 0.5,
                "ta_us_min_api_interval_seconds": 1.0,
                "ta_google_news_sleep_min_seconds": 2.0,
                "ta_google_news_sleep_max_seconds": 6.0,
                "app_timezone": "Asia/Shanghai",
            },
        )

        # 保存到数据库
        await self.save_system_config(default_config)
        return default_config

    async def save_system_config(self, config: SystemConfig) -> bool:
        """保存系统配置到数据库"""
        try:
            print(f"💾 开始保存配置，LLM配置数量: {len(config.llm_configs)}")

            # 保存到数据库
            db = await self._get_db()
            config_collection = db.system_configs

            # 更新时间戳和版本
            config.updated_at = now_tz()
            config.version += 1

            # 将当前激活的配置设为非激活
            old_active_configs = await config_collection.find(
                {"is_active": True}
            ).to_list(length=None)
            update_result = await config_collection.update_many(
                {"is_active": True}, {"$set": {"is_active": False}}
            )
            print(f"📝 禁用旧配置数量: {update_result.modified_count}")
            for old_config in old_active_configs:
                await self._dual_write_config_document(
                    "system_configs",
                    {**old_config, "is_active": False, "updated_at": now_tz()},
                )

            # 插入新配置 - 移除_id字段让PostgreSQL自动生成新的
            config_dict = config.model_dump(by_alias=True)
            if "_id" in config_dict:
                del config_dict["_id"]  # 移除旧的_id，让PostgreSQL生成新的

            # 打印即将保存的 system_settings
            system_settings = config_dict.get("system_settings", {})
            print(f"📝 即将保存的 system_settings 包含 {len(system_settings)} 项")
            if "quick_analysis_model" in system_settings:
                print(
                    f"  ✓ 包含 quick_analysis_model: {system_settings['quick_analysis_model']}"
                )
            else:
                print("  ⚠️  不包含 quick_analysis_model")
            if "deep_analysis_model" in system_settings:
                print(
                    f"  ✓ 包含 deep_analysis_model: {system_settings['deep_analysis_model']}"
                )
            else:
                print("  ⚠️  不包含 deep_analysis_model")

            insert_result = await config_collection.insert_one(config_dict)
            print(f"📝 新配置ID: {insert_result.inserted_id}")
            await self._dual_write_config_document(
                "system_configs",
                {**config_dict, "_id": insert_result.inserted_id},
            )

            # 验证保存结果
            saved_config = await config_collection.find_one(
                {"_id": insert_result.inserted_id}
            )
            if saved_config:
                print(
                    f"✅ 配置保存成功，验证LLM配置数量: {len(saved_config.get('llm_configs', []))}"
                )

                # 暂时跳过统一配置同步，避免冲突
                # unified_config.sync_to_legacy_format(config)

                return True
            else:
                print("❌ 配置保存验证失败")
                return False

        except Exception as e:
            print(f"❌ 保存配置失败: {e}")
            traceback = importlib.import_module("traceback")
            traceback.print_exc()
            return False

    async def delete_llm_config(self, provider: str, model_name: str) -> bool:
        """删除大模型配置"""
        try:
            print(f"🗑️ 删除大模型配置 - provider: {provider}, model_name: {model_name}")

            config = await self.get_system_config()
            if not config:
                print("❌ 系统配置为空")
                return False

            print(f"📊 当前大模型配置数量: {len(config.llm_configs)}")

            # 打印所有现有配置
            for i, llm in enumerate(config.llm_configs):
                provider_str = self._provider_to_string(getattr(llm, "provider", ""))
                print(
                    f"   {i + 1}. provider: {provider_str}, model_name: {llm.model_name}"
                )

            # 查找并删除指定的LLM配置
            original_count = len(config.llm_configs)

            # 使用更宽松的匹配条件
            config.llm_configs = [
                llm
                for llm in config.llm_configs
                if not (
                    self._providers_match(getattr(llm, "provider", ""), provider)
                    and llm.model_name == model_name
                )
            ]

            new_count = len(config.llm_configs)
            print(f"🔄 删除后配置数量: {new_count} (原来: {original_count})")

            if new_count == original_count:
                print(f"❌ 没有找到匹配的配置: {provider}/{model_name}")
                return False  # 没有找到要删除的配置

            # 保存更新后的配置
            save_result = await self.save_system_config(config)
            print(f"💾 保存结果: {save_result}")

            return save_result

        except Exception as e:
            print(f"❌ 删除LLM配置失败: {e}")
            traceback = importlib.import_module("traceback")
            traceback.print_exc()
            return False
