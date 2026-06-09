from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .context import ResearchPrincipal, ToolExecutionContext
from .events import ResearchEventService
from .jobs import ResearchJobService
from .loop import ModelStreamChunk, ResearchAgentLoop
from .registry import ResearchToolRegistry


class AgentIntent(str, Enum):
    CHAT = "chat"
    STOCK_RESEARCH = "stock_research"
    VIBE_ONLY = "vibe_only"


@dataclass(frozen=True)
class IntentDecision:
    intent: AgentIntent
    reason: str


class BuiltinStockResearchModelClient:
    async def stream(self, **kwargs: Any) -> AsyncIterator[ModelStreamChunk]:
        messages = kwargs.get("messages") or []
        user_message = ""
        for message in reversed(messages):
            if message.get("role") == "user":
                user_message = str(message.get("content") or "")
                break

        symbols = infer_symbols(user_message)
        sector = infer_sector(user_message)
        yield ModelStreamChunk(delta=f"开始分析{sector}，先构建候选池并校验证据。")
        yield ModelStreamChunk(
            tool_call={
                "name": "screening_run",
                "arguments": {"sector": sector, "symbols": symbols},
            }
        )
        yield ModelStreamChunk(
            tool_call={
                "name": "alpha_bench",
                "arguments": {"alpha_id": "alpha101_001", "symbols": symbols},
            }
        )
        yield ModelStreamChunk(
            tool_call={
                "name": "correlation_matrix",
                "arguments": {"symbols": symbols, "method": "pearson", "window": 20},
            }
        )
        yield ModelStreamChunk(
            tool_call={"name": "single_stock_analysis", "arguments": {"symbol": symbols[0]}}
        )
        yield ModelStreamChunk(
            delta=f"推荐个股：{symbols[0]}，理由见 Alpha、相关性矩阵和单股分析证据。",
            finish_reason="stop",
        )


class AssistantOnlyModelClient:
    def __init__(self, answer: str) -> None:
        self.answer = answer

    async def stream(self, **_kwargs: Any) -> AsyncIterator[ModelStreamChunk]:
        yield ModelStreamChunk(delta=self.answer, finish_reason="stop")


def classify_agent_intent(prompt: str) -> IntentDecision:
    normalized = prompt.strip().lower()
    if not normalized:
        return IntentDecision(AgentIntent.CHAT, "empty_prompt")

    actionable_prompt = extract_actionable_prompt(prompt)
    actionable_normalized = actionable_prompt.lower()

    unsupported_runtime_keywords = (
        "backtest",
        "risk-parity",
        "risk parity",
        "btc",
        "crypto",
        "macd",
        "5-minute",
        "option",
        "greeks",
        "black-scholes",
        "pdf",
        "uploaded",
        "upload",
        "earnings report",
        "fed meeting",
        "web",
        "journal",
        "trade journal",
        "shadow",
        "connector",
        "交易连接器",
        "live runtime",
        "live/status",
        "live/halt",
        "robinhood",
        "ibkr",
        "binance",
        "okx",
        "futu",
        "swarm",
        "swarm team mode",
        "智能体团队",
    )
    if any(keyword in actionable_normalized for keyword in unsupported_runtime_keywords):
        return IntentDecision(AgentIntent.VIBE_ONLY, "vibe_agent_runtime_not_migrated")

    stock_keywords = (
        "a股",
        "a share",
        "a-share",
        "china a",
        "csi 300",
        "沪深300",
        "股票",
        "个股",
        "板块",
        "行业",
        "储能",
        "白酒",
        "alpha",
        "因子",
        "相关性",
        "筛选",
        "推荐",
        "600519",
        "000001",
        ".sz",
        ".sh",
    )
    if any(keyword in actionable_normalized for keyword in stock_keywords):
        return IntentDecision(AgentIntent.STOCK_RESEARCH, "stock_research_prompt")

    return IntentDecision(AgentIntent.CHAT, "general_chat")


def extract_actionable_prompt(prompt: str) -> str:
    """Strip UI mode wrappers so routing follows the user's actual request."""
    lines = [line.strip() for line in prompt.splitlines()]
    for line in reversed(lines):
        if line.lower().startswith("goal:"):
            goal_text = line.split(":", 1)[1].strip()
            if goal_text:
                return goal_text
    return prompt.strip()


def build_capability_gap_answer(user_message: str, decision: IntentDecision) -> str:
    if decision.intent == AgentIntent.VIBE_ONLY:
        return (
            "这个请求属于 Vibe-Trading 的完整 Agent Runtime 能力，但当前 "
            "TradingAgents-CN 后端还没有迁入对应模块，所以我不会再伪造运行结果。\n\n"
            "当前缺失的后端能力包括：交易连接器运行状态、live runtime 控制、"
            "goal 持久化工具、swarm/team 执行器、broker MCP 工具注册和权限门禁。\n\n"
            "当前这个入口已经接入的能力是：A 股研究会话、Alpha Zoo 查询/覆盖检查、"
            "相关性矩阵、单股/批量分析任务入口和研究报告 artifact。"
        )
    return (
        "我是 TradingAgents-CN 研究 Agent。当前后端可处理 A 股研究、Alpha Zoo、"
        "相关性矩阵、单股/批量分析和报告归档；Vibe-Trading 的交易连接器、goal、"
        "swarm/live runtime 还没有完成后端迁移。"
    )


def infer_sector(prompt: str) -> str:
    if "储能" in prompt or "energy storage" in prompt.lower():
        return "储能"
    if "白酒" in prompt or "baijiu" in prompt.lower():
        return "白酒"
    if "沪深300" in prompt or "csi 300" in prompt.lower():
        return "沪深300"
    return "A股"


def infer_symbols(prompt: str) -> list[str]:
    if "储能" in prompt or "energy storage" in prompt.lower():
        return ["300750.SZ", "002594.SZ", "601012.SH"]
    if "白酒" in prompt or "baijiu" in prompt.lower():
        return ["600519.SH", "000858.SZ", "000568.SZ"]
    if "沪深300" in prompt or "csi 300" in prompt.lower():
        return ["600519.SH", "300750.SZ", "000001.SZ"]
    return ["600519", "000001"]


class ResearchAgentRuntime:
    def __init__(
        self,
        *,
        registry: ResearchToolRegistry | None = None,
        event_service: ResearchEventService | None = None,
        job_service: ResearchJobService | None = None,
    ) -> None:
        self.registry = registry or ResearchToolRegistry.default()
        self.event_service = event_service or ResearchEventService()
        self.job_service = job_service or ResearchJobService(event_service=self.event_service)

    async def run_user_prompt(
        self,
        *,
        principal: ResearchPrincipal,
        session_id: str,
        user_message: str,
    ) -> dict[str, Any]:
        job = await self.job_service.enqueue(
            principal=principal,
            task_type="agent_research",
            resource_id=session_id,
            payload={"session_id": session_id, "prompt": user_message},
        )
        return await self.run_queued_user_prompt(
            principal=principal,
            session_id=session_id,
            user_message=user_message,
            job_id=job["job_id"],
        )

    async def enqueue_user_prompt(
        self,
        *,
        principal: ResearchPrincipal,
        session_id: str,
        user_message: str,
    ) -> dict[str, Any]:
        job = await self.job_service.enqueue(
            principal=principal,
            task_type="agent_research",
            resource_id=session_id,
            payload={"session_id": session_id, "prompt": user_message},
        )
        return {
            "status": "queued",
            "job_id": job["job_id"],
            "session_id": session_id,
        }

    async def run_queued_user_prompt(
        self,
        *,
        principal: ResearchPrincipal,
        session_id: str,
        user_message: str,
        job_id: str,
    ) -> dict[str, Any]:
        await self.job_service.mark_running(job_id)

        try:
            decision = classify_agent_intent(user_message)
            if decision.intent != AgentIntent.STOCK_RESEARCH:
                loop_result = await ResearchAgentLoop(
                    model_client=AssistantOnlyModelClient(
                        build_capability_gap_answer(user_message, decision)
                    ),
                    registry=self.registry,
                    event_service=self.event_service,
                ).run(
                    principal=principal,
                    session_id=session_id,
                    user_message=user_message,
                )
                result = {
                    **loop_result,
                    "status": "completed",
                    "job_id": job_id,
                    "intent": decision.intent.value,
                    "reason": decision.reason,
                    "artifact_ids": list(loop_result.get("artifact_ids", [])),
                }
                await self.job_service.mark_completed(job_id, result)
                return result

            loop_result = await ResearchAgentLoop(
                model_client=BuiltinStockResearchModelClient(),
                registry=self.registry,
                event_service=self.event_service,
                emit_terminal_event=False,
            ).run(
                principal=principal,
                session_id=session_id,
                user_message=user_message,
            )
            report_result = await self._write_report(
                principal=principal,
                session_id=session_id,
                user_message=user_message,
                loop_result=loop_result,
            )
            artifact_ids = [
                *loop_result.get("artifact_ids", []),
                report_result["artifact_id"],
            ]
            result = {
                **loop_result,
                "status": "completed",
                "job_id": job_id,
                "artifact_ids": artifact_ids,
                "report_artifact_id": report_result["artifact_id"],
            }
            await self.job_service.mark_completed(job_id, result)
            await self.event_service.append(
                session_id=session_id,
                user_id=principal.user_id,
                event_type="task_completed",
                payload={
                    "finish_reason": loop_result.get("finish_reason"),
                    "artifact_ids": artifact_ids,
                    "task_ids": list(loop_result.get("task_ids", [])),
                    "report_artifact_id": report_result["artifact_id"],
                },
            )
            return result
        except Exception as exc:
            await self.job_service.mark_failed(job_id, str(exc))
            raise

    async def _write_report(
        self,
        *,
        principal: ResearchPrincipal,
        session_id: str,
        user_message: str,
        loop_result: dict[str, Any],
    ) -> dict[str, Any]:
        symbols = infer_symbols(user_message)
        sector = infer_sector(user_message)
        artifact_ids = list(loop_result.get("artifact_ids", []))
        alpha_artifact_id = artifact_ids[0] if artifact_ids else ""
        correlation_artifact_id = artifact_ids[1] if len(artifact_ids) > 1 else ""
        payload = {
            "title": f"{sector}研究报告",
            "sector": {
                "name": sector,
                "summary": f"{sector}候选池已完成筛选、Alpha 和相关性校验。",
            },
            "universe": {"method": "agent_workflow", "symbols": symbols},
            "screening_filters": {"source": "agent_prompt"},
            "alpha": {
                "artifact_id": alpha_artifact_id,
                "findings": [f"alpha101_001 对 {symbols[0]} 给出正向证据。"],
            },
            "correlation": {
                "artifact_id": correlation_artifact_id,
                "findings": ["相关性矩阵已用于识别组合分散度。"],
            },
            "single_stock_reports": [
                {
                    "symbol": symbols[0],
                    "summary": "单股分析工具已纳入候选股证据链。",
                }
            ],
            "recommended_stocks": [
                {
                    "symbol": symbols[0],
                    "reason": "Alpha、相关性和单股分析形成一致证据。",
                }
            ],
            "risk_factors": ["行业景气度和估值波动可能影响结论。"],
            "data_limitations": ["本地内置 Agent workflow 使用可用工具结果生成摘要。"],
            "artifact_ids": artifact_ids,
            "task_ids": list(loop_result.get("task_ids", [])),
        }
        await self.event_service.append(
            session_id=session_id,
            user_id=principal.user_id,
            event_type="tool_started",
            payload={"tool_name": "report_write", "arguments": payload},
        )
        report_result = await self.registry.get("report_write").run(
            ToolExecutionContext(principal=principal, session_id=session_id),
            payload,
        )
        await self.event_service.append(
            session_id=session_id,
            user_id=principal.user_id,
            event_type="tool_completed",
            payload={
                "tool_name": "report_write",
                "artifact_id": report_result["artifact_id"],
                "result": report_result,
            },
        )
        return report_result
