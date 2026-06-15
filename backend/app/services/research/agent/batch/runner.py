from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from app.db.document import normalize_payload
from app.schemas.analysis import AnalysisParameters

from ..context import ToolExecutionContext
from . import context as batch_context
from .events import (
    build_batch_child_event,
    build_batch_completion_event,
    build_batch_progress_event,
    build_batch_stage_event,
)
from .repository import BatchRepository
from .state import (
    BatchChildState,
    BatchWorkflowState,
    aggregate_batch_status,
    build_batch_tool_result,
)

IdFactory = Callable[[], str]
BackgroundScheduler = Callable[[Awaitable[None]], None]
ChildRunner = Callable[
    [
        ToolExecutionContext,
        BatchWorkflowState,
        BatchChildState,
        batch_context.BatchRequestContext,
    ],
    Awaitable[dict[str, Any]],
]

logger = logging.getLogger(__name__)


def _schedule_background(awaitable: Awaitable[None]) -> None:
    asyncio.create_task(awaitable)


class BatchStockWorkflow:
    def __init__(
        self,
        *,
        tool_name: str,
        repository: BatchRepository | None = None,
        id_factory: IdFactory | None = None,
        child_runner: ChildRunner | None = None,
        background_scheduler: BackgroundScheduler | None = _schedule_background,
    ) -> None:
        self.tool_name = tool_name
        self.repository = repository or BatchRepository()
        self.id_factory = id_factory or _uuid
        self.child_runner = child_runner or run_batch_child_workflow
        self.background_scheduler = background_scheduler

    async def submit(
        self,
        context: ToolExecutionContext,
        payload: Mapping[str, object],
    ) -> dict[str, Any]:
        try:
            request = await batch_context.build_batch_request_context_async(
                context, payload
            )
        except batch_context.BatchConfigError as exc:
            return {
                "tool": self.tool_name,
                "mode": "batch",
                "status": "config_required",
                "accepted": False,
                "missing": exc.missing,
                "reason": exc.reason,
                "instruction": exc.instruction,
            }

        state = self._initial_state(request)
        await self._emit(
            context,
            build_batch_stage_event(
                state,
                attempt_id=context.request_id,
                stage="batch_prepare",
                status="completed",
                message="批量分析任务已创建。",
            ),
        )
        await self.repository.save_submitted_batch(state)
        await self._emit(
            context,
            build_batch_progress_event(state, attempt_id=context.request_id),
        )
        if self.background_scheduler is not None:
            self.background_scheduler(
                self._run_submitted_children(context, state, request)
            )
        result = build_batch_tool_result(state)
        result["tool"] = self.tool_name
        return result

    async def run_until_complete(
        self,
        context: ToolExecutionContext,
        payload: Mapping[str, object],
    ) -> dict[str, Any]:
        try:
            request = await batch_context.build_batch_request_context_async(
                context, payload
            )
        except batch_context.BatchConfigError as exc:
            return {
                "tool": self.tool_name,
                "mode": "batch",
                "status": "config_required",
                "accepted": False,
                "missing": exc.missing,
                "reason": exc.reason,
                "instruction": exc.instruction,
            }

        state = self._initial_state(request)
        await self._emit(
            context,
            build_batch_stage_event(
                state,
                attempt_id=context.request_id,
                stage="batch_prepare",
                status="completed",
                message="批量分析任务已创建。",
            ),
        )
        await self.repository.save_submitted_batch(state)
        await self._emit(
            context,
            build_batch_progress_event(state, attempt_id=context.request_id),
        )

        await self._run_children_until_complete(context, state, request)
        result = build_batch_tool_result(state)
        result["tool"] = self.tool_name
        return result

    def _initial_state(
        self,
        request: batch_context.BatchRequestContext,
    ) -> BatchWorkflowState:
        batch_id = self.id_factory()
        return BatchWorkflowState(
            batch_id=batch_id,
            user_id=request.user_id,
            title=request.title,
            description=request.description,
            status="pending",
            parameters=normalize_payload(request.parameters.model_dump()),
            children=[
                BatchChildState(
                    symbol=symbol,
                    stock_code=symbol,
                    task_id=self.id_factory(),
                )
                for symbol in request.symbols
            ],
        )

    async def _emit(
        self,
        context: ToolExecutionContext,
        event: dict[str, Any],
    ) -> None:
        if context.event_emitter is None:
            return
        await context.event_emitter(event)

    async def _run_child(
        self,
        context: ToolExecutionContext,
        state: BatchWorkflowState,
        child: BatchChildState,
        request: batch_context.BatchRequestContext,
    ) -> None:
        child.status = "processing"
        await self.repository.update_child(state.batch_id, state.user_id, child)
        await self._emit(
            context,
            build_batch_child_event(
                state,
                child,
                attempt_id=context.request_id,
                event_type="batch_analysis.child_started",
                message=f"开始分析 {child.symbol}。",
            ),
        )
        try:
            result = await self.child_runner(context, state, child, request)
        except Exception as exc:
            child.status = "failed"
            child.progress = 100
            child.error = str(exc) or exc.__class__.__name__
            await self.repository.update_child(state.batch_id, state.user_id, child)
            await self._emit(
                context,
                build_batch_child_event(
                    state,
                    child,
                    attempt_id=context.request_id,
                    event_type="batch_analysis.child_failed",
                    message=f"{child.symbol} 分析失败。",
                ),
            )
            await self._emit(
                context,
                build_batch_progress_event(state, attempt_id=context.request_id),
            )
            return

        child.status = "completed" if result.get("status") == "completed" else "failed"
        child.progress = 100
        child.analysis_id = _optional_string(result.get("analysis_id"))
        child.report_url = _optional_string(result.get("report_url"))
        if child.status == "failed":
            child.error = _optional_string(
                result.get("error_message")
                or result.get("error")
                or result.get("message")
            )
        await self.repository.update_child(state.batch_id, state.user_id, child)
        await self._emit(
            context,
            build_batch_child_event(
                state,
                child,
                attempt_id=context.request_id,
                event_type=(
                    "batch_analysis.child_completed"
                    if child.status == "completed"
                    else "batch_analysis.child_failed"
                ),
                message=(
                    f"{child.symbol} 分析完成。"
                    if child.status == "completed"
                    else f"{child.symbol} 分析失败。"
                ),
            ),
        )
        await self._emit(
            context,
            build_batch_progress_event(state, attempt_id=context.request_id),
        )

    async def _run_submitted_children(
        self,
        context: ToolExecutionContext,
        state: BatchWorkflowState,
        request: batch_context.BatchRequestContext,
    ) -> None:
        try:
            await self._run_children_until_complete(context, state, request)
        except Exception as exc:
            logger.exception("Batch workflow background execution failed: %s", exc)
            await self._mark_unfinished_children_failed(context, state, exc)

    async def _run_children_until_complete(
        self,
        context: ToolExecutionContext,
        state: BatchWorkflowState,
        request: batch_context.BatchRequestContext,
    ) -> None:
        semaphore = asyncio.Semaphore(request.max_concurrency)

        async def run_child(child: BatchChildState) -> None:
            async with semaphore:
                await self._run_child(context, state, child, request)

        await asyncio.gather(*(run_child(child) for child in state.children))
        await self.repository.update_batch_aggregate(state)
        await self._emit_completion(context, state)

    async def _mark_unfinished_children_failed(
        self,
        context: ToolExecutionContext,
        state: BatchWorkflowState,
        exc: Exception,
    ) -> None:
        message = str(exc) or exc.__class__.__name__
        for child in state.children:
            if child.status in {"completed", "failed", "cancelled"}:
                continue
            child.status = "failed"
            child.progress = 100
            child.error = message
            await self.repository.update_child(state.batch_id, state.user_id, child)
        await self.repository.update_batch_aggregate(state)
        await self._emit_completion(context, state)

    async def _emit_completion(
        self,
        context: ToolExecutionContext,
        state: BatchWorkflowState,
    ) -> None:
        aggregate = aggregate_batch_status(state)
        event_type = {
            "completed": "batch_analysis.completed",
            "partial": "batch_analysis.partial",
            "failed": "batch_analysis.failed",
            "cancelled": "batch_analysis.failed",
        }.get(aggregate.status)
        if event_type is None:
            return
        await self._emit(
            context,
            build_batch_completion_event(
                state,
                attempt_id=context.request_id,
                event_type=event_type,
                message="批量分析已完成。",
            ),
        )


def _uuid() -> str:
    return str(uuid.uuid4())


async def run_batch_child_workflow(
    context: ToolExecutionContext,
    state: BatchWorkflowState,
    child: BatchChildState,
    request: batch_context.BatchRequestContext,
) -> dict[str, Any]:
    from ..stock import run_agent_stock_workflow

    return await run_agent_stock_workflow(
        context,
        tool_name="stock_analysis",
        symbol=child.symbol,
        market_type=request.parameters.market_type,
        parameters=_copy_parameters(request.parameters),
        skipped_stages=[dict(stage) for stage in request.skipped_stages],
        stage_plan=[dict(stage) for stage in request.stage_plan],
        batch_id=state.batch_id,
    )


def _copy_parameters(parameters: AnalysisParameters) -> AnalysisParameters:
    return AnalysisParameters.model_validate(parameters.model_dump())


def _optional_string(raw: object) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None
