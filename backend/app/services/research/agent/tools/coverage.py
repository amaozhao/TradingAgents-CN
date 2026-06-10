from __future__ import annotations

from typing import Any

from app.services.research.agent.jobs import ResearchJobService
from app.services.research.agent.sessions import ResearchSessionService

from ..context import ToolExecutionContext
from ..permissions import (
    ADMIN_UNSAFE_TOOL,
    BACKGROUND_JOB_READ,
    COMPACT_CONTEXT,
    DISABLED_RESEARCH_TOOL,
    SESSION_SEARCH,
)
from ..registry import ResearchTool


def _disabled_handler(
    *,
    source_tool_class: str,
    status: str = "disabled_config_required",
    reason: str,
    required_capability: str | None = None,
):
    async def handler(_context: ToolExecutionContext, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "tool": _tool_name_from_source(source_tool_class),
            "source_tool_class": source_tool_class,
            "status": status,
            "accepted": False,
            "reason": reason,
            "required_capability": required_capability,
            "payload": payload,
        }

    return handler


def _tool_name_from_source(source_tool_class: str) -> str:
    name = source_tool_class.removesuffix("Tool")
    out = []
    for index, char in enumerate(name):
        if char.isupper() and index:
            out.append("_")
        out.append(char.lower())
    return "".join(out)


async def _compact_context(
    _context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    return {
        "tool": "compact_context",
        "status": "completed",
        "accepted": True,
        "message": "Context compaction is automatic in the current Agent loop; future provider calls will use compacted history when needed.",
        "payload": payload,
    }


async def _session_search(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    query = str(payload.get("query") or "").strip().lower()
    if not query:
        raise ValueError("query is required")

    session_service = ResearchSessionService()
    matches: list[dict[str, Any]] = []
    for session in await session_service.list_sessions(context.principal.user_id):
        session_id = session["session_id"]
        title = str(session.get("title") or "")
        title_match = query in title.lower()
        message_matches: list[dict[str, Any]] = []
        for message in await session_service.list_messages(
            session_id, context.principal.user_id
        ):
            content = str(message.get("content") or "")
            if query in content.lower():
                message_matches.append(
                    {
                        "message_id": message.get("message_id"),
                        "role": message.get("role"),
                        "preview": content[:240],
                        "created_at": message.get("created_at"),
                    }
                )
        if title_match or message_matches:
            matches.append(
                {
                    "session_id": session_id,
                    "title": title,
                    "title_match": title_match,
                    "messages": message_matches[:5],
                }
            )
    return {"tool": "session_search", "status": "completed", "matches": matches[:10]}


async def _check_background(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    job_id = str(payload.get("job_id") or "").strip()
    if not job_id:
        raise ValueError("job_id is required")
    job = await ResearchJobService().get(job_id, context.principal.user_id)
    if not job:
        return {"tool": "check_background", "status": "not_found", "job_id": job_id}
    return {
        "tool": "check_background",
        "status": "completed",
        "job": {
            "job_id": job.get("job_id"),
            "session_id": job.get("session_id"),
            "attempt_id": job.get("attempt_id"),
            "task_type": job.get("task_type"),
            "resource_id": job.get("resource_id"),
            "status": job.get("status"),
            "result": job.get("result"),
            "error": job.get("error"),
            "created_at": job.get("created_at"),
            "updated_at": job.get("updated_at"),
        },
    }


def _disabled_tool(
    *,
    name: str,
    source_tool_class: str,
    description: str,
    permission: str = DISABLED_RESEARCH_TOOL,
    reason: str,
    required_capability: str | None = None,
) -> ResearchTool:
    return ResearchTool(
        name=name,
        description=description,
        permission=permission,
        schema={"type": "object", "additionalProperties": True},
        handler=_disabled_handler(
            source_tool_class=source_tool_class,
            reason=reason,
            required_capability=required_capability,
        ),
    )


def coverage_tools() -> list[ResearchTool]:
    return [
        ResearchTool(
            name="compact_context",
            description="Request context compaction; current loop compacts automatically and records compact events.",
            permission=COMPACT_CONTEXT,
            schema={"type": "object", "additionalProperties": True},
            handler=_compact_context,
        ),
        ResearchTool(
            name="session_search",
            description="Search the current user's research sessions and messages.",
            permission=SESSION_SEARCH,
            schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            handler=_session_search,
        ),
        ResearchTool(
            name="check_background",
            description="Check an owner-scoped background research job.",
            permission=BACKGROUND_JOB_READ,
            schema={
                "type": "object",
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
            },
            handler=_check_background,
        ),
        _disabled_tool(
            name="factor_analysis",
            source_tool_class="FactorAnalysisTool",
            description="Factor analysis is not yet wired to current-project services.",
            reason="Factor analysis service migration is pending.",
        ),
        _disabled_tool(
            name="backtest",
            source_tool_class="BacktestTool",
            description="Backtest execution is not yet wired to current-project run artifacts.",
            reason="Backtest run/artifact migration is pending.",
        ),
        _disabled_tool(
            name="background_run",
            source_tool_class="BackgroundRunTool",
            description="Generic background execution is disabled until task allowlists are migrated.",
            reason="Arbitrary background task dispatch is not enabled.",
            required_capability="background_task_allowlist",
        ),
        _disabled_tool(
            name="remember",
            source_tool_class="RememberTool",
            description="Persistent cross-session memory is not yet migrated.",
            reason="Agent memory storage and retention policy are pending.",
        ),
        _disabled_tool(
            name="create_hypothesis",
            source_tool_class="CreateHypothesisTool",
            description="Hypothesis ledger creation is not yet migrated.",
            reason="Hypothesis service migration is pending.",
        ),
        _disabled_tool(
            name="update_hypothesis",
            source_tool_class="UpdateHypothesisTool",
            description="Hypothesis updates are not yet migrated.",
            reason="Hypothesis service migration is pending.",
        ),
        _disabled_tool(
            name="link_backtest",
            source_tool_class="LinkBacktestTool",
            description="Hypothesis-to-backtest linking is not yet migrated.",
            reason="Backtest artifact linkage is pending.",
        ),
        _disabled_tool(
            name="search_hypotheses",
            source_tool_class="SearchHypothesesTool",
            description="Hypothesis search is not yet migrated.",
            reason="Hypothesis service migration is pending.",
        ),
        _disabled_tool(
            name="options_pricing",
            source_tool_class="OptionsPricingTool",
            description="Options pricing is not yet migrated.",
            reason="Options pricing service migration is pending.",
        ),
        _disabled_tool(
            name="pattern",
            source_tool_class="PatternTool",
            description="Pattern extraction is not yet migrated.",
            reason="Pattern service migration is pending.",
        ),
        _disabled_tool(
            name="read_file",
            source_tool_class="ReadFileTool",
            description="Owned file reads are not yet wired to scoped uploads/artifacts.",
            reason="Scoped upload/artifact file access is pending.",
            required_capability="owned_file_read",
        ),
        _disabled_tool(
            name="read_document",
            source_tool_class="DocReaderTool",
            description="Document reading is not yet wired to owned uploads.",
            reason="Document upload and parser migration is pending.",
            required_capability="owned_document_reader",
        ),
        _disabled_tool(
            name="read_url",
            source_tool_class="WebReaderTool",
            description="Web URL reading is not yet enabled.",
            reason="URL allow/block policy and timeout controls are pending.",
            required_capability="web_reader_policy",
        ),
        _disabled_tool(
            name="web_search",
            source_tool_class="WebSearchTool",
            description="Web search is not yet enabled.",
            reason="Search provider configuration and policy controls are pending.",
            required_capability="web_search_provider",
        ),
        _disabled_tool(
            name="start_research_goal",
            source_tool_class="StartResearchGoalTool",
            description="Research goals are not yet migrated.",
            reason="Goal service migration is pending.",
        ),
        _disabled_tool(
            name="update_research_goal_status",
            source_tool_class="UpdateResearchGoalStatusTool",
            description="Research goal status updates are not yet migrated.",
            reason="Goal service migration is pending.",
        ),
        _disabled_tool(
            name="get_research_goal",
            source_tool_class="GetResearchGoalTool",
            description="Research goal lookup is not yet migrated.",
            reason="Goal service migration is pending.",
        ),
        _disabled_tool(
            name="add_goal_evidence",
            source_tool_class="AddGoalEvidenceTool",
            description="Research goal evidence is not yet migrated.",
            reason="Goal evidence service migration is pending.",
        ),
        _disabled_tool(
            name="load_skill",
            source_tool_class="LoadSkillTool",
            description="Skill loading is not yet wired to current-project skill storage.",
            reason="Skill catalog migration is pending.",
        ),
        _disabled_tool(
            name="trading_connections",
            source_tool_class="TradingConnectionsTool",
            description="Trading connector listing is not yet migrated.",
            reason="Live connector facade migration is pending.",
            required_capability="live_connector_read",
        ),
        _disabled_tool(
            name="trading_select_connection",
            source_tool_class="TradingSelectConnectionTool",
            description="Trading connector selection is not yet migrated.",
            reason="Live connector facade migration is pending.",
            required_capability="live_connector_read",
        ),
        _disabled_tool(
            name="trading_check",
            source_tool_class="TradingCheckTool",
            description="Trading connector health checks are not yet migrated.",
            reason="Live connector facade migration is pending.",
            required_capability="live_connector_read",
        ),
        _disabled_tool(
            name="trading_account",
            source_tool_class="TradingAccountTool",
            description="Trading account reads are not yet migrated.",
            reason="Live connector facade migration is pending.",
            required_capability="live_connector_read",
        ),
        _disabled_tool(
            name="trading_positions",
            source_tool_class="TradingPositionsTool",
            description="Trading position reads are not yet migrated.",
            reason="Live connector facade migration is pending.",
            required_capability="live_connector_read",
        ),
        _disabled_tool(
            name="trading_orders",
            source_tool_class="TradingOrdersTool",
            description="Trading order reads are not yet migrated.",
            reason="Live connector facade migration is pending.",
            required_capability="live_connector_read",
        ),
        _disabled_tool(
            name="trading_quote",
            source_tool_class="TradingQuoteTool",
            description="Trading quote reads are not yet migrated.",
            reason="Live connector facade migration is pending.",
            required_capability="live_connector_read",
        ),
        _disabled_tool(
            name="trading_history",
            source_tool_class="TradingHistoryTool",
            description="Trading history reads are not yet migrated.",
            reason="Live connector facade migration is pending.",
            required_capability="live_connector_read",
        ),
        _disabled_tool(
            name="propose_mandate_profiles",
            source_tool_class="ProposeMandateProfilesTool",
            description="Mandate proposal tooling is not yet migrated.",
            reason="Live mandate service migration is pending.",
            required_capability="live_mandate_propose",
        ),
        _disabled_tool(
            name="run_swarm",
            source_tool_class="SwarmTool",
            description="Swarm/team runtime is not yet migrated.",
            reason="Swarm service migration is pending.",
            required_capability="swarm_runtime",
        ),
        _disabled_tool(
            name="extract_shadow_strategy",
            source_tool_class="ExtractShadowStrategyTool",
            description="Shadow strategy extraction is not yet migrated.",
            reason="Shadow account service migration is pending.",
        ),
        _disabled_tool(
            name="run_shadow_backtest",
            source_tool_class="RunShadowBacktestTool",
            description="Shadow backtest execution is not yet migrated.",
            reason="Shadow account service migration is pending.",
        ),
        _disabled_tool(
            name="render_shadow_report",
            source_tool_class="RenderShadowReportTool",
            description="Shadow report rendering is not yet migrated.",
            reason="Shadow account service migration is pending.",
        ),
        _disabled_tool(
            name="scan_shadow_signals",
            source_tool_class="ScanShadowSignalsTool",
            description="Shadow signal scanning is not yet migrated.",
            reason="Shadow account service migration is pending.",
        ),
        _disabled_tool(
            name="analyze_trade_journal",
            source_tool_class="TradeJournalTool",
            description="Trade journal parsing is not yet migrated.",
            reason="Owned upload parsing and journal analytics are pending.",
        ),
        _disabled_tool(
            name="bash",
            source_tool_class="BashTool",
            description="Shell execution is disabled by default.",
            permission=ADMIN_UNSAFE_TOOL,
            reason="Shell execution requires explicit sandbox, allowlist, timeout, and audit configuration.",
            required_capability="sandboxed_shell",
        ),
        _disabled_tool(
            name="shell",
            source_tool_class="ShellTool",
            description="Shell execution is disabled by default.",
            permission=ADMIN_UNSAFE_TOOL,
            reason="Shell execution requires explicit sandbox, allowlist, timeout, and audit configuration.",
            required_capability="sandboxed_shell",
        ),
        _disabled_tool(
            name="docker_python_repl",
            source_tool_class="DockerPythonREPLTool",
            description="Isolated Python execution is disabled until sandbox policy is configured.",
            permission=ADMIN_UNSAFE_TOOL,
            reason="Python execution requires container isolation, resource limits, and audit logs.",
            required_capability="sandboxed_python",
        ),
        _disabled_tool(
            name="write_file",
            source_tool_class="WriteFileTool",
            description="Arbitrary file writes are disabled.",
            permission=ADMIN_UNSAFE_TOOL,
            reason="File mutation requires workspace scoping and explicit admin approval.",
            required_capability="scoped_file_write",
        ),
        _disabled_tool(
            name="edit_file",
            source_tool_class="EditFileTool",
            description="Arbitrary file edits are disabled.",
            permission=ADMIN_UNSAFE_TOOL,
            reason="File mutation requires workspace scoping and explicit admin approval.",
            required_capability="scoped_file_edit",
        ),
        _disabled_tool(
            name="save_skill",
            source_tool_class="SaveSkillTool",
            description="Skill mutation is disabled by default.",
            permission=ADMIN_UNSAFE_TOOL,
            reason="Skill writes require admin/skill-write policy and current-project skill storage.",
            required_capability="skill_write",
        ),
        _disabled_tool(
            name="patch_skill",
            source_tool_class="PatchSkillTool",
            description="Skill mutation is disabled by default.",
            permission=ADMIN_UNSAFE_TOOL,
            reason="Skill writes require admin/skill-write policy and current-project skill storage.",
            required_capability="skill_write",
        ),
        _disabled_tool(
            name="delete_skill",
            source_tool_class="DeleteSkillTool",
            description="Skill deletion is disabled by default.",
            permission=ADMIN_UNSAFE_TOOL,
            reason="Skill deletion requires admin/skill-write policy and current-project skill storage.",
            required_capability="skill_write",
        ),
        _disabled_tool(
            name="skill_file",
            source_tool_class="SkillFileTool",
            description="Skill file access is disabled by default.",
            permission=ADMIN_UNSAFE_TOOL,
            reason="Skill file access requires scoped current-project skill storage.",
            required_capability="skill_file_access",
        ),
        _disabled_tool(
            name="trading_place_order",
            source_tool_class="TradingPlaceOrderTool",
            description="Live order placement is disabled by default.",
            permission=ADMIN_UNSAFE_TOOL,
            reason="Live trading requires explicit mandate, connector liveness, and surface authorization.",
            required_capability="live_trading_commit",
        ),
        _disabled_tool(
            name="trading_cancel_order",
            source_tool_class="TradingCancelOrderTool",
            description="Live order cancellation is disabled by default.",
            permission=ADMIN_UNSAFE_TOOL,
            reason="Live trading requires explicit mandate, connector liveness, and surface authorization.",
            required_capability="live_trading_commit",
        ),
        _disabled_tool(
            name="mcp_remote",
            source_tool_class="MCPRemoteTool",
            description="Remote MCP execution is disabled until configured.",
            permission=ADMIN_UNSAFE_TOOL,
            reason="MCP remote tools require explicit server allowlist, classification, and permissions.",
            required_capability="mcp_remote_allowlist",
        ),
    ]
