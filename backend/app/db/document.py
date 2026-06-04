from __future__ import annotations

import hashlib
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Mapping, cast

try:
    from bson import ObjectId
except Exception:  # pragma: no cover - bson is provided by pymongo in this project
    ObjectId = None


def legacy_id_from_document(document: Mapping[str, Any]) -> str:
    if "_id" in document and document["_id"] is not None:
        return str(document["_id"])
    if "legacy_id" in document and document["legacy_id"]:
        return str(document["legacy_id"])
    raise ValueError("document must include _id or legacy_id for PostgreSQL migration")


def normalize_payload(value: Any) -> Any:
    if _is_object_id(value):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): normalize_payload(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [normalize_payload(item) for item in value]
    return value


def map_stock_basic_info(document: Mapping[str, Any]) -> dict[str, Any]:
    source = _as_str(document.get("source") or document.get("data_source") or "")
    code = _as_str(document.get("code"))
    return {
        **_base_values(document, f"stock_basic_info:{source}:{code}"),
        "code": code,
        "source": source,
        "name": _as_optional_str(document.get("name")),
        "industry": _as_optional_str(document.get("industry")),
        "area": _as_optional_str(document.get("area")),
        "market": _as_optional_str(document.get("market")),
        "list_date": _as_date(document.get("list_date")),
        "total_mv": _as_decimal(document.get("total_mv")),
        "circ_mv": _as_decimal(document.get("circ_mv")),
        "pe": _as_decimal(document.get("pe")),
        "pb": _as_decimal(document.get("pb")),
        "pe_ttm": _as_decimal(document.get("pe_ttm")),
        "pb_mrq": _as_decimal(document.get("pb_mrq")),
    }


def map_market_quote(document: Mapping[str, Any]) -> dict[str, Any]:
    source = _as_str(document.get("source") or document.get("data_source") or "")
    code = _as_str(document.get("code"))
    return {
        **_base_values(document, f"market_quotes:{source}:{code}"),
        "code": code,
        "source": source,
        "trade_date": _as_date(document.get("trade_date")),
        "open": _as_decimal(document.get("open")),
        "high": _as_decimal(document.get("high")),
        "low": _as_decimal(document.get("low")),
        "close": _as_decimal(document.get("close")),
        "pre_close": _as_decimal(document.get("pre_close")),
        "pct_chg": _as_decimal(document.get("pct_chg")),
        "amount": _as_decimal(document.get("amount")),
        "volume": _as_decimal(document.get("volume") or document.get("vol")),
    }


def map_stock_daily_quote(document: Mapping[str, Any]) -> dict[str, Any]:
    symbol = _as_str(document.get("symbol") or document.get("code"))
    trade_date = _as_date(document.get("trade_date"))
    data_source = _as_str(document.get("data_source") or document.get("source") or "")
    period = _as_str(document.get("period") or "daily")
    fallback = f"stock_daily_quotes:{data_source}:{symbol}:{trade_date.isoformat() if trade_date else ''}:{period}"
    return {
        **_base_values(document, fallback),
        "symbol": symbol,
        "code": _as_optional_str(document.get("code") or symbol),
        "full_symbol": _as_optional_str(document.get("full_symbol")),
        "market": _as_optional_str(document.get("market")),
        "trade_date": trade_date,
        "period": period,
        "data_source": data_source,
        "open": _as_decimal(document.get("open")),
        "high": _as_decimal(document.get("high")),
        "low": _as_decimal(document.get("low")),
        "close": _as_decimal(document.get("close")),
        "pre_close": _as_decimal(document.get("pre_close")),
        "volume": _as_decimal(document.get("volume") or document.get("vol")),
        "amount": _as_decimal(document.get("amount") or document.get("turnover")),
        "change": _as_decimal(document.get("change")),
        "pct_chg": _as_decimal(document.get("pct_chg") or document.get("change_percent")),
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def map_stock_financial_data(document: Mapping[str, Any]) -> dict[str, Any]:
    data_source = _as_str(document.get("data_source") or document.get("source") or "")
    code = _as_str(document.get("code"))
    report_period = _as_str(document.get("report_period") or "")
    return {
        **_base_values(document, f"stock_financial_data:{data_source}:{code}:{report_period}"),
        "code": code,
        "data_source": data_source,
        "report_period": report_period,
        "roe": _as_decimal(document.get("roe")),
        "roa": _as_decimal(document.get("roa")),
        "netprofit_margin": _as_decimal(document.get("netprofit_margin")),
        "gross_margin": _as_decimal(document.get("gross_margin")),
    }


def map_stock_news(document: Mapping[str, Any]) -> dict[str, Any]:
    publish_time = _as_datetime(document.get("publish_time") or document.get("published_at") or document.get("created_at"))
    title = _as_optional_str(document.get("title"))
    url = _as_optional_str(document.get("url"))
    fallback = _stable_legacy_id(
        "stock_news",
        url,
        title,
        publish_time.isoformat() if publish_time else "",
    )
    return {
        **_base_values(document, fallback),
        "symbol": _as_optional_str(document.get("symbol") or document.get("code")),
        "market": _as_optional_str(document.get("market")),
        "title": title,
        "url": url,
        "data_source": _as_optional_str(document.get("data_source") or document.get("source")),
        "category": _as_optional_str(document.get("category")),
        "sentiment": _as_optional_str(document.get("sentiment")),
        "importance": _as_optional_str(document.get("importance")),
        "publish_time": publish_time,
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def map_analysis_task(document: Mapping[str, Any]) -> dict[str, Any]:
    task_id = _as_str(document.get("task_id") or document.get("id"))
    return {
        **_base_values(document, f"analysis_tasks:{task_id}"),
        "task_id": task_id,
        "user_id": _as_optional_str(document.get("user_id") or document.get("user")),
        "stock_symbol": _as_optional_str(document.get("stock_symbol") or document.get("symbol") or document.get("stock_code")),
        "status": _as_optional_str(document.get("status")),
        "progress": _as_int(document.get("progress")),
    }


def map_analysis_report(document: Mapping[str, Any]) -> dict[str, Any]:
    analysis_id = _as_str(document.get("analysis_id") or document.get("task_id") or document.get("id"))
    return {
        **_base_values(document, f"analysis_reports:{analysis_id}"),
        "analysis_id": analysis_id,
        "task_id": _as_optional_str(document.get("task_id")),
        "user_id": _as_optional_str(document.get("user_id") or document.get("user")),
        "stock_symbol": _as_optional_str(document.get("stock_symbol") or document.get("symbol") or document.get("stock_code")),
        "analysis_date": _as_date(document.get("analysis_date") or document.get("created_at")),
        "summary": _as_optional_str(document.get("summary") or document.get("final_decision") or document.get("recommendation")),
    }


def map_analysis_batch(document: Mapping[str, Any]) -> dict[str, Any]:
    batch_id = _as_str(document.get("batch_id") or document.get("id"))
    return {
        **_base_values(document, f"analysis_batches:{batch_id}"),
        "batch_id": batch_id,
        "user_id": _as_optional_str(document.get("user_id")),
        "status": _as_optional_str(document.get("status")),
        "total_tasks": _as_int(document.get("total_tasks")),
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def map_analysis_result(document: Mapping[str, Any]) -> dict[str, Any]:
    task_id = _as_optional_str(document.get("task_id") or document.get("analysis_id") or document.get("id"))
    stock_symbol = _as_optional_str(document.get("stock_symbol") or document.get("symbol") or document.get("stock_code"))
    fallback = f"analysis:{task_id or stock_symbol or _as_str(document.get('created_at'))}"
    return {
        **_base_values(document, fallback),
        "task_id": task_id,
        "user_id": _as_optional_str(document.get("user_id")),
        "stock_symbol": stock_symbol,
        "status": _as_optional_str(document.get("status")),
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def map_sync_status(document: Mapping[str, Any]) -> dict[str, Any]:
    job = _as_str(document.get("job") or document.get("job_id") or document.get("name"))
    success = _as_bool(document.get("success"))
    status = _as_optional_str(document.get("status"))
    if status is None and success is not None:
        status = "success" if success else "failed"
    started_at = _as_datetime(document.get("started_at"))
    finished_at = _as_datetime(document.get("finished_at") or document.get("last_sync_time"))
    return {
        **_base_values(document, f"sync_status:{job}"),
        "job": job,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration": _as_decimal(document.get("duration")),
    }


def map_scheduler_execution(document: Mapping[str, Any]) -> dict[str, Any]:
    job_id = _as_str(document.get("job_id") or document.get("job") or "")
    timestamp = _as_datetime(document.get("timestamp") or document.get("created_at") or document.get("started_at"))
    timestamp_key = timestamp.isoformat() if timestamp else ""
    return {
        **_base_values(document, f"scheduler_executions:{job_id}:{timestamp_key}"),
        "job_id": job_id,
        "status": _as_optional_str(document.get("status")),
        "progress": _as_int(document.get("progress")),
        "progress_message": _as_optional_str(document.get("progress_message") or document.get("message")),
        "timestamp": timestamp,
        "cancel_requested": _as_bool(document.get("cancel_requested")),
    }


def map_scheduler_history(document: Mapping[str, Any]) -> dict[str, Any]:
    job_id = _as_str(document.get("job_id") or document.get("job") or "")
    timestamp = _as_datetime(document.get("timestamp") or document.get("created_at"))
    timestamp_key = timestamp.isoformat() if timestamp else ""
    return {
        **_base_values(document, f"scheduler_history:{job_id}:{document.get('action') or ''}:{timestamp_key}"),
        "job_id": job_id,
        "action": _as_optional_str(document.get("action")),
        "status": _as_optional_str(document.get("status")),
        "timestamp": timestamp,
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def map_scheduler_metadata(document: Mapping[str, Any]) -> dict[str, Any]:
    job_id = _as_str(document.get("job_id") or document.get("job") or "")
    return {
        **_base_values(document, f"scheduler_metadata:{job_id}"),
        "job_id": job_id,
        "display_name": _as_optional_str(document.get("display_name")),
        "description": _as_optional_str(document.get("description")),
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def map_system_config_document(
    document: Mapping[str, Any],
    *,
    collection: str = "system_configs",
) -> dict[str, Any]:
    raw_key = (
        document.get("config_key")
        or document.get("key")
        or document.get("id")
        or _join_key(document.get("data_source_name"), document.get("market_category_id"))
        or document.get("name")
        or document.get("provider")
        or document.get("_id")
    )
    key = _as_str(raw_key)
    config_key = f"{collection}:{key}"
    return {
        **_base_values(document, config_key),
        "config_key": config_key,
        "config_type": collection,
        "enabled": _as_bool(document.get("enabled", document.get("is_active"))),
    }


def iter_user_favorite_documents(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    if "favorites" not in document or "stock_code" in document:
        return [dict(document)]

    user_id = _as_str(document.get("user_id"))
    parent_id = document.get("_id") or document.get("legacy_id")
    documents: list[dict[str, Any]] = []
    for favorite in document.get("favorites") or []:
        if not isinstance(favorite, Mapping):
            continue
        documents.append(
            {
                **favorite,
                "user_id": user_id,
                "parent_legacy_id": str(parent_id) if parent_id else None,
                "updated_at": document.get("updated_at"),
                "created_at": favorite.get("added_at") or document.get("created_at"),
            }
        )
    return documents


def map_user_favorite(document: Mapping[str, Any]) -> dict[str, Any]:
    user_id = _as_str(document.get("user_id"))
    stock_code = _as_str(document.get("stock_code"))
    return {
        **_base_values(document, f"user_favorites:{user_id}:{stock_code}"),
        "user_id": user_id,
        "stock_code": stock_code,
        "stock_name": _as_optional_str(document.get("stock_name")),
        "market": _as_optional_str(document.get("market")),
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def map_user_tag(document: Mapping[str, Any]) -> dict[str, Any]:
    user_id = _as_str(document.get("user_id"))
    tag_id = _as_optional_str(document.get("tag_id") or document.get("id") or document.get("_id"))
    name = _as_str(document.get("name"))
    return {
        **_base_values(document, f"user_tags:{user_id}:{tag_id or name}"),
        "user_id": user_id,
        "tag_id": tag_id,
        "name": name,
        "color": _as_optional_str(document.get("color")),
        "sort_order": _as_int(document.get("sort_order")),
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def map_paper_account(document: Mapping[str, Any]) -> dict[str, Any]:
    user_id = _as_str(document.get("user_id"))
    return {
        **_base_values(document, f"paper_accounts:{user_id}"),
        "user_id": user_id,
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def map_paper_position(document: Mapping[str, Any]) -> dict[str, Any]:
    user_id = _as_str(document.get("user_id"))
    code = _as_str(document.get("code"))
    return {
        **_base_values(document, f"paper_positions:{user_id}:{code}"),
        "user_id": user_id,
        "code": code,
        "market": _as_optional_str(document.get("market")),
        "currency": _as_optional_str(document.get("currency")),
        "quantity": _as_int(document.get("quantity")),
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def map_paper_order(document: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **_base_values(document, None),
        "user_id": _as_str(document.get("user_id")),
        "code": _as_optional_str(document.get("code")),
        "side": _as_optional_str(document.get("side")),
        "status": _as_optional_str(document.get("status")),
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def map_paper_trade(document: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **_base_values(document, None),
        "user_id": _as_str(document.get("user_id")),
        "code": _as_optional_str(document.get("code")),
        "side": _as_optional_str(document.get("side")),
        "timestamp": _as_datetime(document.get("timestamp")),
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def map_user_account(document: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **_base_values(document, f"user_accounts:{_as_str(document.get('username'))}"),
        "username": _as_str(document.get("username")),
        "email": _as_str(document.get("email")),
        "is_active": _as_bool(document.get("is_active")) if document.get("is_active") is not None else True,
        "is_admin": bool(_as_bool(document.get("is_admin"))),
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def map_user_session(document: Mapping[str, Any]) -> dict[str, Any]:
    session_id = _as_str(document.get("session_id") or document.get("token_id") or document.get("jti"))
    if not session_id:
        session_id = _stable_legacy_id(
            "user_sessions",
            document.get("user_id"),
            document.get("username"),
            document.get("created_at"),
            document.get("ip_address"),
        )
    return {
        **_base_values(document, f"user_sessions:{session_id}"),
        "session_id": session_id,
        "user_id": _as_optional_str(document.get("user_id")),
        "username": _as_optional_str(document.get("username")),
        "ip_address": _as_optional_str(document.get("ip_address") or document.get("ip")),
        "user_agent": _as_optional_str(document.get("user_agent")),
        "expires_at": _as_datetime(document.get("expires_at") or document.get("expires")),
        "last_activity_at": _as_datetime(
            document.get("last_activity_at")
            or document.get("last_activity")
            or document.get("updated_at")
        ),
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def map_login_attempt(document: Mapping[str, Any]) -> dict[str, Any]:
    timestamp = _as_datetime(document.get("timestamp") or document.get("created_at"))
    fallback = _stable_legacy_id(
        "login_attempts",
        document.get("username"),
        document.get("user_id"),
        document.get("ip_address") or document.get("ip"),
        timestamp.isoformat() if timestamp else "",
    )
    return {
        **_base_values(document, fallback),
        "user_id": _as_optional_str(document.get("user_id")),
        "username": _as_optional_str(document.get("username")),
        "ip_address": _as_optional_str(document.get("ip_address") or document.get("ip")),
        "success": _as_bool(document.get("success")),
        "reason": _as_optional_str(document.get("reason") or document.get("failure_reason")),
        "timestamp": timestamp,
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def map_operation_log(document: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **_base_values(document, None),
        "user_id": _as_optional_str(document.get("user_id")),
        "username": _as_optional_str(document.get("username")),
        "action_type": _as_optional_str(document.get("action_type")),
        "success": _as_bool(document.get("success")),
        "timestamp": _as_datetime(document.get("timestamp") or document.get("created_at")),
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def map_database_backup(document: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **_base_values(document, None),
        "name": _as_optional_str(document.get("name")),
        "filename": _as_optional_str(document.get("filename")),
        "created_by": _as_optional_str(document.get("created_by")),
        "backup_type": _as_optional_str(document.get("backup_type")),
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def map_notification(document: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **_base_values(document, None),
        "user_id": _as_str(document.get("user_id")),
        "type": _as_optional_str(document.get("type")),
        "status": _as_optional_str(document.get("status")),
        "severity": _as_optional_str(document.get("severity")),
        "title": _as_optional_str(document.get("title")),
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def map_token_usage(document: Mapping[str, Any]) -> dict[str, Any]:
    timestamp = _as_datetime(document.get("timestamp") or document.get("created_at"))
    fallback = _stable_legacy_id(
        "token_usage",
        document.get("provider"),
        document.get("model_name"),
        document.get("session_id"),
        timestamp.isoformat() if timestamp else "",
    )
    return {
        **_base_values(document, fallback),
        "provider": _as_optional_str(document.get("provider")),
        "model_name": _as_optional_str(document.get("model_name")),
        "session_id": _as_optional_str(document.get("session_id")),
        "analysis_type": _as_optional_str(document.get("analysis_type")),
        "stock_code": _as_optional_str(document.get("stock_code")),
        "timestamp": timestamp,
        "input_tokens": _as_int(document.get("input_tokens")),
        "output_tokens": _as_int(document.get("output_tokens")),
        "cost": _as_decimal(document.get("cost")),
        "currency": _as_optional_str(document.get("currency")),
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def map_internal_message(document: Mapping[str, Any]) -> dict[str, Any]:
    message_id = _as_str(document.get("message_id"))
    source = cast(Mapping[str, Any], document.get("source")) if isinstance(document.get("source"), Mapping) else {}
    related_data = cast(Mapping[str, Any], document.get("related_data")) if isinstance(document.get("related_data"), Mapping) else {}
    return {
        **_base_values(document, f"internal_messages:{message_id}"),
        "message_id": message_id,
        "symbol": _as_optional_str(document.get("symbol")),
        "message_type": _as_optional_str(document.get("message_type")),
        "category": _as_optional_str(document.get("category")),
        "source_type": _as_optional_str(source.get("type")),
        "department": _as_optional_str(source.get("department")),
        "importance": _as_optional_str(document.get("importance")),
        "access_level": _as_optional_str(document.get("access_level")),
        "rating": _as_optional_str(related_data.get("rating")),
        "confidence_level": _as_decimal(document.get("confidence_level")),
        "created_time": _as_datetime(document.get("created_time") or document.get("created_at")),
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def map_social_media_message(document: Mapping[str, Any]) -> dict[str, Any]:
    message_id = _as_str(document.get("message_id"))
    platform = _as_str(document.get("platform"))
    author = cast(Mapping[str, Any], document.get("author")) if isinstance(document.get("author"), Mapping) else {}
    engagement = cast(Mapping[str, Any], document.get("engagement")) if isinstance(document.get("engagement"), Mapping) else {}
    return {
        **_base_values(document, f"social_media_messages:{platform}:{message_id}"),
        "message_id": message_id,
        "platform": platform,
        "symbol": _as_optional_str(document.get("symbol")),
        "message_type": _as_optional_str(document.get("message_type")),
        "sentiment": _as_optional_str(document.get("sentiment")),
        "importance": _as_optional_str(document.get("importance")),
        "publish_time": _as_datetime(document.get("publish_time") or document.get("created_at")),
        "influence_score": _as_decimal(author.get("influence_score")),
        "engagement_rate": _as_decimal(engagement.get("engagement_rate")),
        "verified": _as_bool(author.get("verified")),
        "deleted": bool(_as_bool(document.get("deleted"))),
    }


def _base_values(document: Mapping[str, Any], fallback_legacy_id: str | None = None) -> dict[str, Any]:
    try:
        legacy_id = legacy_id_from_document(document)
    except ValueError:
        if not fallback_legacy_id:
            raise
        legacy_id = fallback_legacy_id

    return {
        "legacy_id": legacy_id,
        "payload": normalize_payload(document),
    }


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _as_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _as_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    text = str(value).strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _is_object_id(value: Any) -> bool:
    return ObjectId is not None and isinstance(value, ObjectId)


def _join_key(*values: Any) -> str:
    parts = [_as_str(value) for value in values if value not in {None, ""}]
    return ":".join(parts)


def _stable_legacy_id(prefix: str, *values: Any) -> str:
    raw = "|".join(_as_str(value) for value in values)
    return f"{prefix}:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"
