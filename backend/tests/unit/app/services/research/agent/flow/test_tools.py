from langchain_core.messages import AIMessage, ToolMessage

from app.services.research.agent.flow.stages.analysts import (
    ToolInventory,
    ToolRunner,
)


class FakeToolkit:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def tool(**kwargs):
            self.calls.append((name, kwargs))
            return f"{name}:{kwargs}"

        tool.__name__ = name
        return tool


def test_tool_inventory_names_match_old_tool_nodes():
    inventory = ToolInventory(FakeToolkit())

    assert inventory.tool_names("market") == [
        "get_stock_market_data_unified",
        "get_yfin_data_online",
        "get_stockstats_indicators_report_online",
        "get_yfin_data",
        "get_stockstats_indicators_report",
    ]
    assert inventory.tool_names("social") == [
        "get_stock_sentiment_unified",
        "get_stock_news_openai",
        "get_reddit_stock_info",
    ]
    assert inventory.tool_names("news") == [
        "get_stock_news_unified",
        "get_global_news_openai",
        "get_google_news",
        "get_finnhub_news",
        "get_reddit_news",
    ]
    assert inventory.tool_names("fundamentals") == [
        "get_stock_fundamentals_unified",
        "get_finnhub_company_insider_sentiment",
        "get_finnhub_company_insider_transactions",
        "get_simfin_balance_sheet",
        "get_simfin_cashflow",
        "get_simfin_income_stmt",
        "get_china_stock_data",
        "get_china_fundamentals",
    ]


def test_tool_runner_executes_current_ai_message_tool_calls():
    toolkit = FakeToolkit()
    runner = ToolRunner(ToolInventory(toolkit))
    state = {"messages": []}
    state["messages"].append(
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_stock_market_data_unified",
                    "args": {"symbol": "600519"},
                    "id": "call-1",
                }
            ],
        )
    )

    update = runner.run_tools("market", state)

    assert toolkit.calls == [
        ("get_stock_market_data_unified", {"symbol": "600519"})
    ]
    assert len(update["messages"]) == 1
    assert isinstance(update["messages"][0], ToolMessage)
    assert update["messages"][0].tool_call_id == "call-1"
    assert "get_stock_market_data_unified" in str(update["messages"][0].content)
