from .imports import (
    ActionType,
    Any,
    ApiResponse,
    BaseModel,
    ConfigDict,
    DataSourceConfig,
    DatabaseConfig,
    Depends,
    Dict,
    HTTPException,
    LLMConfig,
    List,
    User,
    get_current_user,
    importlib,
    log_operation,
    logger,
    now_tz,
    ok,
    router,
    status,
)

class ConfigApiResponse(ApiResponse):
    """配置接口响应模型；允许 /settings 保留历史顶层透传字段。"""

    model_config = ConfigDict(extra="allow")


# ===== 配置重载端点 =====


@router.post("/reload", response_model=ConfigApiResponse, summary="重新加载配置")
async def reload_config(current_user: dict = Depends(get_current_user)):
    """
    重新加载配置并桥接到环境变量

    用于配置更新后立即生效，无需重启服务
    """
    try:
        reload_bridged_config = getattr(importlib.import_module("app.core.bridge"), "reload_bridged_config")

        success = reload_bridged_config()

        if success:
            await log_operation(
                user_id=str(current_user.get("user_id", "")),
                username=current_user.get("username", "unknown"),
                action_type=ActionType.CONFIG_MANAGEMENT,
                action="重载配置",
                details={"action": "reload_config"},
                ip_address="",
                user_agent="",
            )

            return ok(
                data={
                    "success": True,
                    "message": "配置重载成功",
                    "data": {"reloaded_at": now_tz().isoformat()},
                },
                message="配置重载成功",
            )
        else:
            return ok(
                data={"success": False, "message": "配置重载失败，请查看日志"},
                message="配置重载失败，请查看日志",
            )
    except Exception as e:
        logger.error(f"配置重载失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"配置重载失败: {str(e)}",
        )


# ===== 方案A：敏感字段响应脱敏 & 请求清洗 =====


def _sanitize_llm_configs(items):
    try:
        return [LLMConfig(**{**i.model_dump(), "api_key": None}) for i in items]
    except Exception:
        return items


def _sort_llm_configs_by_newest(items):
    indexed_items = list(enumerate(items))

    def get_sort_key(indexed_item):
        index, item = indexed_item
        time_value = getattr(item, "created_at", None) or getattr(item, "updated_at", None)
        if not time_value:
            return (0, index)

        try:
            return (1, time_value.timestamp())
        except Exception:
            return (0, index)

    return [item for _, item in sorted(indexed_items, key=get_sort_key, reverse=True)]


def _sanitize_datasource_configs(items):
    """
    脱敏数据源配置，返回缩略的 API Key

    逻辑：
    1. 如果数据库中有有效的 API Key，返回缩略版本
    2. 如果数据库中没有，尝试从环境变量读取并返回缩略版本
    3. 如果都没有，返回 None
    """
    try:
        is_valid_api_key = getattr(importlib.import_module("app.utils.keys"), "is_valid_api_key")
        truncate_api_key = getattr(importlib.import_module("app.utils.keys"), "truncate_api_key")
        get_env_api_key_for_datasource = getattr(
            importlib.import_module("app.utils.keys"), "get_env_api_key_for_datasource"
        )

        result = []
        for item in items:
            data = item.model_dump()

            # 处理 API Key
            db_key = data.get("api_key")
            if is_valid_api_key(db_key):
                # 数据库中有有效的 API Key，返回缩略版本
                data["api_key"] = truncate_api_key(db_key)
            else:
                # 数据库中没有有效的 API Key，尝试从环境变量读取
                ds_type = data.get("type")
                if isinstance(ds_type, str):
                    env_key = get_env_api_key_for_datasource(ds_type)
                    if env_key:
                        # 环境变量中有有效的 API Key，返回缩略版本
                        data["api_key"] = truncate_api_key(env_key)
                    else:
                        data["api_key"] = None
                else:
                    data["api_key"] = None

            # 处理 API Secret（同样的逻辑）
            db_secret = data.get("api_secret")
            if is_valid_api_key(db_secret):
                data["api_secret"] = truncate_api_key(db_secret)
            else:
                data["api_secret"] = None

            result.append(DataSourceConfig(**data))

        return result
    except Exception as e:
        print(f"⚠️ 脱敏数据源配置失败: {e}")
        return items


def _sanitize_database_configs(items):
    try:
        return [DatabaseConfig(**{**i.model_dump(), "password": None}) for i in items]
    except Exception:
        return items


def _sanitize_kv(d: Dict[str, Any]) -> Dict[str, Any]:
    """对字典中的可能敏感键进行脱敏（仅用于响应）。"""
    try:
        if not isinstance(d, dict):
            return d
        sens_patterns = ("key", "secret", "password", "token", "client_secret")
        redacted = {}
        for k, v in d.items():
            if isinstance(k, str) and any(p in k.lower() for p in sens_patterns):
                redacted[k] = None
            else:
                redacted[k] = v
        return redacted
    except Exception:
        return d


class SetDefaultRequest(BaseModel):
    """设置默认配置请求"""

    name: str


class FetchProviderModelsRequest(BaseModel):
    """从厂家 API 获取模型列表时的过滤参数"""

    type: str | None = None
    modalities: str | None = None
    features: List[str] | None = None
    provider_names: List[str] | None = None
    model_keyword: str | None = None
    sort_by: str | None = None
    sort_order: str | None = None
    limit: int | None = None
    recommended_only: bool = False
    tools_only: bool = False
    exclude_preview: bool = True


class ToggleProviderRequest(BaseModel):
    """厂家启停请求。"""

    is_active: bool = True


def _current_user_field(current_user: dict | User, key: str, default: Any = None) -> Any:
    if isinstance(current_user, dict):
        return current_user.get(key, default)
    return getattr(current_user, key, default)


def require_admin_user(current_user: dict | User) -> None:
    is_admin = bool(_current_user_field(current_user, "is_admin", False))
    roles = _current_user_field(current_user, "roles", []) or []
    username = str(_current_user_field(current_user, "username", "") or "")
    user_id = str(_current_user_field(current_user, "id", "") or "")

    if is_admin or "admin" in set(roles) or username == "admin" or user_id == "admin":
        return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")


class MarketCategoryUpdateRequest(BaseModel):
    """市场分类局部更新请求，保留额外字段兼容旧前端。"""

    model_config = ConfigDict(extra="allow")

    name: str | None = None
    display_name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    sort_order: int | None = None


class DataSourceGroupingUpdateRequest(BaseModel):
    """数据源分组局部更新请求，保留额外字段兼容旧前端。"""

    model_config = ConfigDict(extra="allow")

    priority: int | None = None
    enabled: bool | None = None


class SystemSettingsUpdateRequest(BaseModel):
    """系统设置更新请求；设置项是动态 key，但入口仍由 Pydantic 校验为对象。"""

    model_config = ConfigDict(extra="allow")


class ImportConfigRequest(BaseModel):
    """配置导入请求；导入内容是动态结构，保留原 payload 兼容。"""

    model_config = ConfigDict(extra="allow")
