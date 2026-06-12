from app.services.research.agent.flow import context as flow_context


class FakeMemory:
    def __init__(self, name, config):
        self.name = name
        self.config = config


class FakeToolkit:
    def __init__(self, config):
        self.config = config


class FakeMemoryLog:
    def __init__(self, config):
        self.config = config


def test_builds_context_with_old_graph_components(monkeypatch):
    fake_quick_llm = object()
    fake_deep_llm = object()

    monkeypatch.setattr(flow_context, "FinancialSituationMemory", FakeMemory)
    monkeypatch.setattr(flow_context, "Toolkit", FakeToolkit)
    monkeypatch.setattr(flow_context, "TradingMemoryLog", FakeMemoryLog)

    context = flow_context.build_stock_workflow_context(
        symbol="600519",
        trade_date="2026-06-12",
        asset_type="stock",
        selected_analysts=["market", "social", "news", "fundamentals"],
        config={
            "memory_enabled": True,
            "max_debate_rounds": 2,
            "max_risk_discuss_rounds": 3,
        },
        quick_llm=fake_quick_llm,
        deep_llm=fake_deep_llm,
    )

    assert context.symbol == "600519"
    assert context.trade_date == "2026-06-12"
    assert context.asset_type == "stock"
    assert context.selected_analysts == [
        "market",
        "social",
        "news",
        "fundamentals",
    ]
    assert context.quick_llm is fake_quick_llm
    assert context.deep_llm is fake_deep_llm
    assert context.conditional_logic.max_debate_rounds == 2
    assert context.conditional_logic.max_risk_discuss_rounds == 3
    assert context.runtime_config.recursion_limit == 100
    assert context.bull_memory.name == "bull_memory"
    assert context.bear_memory.name == "bear_memory"
    assert context.trader_memory.name == "trader_memory"
    assert context.invest_judge_memory.name == "invest_judge_memory"
    assert context.risk_manager_memory.name == "risk_manager_memory"
    assert context.signal_processor.quick_thinking_llm is fake_quick_llm
    assert context.reflector.quick_thinking_llm is fake_quick_llm
    assert context.memory_log.config["max_debate_rounds"] == 2
    assert context.toolkit.config["max_risk_discuss_rounds"] == 3


def test_builds_context_without_role_memories_when_disabled(monkeypatch):
    fake_quick_llm = object()
    fake_deep_llm = object()

    monkeypatch.setattr(flow_context, "FinancialSituationMemory", FakeMemory)
    monkeypatch.setattr(flow_context, "Toolkit", FakeToolkit)
    monkeypatch.setattr(flow_context, "TradingMemoryLog", FakeMemoryLog)

    context = flow_context.build_stock_workflow_context(
        symbol="AAPL",
        trade_date="2026-06-12",
        asset_type="stock",
        selected_analysts=["market"],
        config={"memory_enabled": False},
        quick_llm=fake_quick_llm,
        deep_llm=fake_deep_llm,
    )

    assert context.bull_memory is None
    assert context.bear_memory is None
    assert context.trader_memory is None
    assert context.invest_judge_memory is None
    assert context.risk_manager_memory is None
