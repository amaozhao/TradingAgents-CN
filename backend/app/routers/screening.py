import importlib
import logging
from collections import Counter
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.screening import BASIC_FIELDS_INFO, FieldInfo, ScreeningCondition
from app.schemas.screening import ScreeningRequest as NewScreeningRequest
from app.schemas.screening import ScreeningResponse as NewScreeningResponse
from app.routers.account import get_current_user
from app.services.screening.enhanced import get_enhanced_screening_service

router = APIRouter(tags=["screening"])
logger = logging.getLogger("webapi")


# 筛选字段配置响应模型
class FieldConfigResponse(BaseModel):
    """筛选字段配置响应"""

    fields: Dict[str, FieldInfo]
    categories: Dict[str, List[str]]


class SupportedFieldInfoResponse(BaseModel):
    """增强筛选字段信息响应，保留服务返回的统计和可选值字段。"""

    model_config = ConfigDict(extra="allow")

    name: str
    display_name: str
    field_type: str
    data_type: str
    description: str = ""
    unit: Optional[str] = None
    supported_operators: List[str] = Field(default_factory=list)
    statistics: Any = None
    available_values: Optional[List[Any]] = None


class ConditionValidationResponse(BaseModel):
    """筛选条件验证响应。"""

    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class IndustryItemResponse(BaseModel):
    value: str
    label: str
    count: int


class IndustriesResponse(BaseModel):
    industries: List[IndustryItemResponse]
    total: int
    source: str


# 传统的请求/响应模型（保持向后兼容）
class OrderByItem(BaseModel):
    field: str
    direction: str = Field("desc", pattern=r"^(?i)(asc|desc)$")


class ScreeningRequest(BaseModel):
    market: str = Field("CN", description="市场：CN")
    date: Optional[str] = Field(None, description="交易日YYYY-MM-DD，缺省为最新")
    adj: str = Field("qfq", description="复权口径：qfq/hfq/none（P0占位）")
    conditions: Dict[str, Any] = Field(default_factory=dict)
    order_by: Optional[List[OrderByItem]] = None
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)


class ScreeningResponse(BaseModel):
    total: int
    items: List[dict]


def _get_enhanced_svc():
    return get_enhanced_screening_service()


SUPPORTED_A_SHARE_INDUSTRY_SOURCES = ("tushare", "akshare", "baostock")
EMPTY_INDUSTRY_VALUES = {"", "-", "未知", "nan", "none", "null", "NaN", "None", "NULL"}


def _normalize_industry(value: Any) -> str:
    try:
        if value is None:
            return ""
        if isinstance(value, float) and (
            value != value or value in (float("inf"), float("-inf"))
        ):
            return ""
        text = str(value).strip()
        return "" if text in EMPTY_INDUSTRY_VALUES else text
    except Exception:
        return ""


def _normalize_source_order(sources: List[str]) -> List[str]:
    normalized: List[str] = []
    for source in sources:
        source_name = str(source or "").lower()
        if (
            source_name in SUPPORTED_A_SHARE_INDUSTRY_SOURCES
            and source_name not in normalized
        ):
            normalized.append(source_name)
    for source_name in SUPPORTED_A_SHARE_INDUSTRY_SOURCES:
        if source_name not in normalized:
            normalized.append(source_name)
    return normalized


def _build_industry_options_from_documents(
    documents: List[Dict[str, Any]], source_order: List[str]
) -> tuple[List[Dict[str, Any]], str]:
    for source in _normalize_source_order(source_order):
        counts: Counter[str] = Counter()
        for document in documents:
            if str(document.get("source") or "").lower() != source:
                continue
            industry = _normalize_industry(document.get("industry"))
            if industry:
                counts[industry] += 1

        if counts:
            industries = [
                {"value": industry, "label": industry, "count": count}
                for industry, count in sorted(
                    counts.items(), key=lambda item: (-item[1], item[0])
                )
            ]
            return industries, source

    return [], _normalize_source_order(source_order)[0]


async def _query_industry_options_by_source(
    source_order: List[str],
) -> tuple[List[Dict[str, Any]], str]:
    init_postgres = getattr(
        importlib.import_module("app.core.session"), "init_postgres"
    )
    get_session_factory = getattr(
        importlib.import_module("app.core.session"), "get_session_factory"
    )
    text = getattr(importlib.import_module("sqlalchemy"), "text")

    await init_postgres()
    async with get_session_factory()() as session:
        for source in _normalize_source_order(source_order):
            result = await session.execute(
                text(
                    """
                    select trim(industry) as industry, count(*) as count
                    from stock_basic_info
                    where source = :source
                      and industry is not null
                      and trim(industry) <> ''
                      and lower(trim(industry)) not in ('-', '未知', 'nan', 'none', 'null')
                    group by trim(industry)
                    order by count(*) desc, trim(industry) asc
                    """
                ),
                {"source": source},
            )
            rows = result.mappings().all()
            if rows:
                return (
                    [
                        {
                            "value": str(row["industry"]),
                            "label": str(row["industry"]),
                            "count": int(row["count"] or 0),
                        }
                        for row in rows
                    ],
                    source,
                )

    return [], _normalize_source_order(source_order)[0]


@router.get("/fields", response_model=FieldConfigResponse)
async def get_screening_fields(user: dict = Depends(get_current_user)):
    """
    获取筛选字段配置
    返回所有可用的筛选字段及其配置信息
    """
    try:
        # 字段分类
        categories = {
            "basic": ["code", "name", "industry", "area", "market"],
            "market_value": ["total_mv", "circ_mv"],
            "financial": ["pe", "pb", "pe_ttm", "pb_mrq", "roe"],
            "trading": ["turnover_rate", "volume_ratio"],
            "price": ["close", "pct_chg", "amount"],
            "technical": [
                "ma20",
                "rsi14",
                "kdj_k",
                "kdj_d",
                "kdj_j",
                "dif",
                "dea",
                "macd_hist",
            ],
        }

        return FieldConfigResponse(fields=BASIC_FIELDS_INFO, categories=categories)

    except Exception as e:
        logger.error(f"[get_screening_fields] 获取字段配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _convert_legacy_conditions_to_new_format(
    legacy_conditions: Dict[str, Any],
) -> List[ScreeningCondition]:
    """
    将传统格式的筛选条件转换为新格式

    传统格式示例:
    {
        "logic": "AND",
        "children": [
            {"field": "market_cap", "op": "between", "value": [5000000, 9007199254740991]}
        ]
    }

    新格式:
    [
        ScreeningCondition(field="total_mv", operator="between", value=[50, 90071992547])
    ]
    """
    conditions = []

    # 字段名映射（前端可能使用的旧字段名 -> 统一的后端字段名）
    field_mapping = {
        "market_cap": "total_mv",  # 市值（兼容旧字段名）
        "pe_ratio": "pe",  # 市盈率（兼容旧字段名）
        "pb_ratio": "pb",  # 市净率（兼容旧字段名）
        "turnover": "turnover_rate",  # 换手率（兼容旧字段名）
        "change_percent": "pct_chg",  # 涨跌幅（兼容旧字段名）
        "price": "close",  # 价格（兼容旧字段名）
    }

    # 操作符映射
    operator_mapping = {
        "between": "between",
        "gt": ">",
        "lt": "<",
        "gte": ">=",
        "lte": "<=",
        "eq": "==",
        "ne": "!=",
        "in": "in",
        "contains": "contains",
    }

    if isinstance(legacy_conditions, dict):
        children = legacy_conditions.get("children", [])

        for child in children:
            if isinstance(child, dict):
                field = child.get("field")
                op = child.get("op")
                value = child.get("value")

                if field and op and value is not None:
                    # 映射字段名
                    mapped_field = field_mapping.get(field, field)

                    # 映射操作符
                    mapped_op = operator_mapping.get(op, op)
                    if not mapped_field or not mapped_op:
                        continue

                    # 处理市值单位转换（前端传入的是万元，数据库存储的是亿元）
                    if mapped_field == "total_mv" and isinstance(value, list):
                        # 将万元转换为亿元
                        converted_value = [
                            v / 10000 for v in value if isinstance(v, (int, float))
                        ]
                        logger.info(
                            f"[screening] 市值单位转换: {value} 万元 -> {converted_value} 亿元"
                        )
                        value = converted_value
                    elif mapped_field == "total_mv" and isinstance(value, (int, float)):
                        value = value / 10000
                        logger.info(
                            f"[screening] 市值单位转换: {child.get('value')} 万元 -> {value} 亿元"
                        )

                    # 创建筛选条件
                    condition = ScreeningCondition(
                        field=str(mapped_field),
                        operator=cast(Any, mapped_op),
                        value=cast(Any, value),
                        field_type=None,
                    )
                    conditions.append(condition)

                    logger.info(
                        f"[screening] 转换条件: {field}({op}) -> {mapped_field}({mapped_op}), 值: {value}"
                    )

    return conditions


# 传统筛选接口（保持向后兼容，但使用增强服务）
@router.post("/run", response_model=ScreeningResponse)
async def run_screening(req: ScreeningRequest, user: dict = Depends(get_current_user)):
    try:
        logger.info(f"[screening] 请求条件: {req.conditions}")
        logger.info(
            f"[screening] 排序与分页: order_by={req.order_by}, limit={req.limit}, offset={req.offset}"
        )

        # 转换传统格式的条件为新格式
        conditions = _convert_legacy_conditions_to_new_format(req.conditions)
        logger.info(f"[screening] 转换后的条件: {conditions}")

        # 使用增强筛选服务
        result = await _get_enhanced_svc().screen_stocks(
            conditions=conditions,
            market=req.market,
            date=req.date,
            adj=req.adj,
            limit=req.limit,
            offset=req.offset,
            order_by=[
                {"field": o.field, "direction": o.direction}
                for o in (req.order_by or [])
            ],
            use_database_optimization=True,
        )

        logger.info(
            f"[screening] 筛选完成: total={result.get('total')}, "
            f"took={result.get('took_ms')}ms, optimization={result.get('optimization_used')}"
        )

        if result.get("items"):
            sample = result["items"][:3]
            logger.info(f"[screening] 返回样例(前3条): {sample}")

        return ScreeningResponse(total=result["total"], items=result["items"])

    except Exception as e:
        logger.error(f"[screening] 处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# 新的优化筛选接口
@router.post("/enhanced", response_model=NewScreeningResponse)
async def enhanced_screening(
    req: NewScreeningRequest, user: dict = Depends(get_current_user)
):
    """
    增强的股票筛选接口
    - 支持更丰富的筛选条件格式
    - 自动选择最优的筛选策略（数据库优化 vs 传统方法）
    - 提供详细的性能统计信息
    """
    try:
        logger.info(f"[enhanced_screening] 筛选条件: {len(req.conditions)}个")
        logger.info(
            f"[enhanced_screening] 排序与分页: order_by={req.order_by}, limit={req.limit}, offset={req.offset}"
        )

        # 执行增强筛选
        result = await _get_enhanced_svc().screen_stocks(
            conditions=req.conditions,
            market=req.market,
            date=req.date,
            adj=req.adj,
            limit=req.limit,
            offset=req.offset,
            order_by=req.order_by,
            use_database_optimization=req.use_database_optimization,
        )

        logger.info(
            f"[enhanced_screening] 筛选完成: total={result.get('total')}, "
            f"took={result.get('took_ms')}ms, optimization={result.get('optimization_used')}"
        )

        return NewScreeningResponse(
            total=result["total"],
            items=result["items"],
            took_ms=result.get("took_ms"),
            optimization_used=result.get("optimization_used"),
            source=result.get("source"),
        )

    except Exception as e:
        logger.error(f"[enhanced_screening] 筛选失败: {e}")
        raise HTTPException(status_code=500, detail=f"增强筛选失败: {str(e)}")


# 获取支持的字段信息
@router.get("/fields", response_model=List[SupportedFieldInfoResponse])
async def get_supported_fields(user: dict = Depends(get_current_user)):
    """获取所有支持的筛选字段信息"""
    try:
        fields = await _get_enhanced_svc().get_all_supported_fields()
        return fields
    except Exception as e:
        logger.error(f"[screening] 获取字段信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取字段信息失败: {str(e)}")


# 获取单个字段的详细信息
@router.get("/fields/{field_name}", response_model=SupportedFieldInfoResponse)
async def get_field_info(field_name: str, user: dict = Depends(get_current_user)):
    """获取指定字段的详细信息"""
    try:
        field_info = await _get_enhanced_svc().get_field_info(field_name)
        if not field_info:
            raise HTTPException(status_code=404, detail=f"字段 '{field_name}' 不存在")
        return field_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[screening] 获取字段信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取字段信息失败: {str(e)}")


# 验证筛选条件
@router.post("/validate", response_model=ConditionValidationResponse)
async def validate_conditions(
    conditions: List[ScreeningCondition], user: dict = Depends(get_current_user)
):
    """验证筛选条件的有效性"""
    try:
        validation_result = await _get_enhanced_svc().validate_conditions(conditions)
        return validation_result
    except Exception as e:
        logger.error(f"[screening] 验证条件失败: {e}")
        raise HTTPException(status_code=500, detail=f"验证条件失败: {str(e)}")


# 重复定义的旧端点移除（保留带日志的版本）


@router.get("/industries", response_model=IndustriesResponse)
async def get_industries(user: dict = Depends(get_current_user)):
    """
    获取数据库中所有可用的行业列表
    根据系统配置的数据源优先级，从优先级最高的数据源获取行业分类数据
    返回按股票数量排序的行业列表
    """
    try:
        UnifiedConfigManager = getattr(
            importlib.import_module("app.core.unified"), "UnifiedConfigManager"
        )

        # 🔥 获取数据源优先级配置（使用统一配置管理器的异步方法）
        config = UnifiedConfigManager()
        data_source_configs = await config.get_data_source_configs_async()

        # 提取启用的数据源，按优先级排序（已排序）
        enabled_sources = [
            ds.type.lower()
            for ds in data_source_configs
            if ds.enabled and ds.type.lower() in ["tushare", "akshare", "baostock"]
        ]

        enabled_sources = _normalize_source_order(enabled_sources)

        logger.info(f"[get_industries] 数据源优先级: {enabled_sources}")

        industries, preferred_source = await _query_industry_options_by_source(
            enabled_sources
        )

        logger.info(
            f"[get_industries] 从数据源 {preferred_source} 返回 {len(industries)} 个行业"
        )

        return {
            "industries": industries,
            "total": len(industries),
            "source": preferred_source,  # 🔥 返回数据来源
        }

    except Exception as e:
        logger.error(f"[get_industries] 获取行业列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
