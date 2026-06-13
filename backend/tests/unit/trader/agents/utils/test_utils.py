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
