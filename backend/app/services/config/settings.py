# ruff: noqa: F403,F405
from .common import *


class SettingsMixin:
    async def _set_default_llm_legacy(self, model_name: str) -> bool:
        """设置默认大模型"""
        try:
            config = await self.get_system_config()
            if not config:
                return False

            # 检查指定的模型是否存在
            model_exists = any(
                llm.model_name == model_name for llm in config.llm_configs
            )

            if not model_exists:
                return False

            config.default_llm = model_name
            return await self.save_system_config(config)

        except Exception as e:
            print(f"设置默认LLM失败: {e}")
            return False

    async def _set_default_data_source_legacy(self, data_source_name: str) -> bool:
        """设置默认数据源"""
        try:
            config = await self.get_system_config()
            if not config:
                return False

            # 检查指定的数据源是否存在
            source_exists = any(
                ds.name == data_source_name for ds in config.data_source_configs
            )

            if not source_exists:
                return False

            config.default_data_source = data_source_name
            return await self.save_system_config(config)

        except Exception as e:
            print(f"设置默认数据源失败: {e}")
            return False

    async def update_system_settings(self, settings: Dict[str, Any]) -> bool:
        """更新系统设置"""
        try:
            config = await self.get_system_config()
            if not config:
                return False

            # 打印更新前的系统设置
            print(f"📝 更新前 system_settings 包含 {len(config.system_settings)} 项")
            if "quick_analysis_model" in config.system_settings:
                print(
                    f"  ✓ 更新前包含 quick_analysis_model: {config.system_settings['quick_analysis_model']}"
                )
            else:
                print("  ⚠️  更新前不包含 quick_analysis_model")

            # 更新系统设置
            config.system_settings.update(settings)

            # 打印更新后的系统设置
            print(f"📝 更新后 system_settings 包含 {len(config.system_settings)} 项")
            if "quick_analysis_model" in config.system_settings:
                print(
                    f"  ✓ 更新后包含 quick_analysis_model: {config.system_settings['quick_analysis_model']}"
                )
            else:
                print("  ⚠️  更新后不包含 quick_analysis_model")
            if "deep_analysis_model" in config.system_settings:
                print(
                    f"  ✓ 更新后包含 deep_analysis_model: {config.system_settings['deep_analysis_model']}"
                )
            else:
                print("  ⚠️  更新后不包含 deep_analysis_model")

            result = await self.save_system_config(config)

            # 同步到文件系统（供 unified_config 使用）
            if result:
                try:
                    unified_config = getattr(
                        importlib.import_module("app.core.unified"), "unified_config"
                    )
                    unified_config.sync_to_legacy_format(config)
                    print("✅ 系统设置已同步到文件系统")
                except Exception as e:
                    print(f"⚠️  同步系统设置到文件系统失败: {e}")

            return result

        except Exception as e:
            print(f"更新系统设置失败: {e}")
            return False

    async def get_system_settings(self) -> Dict[str, Any]:
        """获取系统设置"""
        try:
            config = await self.get_system_config()
            if not config:
                return {}
            return config.system_settings
        except Exception as e:
            print(f"获取系统设置失败: {e}")
            return {}

    async def export_config(self) -> Dict[str, Any]:
        """导出配置"""
        try:
            config = await self.get_system_config()
            if not config:
                return {}

            # 转换为可序列化的字典格式
            # 方案A：导出时对敏感字段脱敏/清空
            def _llm_sanitize(x: LLMConfig):
                d = x.model_dump()
                d["api_key"] = ""
                # 确保必填字段有默认值（防止导出 None 或空字符串）
                # 注意：max_tokens 在 system_configs 中已经有正确的值，直接使用
                if not d.get("max_tokens") or d.get("max_tokens") == "":
                    d["max_tokens"] = 4000
                if not d.get("temperature") and d.get("temperature") != 0:
                    d["temperature"] = 0.7
                if not d.get("timeout") or d.get("timeout") == "":
                    d["timeout"] = 180
                if not d.get("retry_times") or d.get("retry_times") == "":
                    d["retry_times"] = 3
                return d

            def _ds_sanitize(x: DataSourceConfig):
                d = x.model_dump()
                d["api_key"] = ""
                d["api_secret"] = ""
                return d

            def _db_sanitize(x: DatabaseConfig):
                d = x.model_dump()
                d["password"] = ""
                return d

            export_data = {
                "config_name": config.config_name,
                "config_type": config.config_type,
                "llm_configs": [_llm_sanitize(llm) for llm in config.llm_configs],
                "default_llm": config.default_llm,
                "data_source_configs": [
                    _ds_sanitize(ds) for ds in config.data_source_configs
                ],
                "default_data_source": config.default_data_source,
                "database_configs": [
                    _db_sanitize(db) for db in config.database_configs
                ],
                # 方案A：导出时对 system_settings 中的敏感键做脱敏
                "system_settings": {
                    k: (
                        None
                        if any(
                            p in k.lower()
                            for p in (
                                "key",
                                "secret",
                                "password",
                                "token",
                                "client_secret",
                            )
                        )
                        else v
                    )
                    for k, v in (config.system_settings or {}).items()
                },
                "exported_at": now_tz().isoformat(),
                "version": config.version,
            }

            return export_data

        except Exception as e:
            print(f"导出配置失败: {e}")
            return {}

    async def import_config(self, config_data: Dict[str, Any]) -> bool:
        """导入配置"""
        try:
            # 验证配置数据格式
            if not self._validate_config_data(config_data):
                return False

            # 创建新的系统配置（方案A：导入时忽略敏感字段）
            def _llm_sanitize_in(llm: Dict[str, Any]):
                d = dict(llm or {})
                d.pop("api_key", None)
                d["api_key"] = ""
                # 清理空字符串，让 Pydantic 使用默认值
                if d.get("max_tokens") == "" or d.get("max_tokens") is None:
                    d.pop("max_tokens", None)
                if d.get("temperature") == "" or d.get("temperature") is None:
                    d.pop("temperature", None)
                if d.get("timeout") == "" or d.get("timeout") is None:
                    d.pop("timeout", None)
                if d.get("retry_times") == "" or d.get("retry_times") is None:
                    d.pop("retry_times", None)
                return LLMConfig(**d)

            def _ds_sanitize_in(ds: Dict[str, Any]):
                d = dict(ds or {})
                d.pop("api_key", None)
                d.pop("api_secret", None)
                d["api_key"] = ""
                d["api_secret"] = ""
                return DataSourceConfig(**d)

            def _db_sanitize_in(db: Dict[str, Any]):
                d = dict(db or {})
                d.pop("password", None)
                d["password"] = ""
                return DatabaseConfig(**d)

            new_config = SystemConfig(
                config_name=config_data.get("config_name", "导入的配置"),
                config_type="imported",
                llm_configs=[
                    _llm_sanitize_in(llm) for llm in config_data.get("llm_configs", [])
                ],
                default_llm=config_data.get("default_llm"),
                data_source_configs=[
                    _ds_sanitize_in(ds)
                    for ds in config_data.get("data_source_configs", [])
                ],
                default_data_source=config_data.get("default_data_source"),
                database_configs=[
                    _db_sanitize_in(db)
                    for db in config_data.get("database_configs", [])
                ],
                system_settings=config_data.get("system_settings", {}),
            )

            return await self.save_system_config(new_config)

        except Exception as e:
            print(f"导入配置失败: {e}")
            return False

    def _validate_config_data(self, config_data: Dict[str, Any]) -> bool:
        """验证配置数据格式"""
        try:
            required_fields = [
                "llm_configs",
                "data_source_configs",
                "database_configs",
                "system_settings",
            ]
            for field in required_fields:
                if field not in config_data:
                    print(f"配置数据缺少必需字段: {field}")
                    return False

            return True

        except Exception as e:
            print(f"验证配置数据失败: {e}")
            return False

    async def migrate_legacy_config(self) -> bool:
        """迁移传统配置"""
        try:
            # 这里可以调用迁移脚本的逻辑
            # 或者直接在这里实现迁移逻辑
            ConfigMigrator = getattr(
                importlib.import_module("scripts.migrate.config.to.web.api.script"),
                "ConfigMigrator",
            )

            migrator = ConfigMigrator()
            return await migrator.migrate_all_configs()

        except Exception as e:
            print(f"迁移传统配置失败: {e}")
            return False

    async def update_llm_config(self, llm_config: LLMConfig) -> bool:
        """更新大模型配置"""
        try:
            config = await self.get_system_config()
            if not config:
                return False

            now = now_tz()

            # 更新时保留原创建时间；新增时补齐创建时间和更新时间
            for existing_config in config.llm_configs:
                if (
                    self._providers_match(existing_config.provider, llm_config.provider)
                    and existing_config.model_name == llm_config.model_name
                ):
                    llm_config.created_at = existing_config.created_at or now
                    break
            else:
                llm_config.created_at = llm_config.created_at or now

            llm_config.updated_at = now

            # 直接保存到统一配置管理器
            success = unified_config.save_llm_config(llm_config)
            if not success:
                return False

            # 查找并更新对应的LLM配置
            for i, existing_config in enumerate(config.llm_configs):
                if (
                    self._providers_match(existing_config.provider, llm_config.provider)
                    and existing_config.model_name == llm_config.model_name
                ):
                    config.llm_configs[i] = llm_config
                    break
            else:
                # 如果不存在，添加新配置
                config.llm_configs.append(llm_config)

            return await self.save_system_config(config)
        except Exception as e:
            print(f"更新LLM配置失败: {e}")
            return False
