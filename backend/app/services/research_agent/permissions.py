from __future__ import annotations


MARKET_DATA_READ = "research.market_data.read"
SCREENING_RUN = "research.screening.run"
SINGLE_STOCK_ANALYSIS = "research.analysis.single"
BATCH_STOCK_ANALYSIS = "research.analysis.batch"
REPORT_READ = "research.report.read"
REPORT_WRITE = "research.report.write"
ALPHA_READ = "research.alpha.read"
ALPHA_RUN = "research.alpha.run"
CORRELATION_RUN = "research.correlation.run"
GOAL_READ = "research.goal.read"
GOAL_WRITE = "research.goal.write"
GOAL_EVIDENCE_WRITE = "research.goal.evidence.write"
SWARM_READ = "research.swarm.read"
SWARM_RUN = "research.swarm.run"
LIVE_READ = "research.live.read"
LIVE_MANDATE_PROPOSE = "research.live.mandate.propose"
LIVE_MANDATE_COMMIT = "research.live.mandate.commit"
LIVE_HALT = "research.live.halt"
LIVE_RUNNER_CONTROL = "research.live.runner_control"
DOCUMENT_READ = "research.document.read"
WEB_READ = "research.web.read"
WEB_SEARCH = "research.web.search"
SHADOW_RUN = "research.shadow.run"
SKILL_READ = "research.skill.read"
MEMORY_WRITE = "research.memory.write"
HYPOTHESIS_READ = "research.hypothesis.read"
HYPOTHESIS_WRITE = "research.hypothesis.write"
OPTIONS_RUN = "research.options.run"
PATTERN_RUN = "research.pattern.run"
FACTOR_RUN = "research.factor.run"
BACKTEST_RUN = "research.backtest.run"
TRADE_JOURNAL_ANALYZE = "research.trade_journal.analyze"
SESSION_SEARCH = "research.session.search"
BACKGROUND_JOB_READ = "research.job.read"
COMPACT_CONTEXT = "research.context.compact"
DISABLED_RESEARCH_TOOL = "research.tool.disabled"
ADMIN_CONFIG_WRITE = "admin.config.write"
ADMIN_UNSAFE_TOOL = "admin.agent_unsafe_tool"


def normal_user_permissions() -> frozenset[str]:
    return frozenset(
        {
            MARKET_DATA_READ,
            SCREENING_RUN,
            SINGLE_STOCK_ANALYSIS,
            BATCH_STOCK_ANALYSIS,
            REPORT_READ,
            REPORT_WRITE,
            ALPHA_READ,
            ALPHA_RUN,
            CORRELATION_RUN,
            GOAL_READ,
            GOAL_WRITE,
            GOAL_EVIDENCE_WRITE,
            SWARM_READ,
            SWARM_RUN,
            LIVE_READ,
            LIVE_MANDATE_PROPOSE,
            DOCUMENT_READ,
            WEB_READ,
            WEB_SEARCH,
            SHADOW_RUN,
            SKILL_READ,
            MEMORY_WRITE,
            HYPOTHESIS_READ,
            HYPOTHESIS_WRITE,
            OPTIONS_RUN,
            PATTERN_RUN,
            FACTOR_RUN,
            BACKTEST_RUN,
            TRADE_JOURNAL_ANALYZE,
            SESSION_SEARCH,
            BACKGROUND_JOB_READ,
            COMPACT_CONTEXT,
            DISABLED_RESEARCH_TOOL,
        }
    )


def admin_permissions() -> frozenset[str]:
    return frozenset(
        {
            ADMIN_CONFIG_WRITE,
            ADMIN_UNSAFE_TOOL,
            LIVE_MANDATE_COMMIT,
            LIVE_HALT,
            LIVE_RUNNER_CONTROL,
        }
    )
