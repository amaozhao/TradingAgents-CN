from __future__ import annotations

from typing import Any

from trader.graph.conditions import ConditionalLogic


class WorkflowConditionAdapter:
    def __init__(self, logic: ConditionalLogic):
        self.logic = logic

    def should_continue_market(self, state: Any) -> str:
        return self.logic.should_continue_market(state)

    def should_continue_social(self, state: Any) -> str:
        return self.logic.should_continue_social(state)

    def should_continue_news(self, state: Any) -> str:
        return self.logic.should_continue_news(state)

    def should_continue_fundamentals(self, state: Any) -> str:
        return self.logic.should_continue_fundamentals(state)

    def should_continue_debate(self, state: Any) -> str:
        return self.logic.should_continue_debate(state)

    def should_continue_risk_analysis(self, state: Any) -> str:
        return self.logic.should_continue_risk_analysis(state)
