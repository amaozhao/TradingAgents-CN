from .imports import (
    Depends,
    HTTPException,
    LLMProviderResponse,
    SystemConfigResponse,
    User,
    config_service,
    get_current_user,
    importlib,
    ok,
    router,
    status,
)
from .setup import (
    ConfigApiResponse,
    _sanitize_database_configs,
    _sanitize_datasource_configs,
    _sanitize_kv,
    _sanitize_llm_configs,
)

@router.get("/system", response_model=ConfigApiResponse)
async def get_system_config(current_user: User = Depends(get_current_user)):
    """获取系统配置"""
    try:
        config = await config_service.get_system_config()
        if not config:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="系统配置不存在")

        return ok(
            data=SystemConfigResponse(
                config_name=config.config_name,
                config_type=config.config_type,
                llm_configs=_sanitize_llm_configs(config.llm_configs),
                default_llm=config.default_llm,
                data_source_configs=_sanitize_datasource_configs(config.data_source_configs),
                default_data_source=config.default_data_source,
                database_configs=_sanitize_database_configs(config.database_configs),
                system_settings=_sanitize_kv(config.system_settings),
                created_at=config.created_at,
                updated_at=config.updated_at,
                version=config.version,
                is_active=config.is_active,
            ),
            message="获取系统配置成功",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统配置失败: {str(e)}",
        )


# ========== 大模型厂家管理 ==========


@router.get("/llm/providers", response_model=ConfigApiResponse)
async def get_llm_providers(current_user: User = Depends(get_current_user)):
    """获取所有大模型厂家"""
    try:
        is_valid_api_key = getattr(importlib.import_module("app.utils.keys"), "is_valid_api_key")
        truncate_api_key = getattr(importlib.import_module("app.utils.keys"), "truncate_api_key")
        get_env_api_key_for_provider = getattr(
            importlib.import_module("app.utils.keys"), "get_env_api_key_for_provider"
        )

        providers = await config_service.get_llm_providers()
        result = []

        for provider in providers:
            # 处理 API Key：优先使用数据库配置，如果数据库没有则检查环境变量
            db_key_valid = is_valid_api_key(provider.api_key)
            if db_key_valid:
                # 数据库中有有效的 API Key，返回缩略版本
                api_key_display = truncate_api_key(provider.api_key)
            else:
                # 数据库中没有有效的 API Key，尝试从环境变量读取
                env_key = get_env_api_key_for_provider(provider.name)
                if env_key:
                    # 环境变量中有有效的 API Key，返回缩略版本
                    api_key_display = truncate_api_key(env_key)
                else:
                    api_key_display = None

            # 处理 API Secret（同样的逻辑）
            db_secret_valid = is_valid_api_key(provider.api_secret)
            if db_secret_valid:
                api_secret_display = truncate_api_key(provider.api_secret)
            else:
                # 注意：API Secret 通常不在环境变量中，所以这里只检查数据库
                api_secret_display = None

            result.append(
                LLMProviderResponse(
                    id=str(provider.id),
                    name=provider.name,
                    display_name=provider.display_name,
                    description=provider.description,
                    website=provider.website,
                    api_doc_url=provider.api_doc_url,
                    logo_url=provider.logo_url,
                    is_active=provider.is_active,
                    supported_features=provider.supported_features,
                    default_base_url=provider.default_base_url,
                    # 返回缩略的 API Key（前6位 + "..." + 后6位）
                    api_key=api_key_display,
                    api_secret=api_secret_display,
                    extra_config={
                        **provider.extra_config,
                        "has_api_key": bool(api_key_display),
                        "has_api_secret": bool(api_secret_display),
                    },
                    created_at=provider.created_at,
                    updated_at=provider.updated_at,
                )
            )

        return ok(data=result, message="获取厂家列表成功")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取厂家列表失败: {str(e)}",
        )
