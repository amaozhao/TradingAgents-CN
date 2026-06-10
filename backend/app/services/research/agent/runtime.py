from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .context import ResearchPrincipal
from .events import ResearchEventService
from .jobs import ResearchAttemptService, ResearchJobService
from .loop import ResearchAgentLoop
from .provider.client import OpenAICompatibleModelClient
from .registry import ResearchToolRegistry
from .sessions import ResearchSessionService


class AgentIntent(str, Enum):
    CHAT = "chat"
    STOCK_RESEARCH = "stock_research"


@dataclass(frozen=True)
class IntentDecision:
    intent: AgentIntent
    reason: str


def classify_agent_intent(prompt: str) -> IntentDecision:
    normalized = prompt.strip().lower()
    if not normalized:
        return IntentDecision(AgentIntent.CHAT, "empty_prompt")

    actionable_prompt = extract_actionable_prompt(prompt)
    actionable_normalized = actionable_prompt.lower()

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
    return (
        "我是当前项目研究 Agent。当前后端可处理 A 股研究、Alpha Zoo、"
        "相关性矩阵、单股/批量分析、Research Goal、Swarm、文档/PDF 上传读取、"
        "Web 搜索/网页读取、Shadow Account、期权/形态/因子/回测、交易日志分析、"
        "交易连接器只读检查、live safety surface 和报告归档。"
    )


def _exception_message(exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        return message
    error_name = exc.__class__.__name__
    if "Timeout" in error_name:
        return f"外部模型或网络服务请求超时（{error_name}）"
    return error_name


class ResearchAgentRuntime:
    def __init__(
        self,
        *,
        registry: ResearchToolRegistry | None = None,
        event_service: ResearchEventService | None = None,
        job_service: ResearchJobService | None = None,
        attempt_service: ResearchAttemptService | None = None,
        session_service: ResearchSessionService | None = None,
    ) -> None:
        self._registry = registry
        self.event_service = event_service or ResearchEventService()
        self.job_service = job_service or ResearchJobService(event_service=self.event_service)
        self.attempt_service = attempt_service or ResearchAttemptService(
            event_service=self.event_service
        )
        self.session_service = session_service or ResearchSessionService()

    @property
    def registry(self) -> ResearchToolRegistry:
        if self._registry is None:
            self._registry = ResearchToolRegistry.default()
        return self._registry

    async def run_user_prompt(
        self,
        *,
        principal: ResearchPrincipal,
        session_id: str,
        user_message: str,
    ) -> dict[str, Any]:
        queued = await self.enqueue_user_prompt(
            principal=principal,
            session_id=session_id,
            user_message=user_message,
        )
        return await self.run_queued_user_prompt(
            principal=principal,
            session_id=session_id,
            user_message=user_message,
            job_id=queued["job_id"],
            attempt_id=queued["attempt_id"],
        )

    async def enqueue_user_prompt(
        self,
        *,
        principal: ResearchPrincipal,
        session_id: str,
        user_message: str,
    ) -> dict[str, Any]:
        attempt = await self.attempt_service.create(
            principal=principal,
            session_id=session_id,
            user_message=user_message,
        )
        job = await self.job_service.enqueue(
            principal=principal,
            task_type="agent_research",
            resource_id=session_id,
            payload={
                "session_id": session_id,
                "attempt_id": attempt["attempt_id"],
                "prompt": user_message,
            },
            session_id=session_id,
            attempt_id=attempt["attempt_id"],
        )
        await self.attempt_service.attach_job(
            attempt["attempt_id"], principal.user_id, job["job_id"]
        )
        message = await self.session_service.append_message(
            session_id=session_id,
            user_id=principal.user_id,
            role="user",
            content=user_message,
            metadata={"job_id": job["job_id"], "attempt_id": attempt["attempt_id"]},
            linked_attempt_id=attempt["attempt_id"],
        )
        if message is None:
            await self.attempt_service.mark_failed(
                attempt["attempt_id"], principal.user_id, "research session is unavailable"
            )
            await self.job_service.mark_failed(job["job_id"], "research session is unavailable")
            raise PermissionError("research session is not available to this principal")
        return {
            "status": "queued",
            "job_id": job["job_id"],
            "attempt_id": attempt["attempt_id"],
            "message_id": message["message_id"],
            "session_id": session_id,
        }

    async def run_queued_user_prompt(
        self,
        *,
        principal: ResearchPrincipal,
        session_id: str,
        user_message: str,
        job_id: str,
        attempt_id: str | None = None,
    ) -> dict[str, Any]:
        if attempt_id is None:
            job = await self.job_service.get(job_id, principal.user_id)
            attempt_id = job.get("attempt_id") if job else None

        if await self.job_service.is_cancelled(job_id):
            if attempt_id:
                await self.attempt_service.mark_cancelled(attempt_id, principal.user_id)
            return {"status": "cancelled", "job_id": job_id, "attempt_id": attempt_id}

        await self.job_service.mark_running(job_id)
        if attempt_id:
            await self.attempt_service.mark_started(attempt_id, principal.user_id)

        try:
            decision = classify_agent_intent(user_message)
            if decision.intent in {AgentIntent.CHAT, AgentIntent.STOCK_RESEARCH}:
                loop_result = await ResearchAgentLoop(
                    model_client=OpenAICompatibleModelClient(principal),
                    registry=self.registry,
                    event_service=self.event_service,
                    cancel_checker=lambda: self.job_service.is_cancelled(job_id),
                ).run(
                    principal=principal,
                    session_id=session_id,
                    user_message=user_message,
                    attempt_id=attempt_id,
                    persist_user_message=False,
                )
                result = {
                    **loop_result,
                    "status": "completed",
                    "job_id": job_id,
                    "intent": decision.intent.value,
                    "reason": decision.reason,
                    "artifact_ids": list(loop_result.get("artifact_ids", [])),
                }
                if await self.job_service.is_cancelled(job_id):
                    if attempt_id:
                        await self.attempt_service.mark_cancelled(
                            attempt_id, principal.user_id
                        )
                    return {
                        "status": "cancelled",
                        "job_id": job_id,
                        "attempt_id": attempt_id,
                    }
                await self.job_service.mark_completed(job_id, result)
                if attempt_id:
                    await self.attempt_service.mark_completed(
                        attempt_id, principal.user_id, result
                    )
                return result
        except Exception as exc:
            error_message = _exception_message(exc)
            if await self.job_service.is_cancelled(job_id):
                if attempt_id:
                    await self.attempt_service.mark_cancelled(
                        attempt_id, principal.user_id
                    )
                return {"status": "cancelled", "job_id": job_id, "attempt_id": attempt_id}
            await self.job_service.mark_failed(job_id, error_message)
            if attempt_id:
                await self.attempt_service.mark_failed(
                    attempt_id, principal.user_id, error_message
                )
            return {
                "status": "failed",
                "job_id": job_id,
                "attempt_id": attempt_id,
                "error": error_message,
            }

    async def list_attempts(
        self, *, session_id: str, user_id: str
    ) -> list[dict[str, Any]]:
        return await self.attempt_service.list_for_session(session_id, user_id)

    async def cancel_session(
        self, *, principal: ResearchPrincipal, session_id: str
    ) -> dict[str, Any]:
        cancelled_jobs = await self.job_service.cancel_active_for_session(
            session_id, principal.user_id
        )
        cancelled_attempt_ids: list[str] = []
        for job in cancelled_jobs:
            attempt_id = job.get("attempt_id")
            if not attempt_id:
                continue
            if await self.attempt_service.mark_cancelled(attempt_id, principal.user_id):
                cancelled_attempt_ids.append(attempt_id)
        if cancelled_jobs:
            await self.event_service.append(
                session_id=session_id,
                user_id=principal.user_id,
                event_type="task_failed",
                payload={
                    "status": "cancelled",
                    "job_ids": [job["job_id"] for job in cancelled_jobs],
                    "attempt_ids": cancelled_attempt_ids,
                },
            )
        return {
            "status": "cancelled" if cancelled_jobs else "idle",
            "session_id": session_id,
            "cancelled_job_ids": [job["job_id"] for job in cancelled_jobs],
            "cancelled_attempt_ids": cancelled_attempt_ids,
        }
