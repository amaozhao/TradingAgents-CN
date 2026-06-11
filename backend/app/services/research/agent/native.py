from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta
from typing import Any

from app.core.database import get_postgres_db
from app.services.market.news import get_news_data_service
from app.services.market.news.models import NewsQueryParams

from .context import ToolExecutionContext
from .models import now_utc
from .tools.market.series import lookup_market_snapshot, summarize_returns


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _percent(value: Any) -> str:
    number = _safe_float(value)
    if number is None:
        return "无数据"
    return f"{number * 100:.2f}%"


def _line(label: str, value: Any) -> str:
    if value is None or value == "":
        value = "无数据"
    return f"- {label}: {value}"


def _stage(
    stage: str,
    status: str,
    progress: int,
    message: str,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": status,
        "progress": progress,
        "message": message,
    }


def _quote_value(quote: dict[str, Any] | None, *keys: str) -> Any:
    if not isinstance(quote, dict):
        return None
    for key in keys:
        value = quote.get(key)
        if value is not None and value != "":
            return value
    return None


def _basic_value(info: dict[str, Any] | None, *keys: str) -> Any:
    if not isinstance(info, dict):
        return None
    for key in keys:
        value = info.get(key)
        if value is not None and value != "":
            return value
    return None


def _news_title(item: dict[str, Any]) -> str:
    title = str(item.get("title") or item.get("headline") or "").strip()
    source = str(item.get("source") or item.get("data_source") or "").strip()
    time_text = str(item.get("publish_time") or item.get("published_at") or "").strip()
    parts = [part for part in [title, source, time_text] if part]
    return " | ".join(parts)


async def _load_news(symbol: str, market_type: str, limit: int = 8) -> list[dict[str, Any]]:
    if market_type != "A股":
        return []
    service = await get_news_data_service()
    params = NewsQueryParams(
        symbol=symbol,
        start_time=datetime.utcnow() - timedelta(days=14),
        limit=limit,
        sort_by="publish_time",
        sort_order=-1,
    )
    return await service.query_news(params)


def _market_report(snapshot: dict[str, Any], metrics: dict[str, Any]) -> str:
    quote = snapshot.get("quote") if isinstance(snapshot.get("quote"), dict) else {}
    history = snapshot.get("history") if isinstance(snapshot.get("history"), dict) else {}
    lines = [
        "# 市场分析",
        _line("数据状态", snapshot.get("status")),
        _line("行情来源", history.get("source")),
        _line("观测数", history.get("observations")),
        _line("最新收盘", _quote_value(quote, "close", "price", "last", "current")),
        _line("区间收益", _percent(metrics.get("total_return"))),
        _line("年化波动", _percent(metrics.get("annual_volatility"))),
        _line("最大回撤", _percent(metrics.get("max_drawdown"))),
        _line("胜率", _percent(metrics.get("win_rate"))),
        _line("夏普", metrics.get("sharpe")),
    ]
    reason = snapshot.get("reason") or history.get("reason")
    if reason:
        lines.append(_line("数据限制", reason))
    return "\n".join(lines)


def _fundamentals_report(snapshot: dict[str, Any]) -> str:
    info = snapshot.get("basic_info") if isinstance(snapshot.get("basic_info"), dict) else {}
    lines = [
        "# 基本面分析",
        _line("名称", _basic_value(info, "name", "stock_name", "short_name")),
        _line("行业", _basic_value(info, "industry", "sector")),
        _line("地区", _basic_value(info, "area", "region")),
        _line("上市日期", _basic_value(info, "list_date", "listing_date")),
        _line("总市值", _basic_value(info, "total_mv", "market_cap")),
        _line("流通市值", _basic_value(info, "circ_mv", "float_market_cap")),
        _line("市盈率", _basic_value(info, "pe", "pe_ttm")),
        _line("市净率", _basic_value(info, "pb", "pb_mrq")),
    ]
    if not info:
        lines.append("- 数据限制: 当前本地缓存或免费数据源没有返回基本面字段。")
    return "\n".join(lines)


def _news_report(news: list[dict[str, Any]], include_sentiment: bool) -> str:
    lines = ["# 新闻分析"]
    if not news:
        lines.append("- 最近 14 天未查询到本地新闻缓存。")
        lines.append("- 数据限制: native workflow 不伪造新闻结论；缺数据时显式披露。")
        return "\n".join(lines)
    for item in news[:8]:
        lines.append(f"- {_news_title(item)}")
    if include_sentiment:
        sentiments = [str(item.get("sentiment") or "").lower() for item in news]
        positive = len([item for item in sentiments if "positive" in item or item == "正面"])
        negative = len([item for item in sentiments if "negative" in item or item == "负面"])
        lines.append(_line("情绪统计", f"正面 {positive} 条，负面 {negative} 条"))
    return "\n".join(lines)


def _sentiment_report(news: list[dict[str, Any]]) -> str:
    if not news:
        return "# 情绪分析\n- 未查询到可用于情绪分析的新闻或社媒数据。"
    labels = [str(item.get("sentiment") or "neutral").lower() for item in news]
    positive = len([label for label in labels if "positive" in label or label == "正面"])
    negative = len([label for label in labels if "negative" in label or label == "负面"])
    neutral = len(labels) - positive - negative
    return "\n".join(
        [
            "# 情绪分析",
            _line("样本数", len(labels)),
            _line("正面", positive),
            _line("中性", neutral),
            _line("负面", negative),
        ]
    )


def _decision(
    snapshot: dict[str, Any],
    metrics: dict[str, Any],
    selected_analysts: list[str],
    include_risk: bool,
) -> dict[str, Any]:
    score = 0.5
    total_return = _safe_float(metrics.get("total_return"))
    drawdown = _safe_float(metrics.get("max_drawdown"))
    volatility = _safe_float(metrics.get("annual_volatility"))
    if total_return is not None:
        score += max(min(total_return, 0.2), -0.2)
    if drawdown is not None:
        score += max(drawdown, -0.2) / 2
    if volatility is not None and volatility > 0.45:
        score -= 0.08
    score = max(0.05, min(score, 0.95))
    if score >= 0.62:
        action = "买入"
    elif score <= 0.38:
        action = "卖出"
    else:
        action = "持有"
    risk_score = max(0.1, min((volatility or 0.25) + abs(drawdown or 0), 0.95))
    return {
        "action": action,
        "confidence": round(score, 3),
        "risk_score": round(risk_score, 3) if include_risk else None,
        "target_price": None,
        "reasoning": (
            "Agent-native workflow 根据当前项目可取得的行情、基本面缓存、新闻缓存"
            f"和已选择分析师 {selected_analysts} 生成结论；未使用原 LangGraph DAG。"
        ),
    }


def _risk_level(decision: dict[str, Any]) -> str:
    risk = _safe_float(decision.get("risk_score"))
    if risk is None:
        return "未评估"
    if risk >= 0.65:
        return "高"
    if risk >= 0.35:
        return "中"
    return "低"


def _summary(symbol: str, decision: dict[str, Any], metrics: dict[str, Any]) -> str:
    return (
        f"{symbol} Agent-native 单股分析完成。"
        f"建议：{decision['action']}；置信度：{decision['confidence']}；"
        f"区间收益：{_percent(metrics.get('total_return'))}；"
        f"最大回撤：{_percent(metrics.get('max_drawdown'))}。"
    )


async def _write_native_task(
    *,
    task_id: str,
    user_id: str,
    symbol: str,
    market_type: str,
    parameters: dict[str, Any],
    status: str,
    progress: int,
    message: str,
) -> None:
    now = now_utc()
    await get_postgres_db().analysis_tasks.update_one(
        {"task_id": task_id},
        {
            "$set": {
                "task_id": task_id,
                "user_id": user_id,
                "stock_code": symbol,
                "stock_symbol": symbol,
                "market_type": market_type,
                "status": status,
                "progress": progress,
                "message": message,
                "current_step": message,
                "parameters": parameters,
                "updated_at": now,
                "completed_at": now if status in {"completed", "failed"} else None,
            },
            "$setOnInsert": {"created_at": now, "source": "agent_native"},
        },
        upsert=True,
    )


async def run_native_stock_workflow(
    context: ToolExecutionContext,
    *,
    tool_name: str,
    symbol: str,
    market_type: str,
    parameters: Any,
    skipped_stages: list[dict[str, str]],
    stage_plan: list[dict[str, str]],
) -> dict[str, Any]:
    task_id = str(uuid.uuid4())
    analysis_id = str(uuid.uuid4())
    params = parameters.model_dump(mode="json") if hasattr(parameters, "model_dump") else {}
    selected_analysts = list(params.get("selected_analysts") or [])
    stage_events = [_stage("validate_input", "completed", 8, "单股分析参数已校验。")]

    await _write_native_task(
        task_id=task_id,
        user_id=context.principal.user_id,
        symbol=symbol,
        market_type=market_type,
        parameters=params,
        status="processing",
        progress=10,
        message="Agent-native workflow 正在获取行情数据。",
    )

    snapshot = await lookup_market_snapshot(
        symbol,
        end_date=params.get("analysis_date"),
        limit=252,
    )
    history = snapshot.get("history") if isinstance(snapshot.get("history"), dict) else {}
    metrics = summarize_returns(history.get("returns") or [])
    stage_events.append(_stage("market_analysis", "completed", 35, "市场分析完成。"))

    reports: dict[str, str] = {"market_report": _market_report(snapshot, metrics)}
    if "fundamentals" in selected_analysts:
        reports["fundamentals_report"] = _fundamentals_report(snapshot)
        stage_events.append(_stage("fundamentals_analysis", "completed", 55, "基本面分析完成。"))

    news: list[dict[str, Any]] = []
    if "news" in selected_analysts:
        news = await _load_news(symbol, market_type)
        reports["news_report"] = _news_report(news, bool(params.get("include_sentiment", True)))
        stage_events.append(_stage("news_analysis", "completed", 68, "新闻分析完成。"))

    if params.get("include_sentiment") and ("news" in selected_analysts or "social" in selected_analysts):
        reports["sentiment_report"] = _sentiment_report(news)
        stage_events.append(_stage("sentiment_analysis", "completed", 75, "情绪分析完成。"))

    for skipped in skipped_stages:
        stage_events.append(
            _stage(skipped["stage"], "skipped", 75, skipped.get("reason", "该阶段已跳过。"))
        )

    decision = _decision(snapshot, metrics, selected_analysts, bool(params.get("include_risk", True)))
    reports["final_trade_decision"] = "\n".join(
        [
            "# 最终交易决策",
            _line("执行路径", "Agent-native workflow"),
            _line("建议", decision["action"]),
            _line("置信度", decision["confidence"]),
            _line("风险评分", decision.get("risk_score")),
            _line("依据", decision["reasoning"]),
        ]
    )
    if params.get("include_risk", True):
        stage_events.append(_stage("risk_review", "completed", 88, "风险评估完成。"))
    stage_events.append(_stage("agent_summary", "completed", 100, "Agent-native 报告已生成。"))

    summary = _summary(symbol, decision, metrics)
    report = {
        "analysis_id": analysis_id,
        "task_id": task_id,
        "user_id": context.principal.user_id,
        "stock_code": symbol,
        "stock_symbol": symbol,
        "market_type": market_type,
        "analysis_date": params.get("analysis_date"),
        "summary": summary,
        "recommendation": f"投资建议：{decision['action']}。决策依据：{decision['reasoning']}",
        "confidence_score": decision["confidence"],
        "risk_level": _risk_level(decision),
        "key_points": [
            f"区间收益：{_percent(metrics.get('total_return'))}",
            f"最大回撤：{_percent(metrics.get('max_drawdown'))}",
            f"行情状态：{snapshot.get('status')}",
        ],
        "reports": reports,
        "decision": decision,
        "state": {
            "snapshot": snapshot,
            "metrics": metrics,
            "news_count": len(news),
            "stage_events": stage_events,
        },
        "status": "completed",
        "source": "agent_native",
        "analysts": selected_analysts,
        "research_depth": params.get("research_depth"),
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }
    await get_postgres_db().analysis_reports.insert_one(report)
    await _write_native_task(
        task_id=task_id,
        user_id=context.principal.user_id,
        symbol=symbol,
        market_type=market_type,
        parameters=params,
        status="completed",
        progress=100,
        message="Agent-native 单股分析已完成。",
    )

    return {
        "tool": tool_name,
        "mode": "single",
        "status": "completed",
        "accepted": True,
        "stage": "agent_summary",
        "wait_status": "completed",
        "progress": 100,
        "task_id": task_id,
        "analysis_id": analysis_id,
        "symbol": symbol,
        "market_type": market_type,
        "analysis_date": params.get("analysis_date"),
        "research_depth": params.get("research_depth"),
        "selected_analysts": selected_analysts,
        "include_sentiment": params.get("include_sentiment"),
        "include_risk": params.get("include_risk"),
        "skipped_stages": skipped_stages,
        "stage_plan": stage_plan,
        "stage_events": stage_events,
        "summary": summary,
        "recommendation": report["recommendation"],
        "risk_level": report["risk_level"],
        "decision": decision,
        "report": report,
        "links": {
            "task": f"/tasks?task_id={task_id}",
            "report": f"/reports/view/{task_id}",
        },
        "task_url": f"/tasks?task_id={task_id}",
        "report_url": f"/reports/view/{task_id}",
        "message": "Agent-native 单股分析已完成，未调用原 LangGraph DAG。",
    }
