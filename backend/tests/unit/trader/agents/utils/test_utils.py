from support.registry import export_module as _export_module

_export_module(globals(), "support.m0114.real.scenario.fi.module")
_export_module(globals(), "support.m0114.us.stock.independence.module")
_export_module(globals(), "support.m000002.valuation.module")
_export_module(globals(), "support.agent.utils.tushare.fi.module")
_export_module(globals(), "support.dashscope.tool.calling.fi.module")
_export_module(globals(), "support.detailed.data.display.module")
_export_module(globals(), "support.final.verification.module")
_export_module(globals(), "support.final.verification.with.config.module")
_export_module(globals(), "support.instrument.identity.module")
_export_module(globals(), "support.news.analyst.fi.module")
_export_module(globals(), "support.optimized.data.depth.module")
_export_module(globals(), "support.optimized.fundamentals.module")
_export_module(globals(), "support.simple.depth.check.module")
_export_module(globals(), "support.tool.call.issue.module")
_export_module(globals(), "support.tool.execution.flow.module")
del _export_module


def test_agent_utils_core_imports_without_split_module_name_errors() -> None:
    import trader.agents.utils.core as core

    assert core.Toolkit.get_stock_news_unified.name == "get_stock_news_unified"


def test_agent_utils_base_reads_facade_toolkit_config() -> None:
    import trader.agents.utils.core as core
    import trader.agents.utils.core.base as base

    original_config = core.Toolkit._config.copy()
    try:
        core.Toolkit._config["research_depth"] = 3
        assert base._get_research_depth() == 3
    finally:
        core.Toolkit._config.clear()
        core.Toolkit._config.update(original_config)
