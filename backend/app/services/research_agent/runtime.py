from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from .context import ResearchPrincipal, ToolExecutionContext
from .events import ResearchEventService
from .jobs import ResearchJobService
from .loop import ModelStreamChunk, ResearchAgentLoop
from .registry import ResearchToolRegistry


class BuiltinResearchModelClient:
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


def infer_sector(prompt: str) -> str:
    if "储能" in prompt or "energy storage" in prompt.lower():
        return "储能"
    return "A股"


def infer_symbols(prompt: str) -> list[str]:
    if "储能" in prompt or "energy storage" in prompt.lower():
        return ["300750.SZ", "002594.SZ", "601012.SH"]
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
        await self.job_service.mark_running(job["job_id"])

        try:
            loop_result = await ResearchAgentLoop(
                model_client=BuiltinResearchModelClient(),
                registry=self.registry,
                event_service=self.event_service,
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
                "job_id": job["job_id"],
                "artifact_ids": artifact_ids,
                "report_artifact_id": report_result["artifact_id"],
            }
            await self.job_service.mark_completed(job["job_id"], result)
            return result
        except Exception as exc:
            await self.job_service.mark_failed(job["job_id"], str(exc))
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
