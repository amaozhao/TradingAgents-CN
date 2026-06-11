from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .context import ResearchPrincipal, ToolExecutionContext
from .stage import stock_stage_title


def _direct_tool_content(result: dict[str, Any]) -> str:
    status = str(result.get("status") or "unknown")
    tool_name = str(result.get("tool") or "tool")
    if status == "config_required":
        return str(
            result.get("reason") or result.get("instruction") or "需要补充配置。"
        )
    if result.get("wait_timed_out"):
        task_id = result.get("task_id")
        message = result.get("message") or "任务仍在执行。"
        return f"{message} 任务 ID：{task_id}"
    if status in {"failed", "cancelled"}:
        task_id = result.get("task_id")
        message = (
            result.get("error_message")
            or result.get("message")
            or f"{tool_name} 已结束，状态：{status}。"
        )
        return f"{message}{f' 任务 ID：{task_id}' if task_id else ''}"
    if status == "completed":
        summary = str(result.get("summary") or "").strip()
        recommendation = str(result.get("recommendation") or "").strip()
        risk = str(result.get("risk_level") or "").strip()
        parts = [part for part in [summary, recommendation, risk] if part]
        if parts:
            return "\n".join(parts)
        return "工具已完成，报告链接已生成。"
    if result.get("task_id"):
        return f"{tool_name} 已提交，当前状态：{status}。任务 ID：{result['task_id']}"
    return str(result.get("message") or f"{tool_name} 已返回状态：{status}。")


class DirectToolMixin:
    async def _append_stock_stage_event(
        self,
        *,
        context: ToolExecutionContext,
        stage: str,
        status: str,
        progress: int,
        message: str,
        result: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        completed_at = now if status in {"completed", "failed", "skipped"} else None
        payload = {
            "attempt_id": context.request_id,
            "task_id": (result or {}).get("task_id"),
            "tool_name": "stock_analysis",
            "mode": "single",
            "stage": stage,
            "title": stock_stage_title(stage),
            "status": status,
            "started_at": now,
            "completed_at": completed_at,
            "raw_task_status": (result or {}).get("status"),
            "progress": progress,
            "message": message,
            "artifact_id": (result or {}).get("artifact_id"),
            "report_url": (result or {}).get("report_url"),
        }
        await self._append_event(
            session_id=str(context.session_id),
            user_id=context.principal.user_id,
            event_type="stock_analysis.stage",
            payload=payload,
        )

    async def _append_stock_stage_from_result(
        self, *, context: ToolExecutionContext, result: dict[str, Any]
    ) -> None:
        status = str(result.get("status") or "queued").lower()
        emitted_plan = False
        stage_events = result.get("stage_events")
        if isinstance(stage_events, list):
            for stage in stage_events:
                if not isinstance(stage, dict):
                    continue
                emitted_plan = True
                await self._append_stock_stage_event(
                    context=context,
                    stage=str(stage.get("stage") or "analysis_task"),
                    status=str(stage.get("status") or "completed"),
                    progress=int(stage.get("progress") or result.get("progress") or 0),
                    message=str(stage.get("message") or "Agent-native 单股阶段已更新。"),
                    result=result,
                )
        stage_plan = result.get("stage_plan")
        if not emitted_plan and isinstance(stage_plan, list):
            for stage in stage_plan:
                if not isinstance(stage, dict) or stage.get("stage") == "agent_summary":
                    continue
                planned_status = str(stage.get("status") or "pending")
                if planned_status not in {"pending", "skipped"}:
                    continue
                emitted_plan = True
                await self._append_stock_stage_event(
                    context=context,
                    stage=str(stage.get("stage") or "skipped"),
                    status=planned_status,
                    progress=int(result.get("progress") or 0),
                    message=str(
                        stage.get("reason") or "等待 Agent-native 单股阶段结果。"
                    ),
                    result=result,
                )
        skipped_stages = result.get("skipped_stages")
        if not emitted_plan and isinstance(skipped_stages, list):
            for stage in skipped_stages:
                if not isinstance(stage, dict):
                    continue
                await self._append_stock_stage_event(
                    context=context,
                    stage=str(stage.get("stage") or "skipped"),
                    status="skipped",
                    progress=int(result.get("progress") or 0),
                    message=str(stage.get("reason") or "该阶段已跳过。"),
                    result=result,
                )
        if result.get("wait_timed_out"):
            await self._append_stock_stage_event(
                context=context,
                stage="wait_bounded",
                status="running",
                progress=int(result.get("progress") or 0),
                message=str(result.get("message") or "单股分析仍在执行。"),
                result=result,
            )
            await self._append_event(
                session_id=str(context.session_id),
                user_id=context.principal.user_id,
                event_type="stock_analysis.timed_out",
                payload={
                    "attempt_id": context.request_id,
                    "task_id": result.get("task_id"),
                    "status": status,
                    "progress": result.get("progress", 0),
                },
            )
            return
        if status == "completed":
            await self._append_stock_stage_event(
                context=context,
                stage="agent_summary",
                status="completed",
                progress=100,
                message=str(result.get("message") or "单股分析已完成。"),
                result=result,
            )
            await self._append_event(
                session_id=str(context.session_id),
                user_id=context.principal.user_id,
                event_type="stock_analysis.completed",
                payload={
                    "attempt_id": context.request_id,
                    "task_id": result.get("task_id"),
                    "status": status,
                    "report_url": result.get("report_url"),
                },
            )
            return
        if status in {"failed", "cancelled"}:
            await self._append_stock_stage_event(
                context=context,
                stage="analysis_task",
                status="failed" if status == "failed" else "skipped",
                progress=int(result.get("progress") or 0),
                message=str(
                    result.get("message") or result.get("error_message") or status
                ),
                result=result,
            )
            await self._append_event(
                session_id=str(context.session_id),
                user_id=context.principal.user_id,
                event_type=f"stock_analysis.{status}",
                payload={
                    "attempt_id": context.request_id,
                    "task_id": result.get("task_id"),
                    "status": status,
                    "error": result.get("error_message"),
                },
            )
            return
        await self._append_stock_stage_event(
            context=context,
            stage="analysis_task",
            status="running",
            progress=int(result.get("progress") or 0),
            message=str(result.get("message") or "单股分析任务已提交。"),
            result=result,
        )

    async def run_direct_tool(
        self,
        *,
        principal: ResearchPrincipal,
        session_id: str,
        user_message: str,
        tool_name: str,
        tool_arguments: dict[str, Any],
        attempt_id: str | None = None,
        persist_user_message: bool = False,
    ) -> dict[str, Any]:
        if not await self.session_service.get_session(session_id, principal.user_id):
            raise PermissionError("research session is not available to this principal")
        if persist_user_message:
            await self._append_message(
                session_id=session_id,
                user_id=principal.user_id,
                role="user",
                content=user_message,
                linked_attempt_id=attempt_id,
            )
        context = ToolExecutionContext(
            principal=principal,
            session_id=session_id,
            request_id=attempt_id,
        )
        tool_result = await self._run_tool(
            tool_call={
                "id": f"direct-{tool_name}",
                "name": tool_name,
                "arguments": tool_arguments,
            },
            context=context,
        )
        linked_task_ids = [
            str(task_id)
            for task_id in [tool_result.get("task_id") or tool_result.get("job_id")]
            if task_id
        ]
        linked_artifact_ids = [
            str(artifact_id)
            for artifact_id in [tool_result.get("artifact_id")]
            if artifact_id
        ]
        final_content = _direct_tool_content(tool_result)
        assistant_message = await self._append_message(
            session_id=session_id,
            user_id=principal.user_id,
            role="assistant",
            content=final_content,
            metadata={
                "finish_reason": "direct_tool",
                "tool_name": tool_name,
                "tool_result": tool_result,
                "artifact_ids": linked_artifact_ids,
                "task_ids": linked_task_ids,
                "attempt_id": attempt_id,
            },
            linked_attempt_id=attempt_id,
        )
        await self._append_event(
            session_id=session_id,
            user_id=principal.user_id,
            event_type="message_completed",
            payload={
                "message_id": assistant_message["message_id"],
                "content": final_content,
                "artifact_ids": linked_artifact_ids,
                "task_ids": linked_task_ids,
                "attempt_id": attempt_id,
            },
        )
        if self.emit_terminal_event:
            await self._append_event(
                session_id=session_id,
                user_id=principal.user_id,
                event_type="task_completed",
                payload={
                    "finish_reason": "direct_tool",
                    "artifact_ids": linked_artifact_ids,
                    "task_ids": linked_task_ids,
                    "attempt_id": attempt_id,
                },
            )
        return {
            "content": final_content,
            "message_id": assistant_message["message_id"],
            "finish_reason": "direct_tool",
            "artifact_ids": linked_artifact_ids,
            "task_ids": linked_task_ids,
            "tool_result": tool_result,
        }
