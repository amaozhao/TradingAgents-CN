"""Portfolio Manager: synthesises the risk-analyst debate into the final decision.

Uses LangChain's ``with_structured_output`` so the LLM produces a typed
``PortfolioDecision`` directly, in a single call.  The result is rendered
back to markdown for storage in ``final_trade_decision`` so memory log,
CLI display, and saved reports continue to consume the same shape they do
today.  When a provider does not expose structured output, the agent falls
back gracefully to free-text generation.
"""

from __future__ import annotations

from tradingagents.agents.schemas import PortfolioDecision, render_pm_decision
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
)
from tradingagents.agents.utils.structured import (
    bind_structured,
    invoke_structured_or_freetext,
)


def create_portfolio_manager(llm):
    structured_llm = bind_structured(llm, PortfolioDecision, "Portfolio Manager")

    def portfolio_manager_node(state) -> dict:
        instrument_context = get_instrument_context_from_state(state)

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        research_plan = state["investment_plan"]
        trader_plan = state["trader_investment_plan"]

        past_context = state.get("past_context", "")
        lessons_line = (
            f"- Lessons from prior decisions and outcomes:\n{past_context}\n"
            if past_context
            else ""
        )

        prompt = f"""作为投资组合经理，请综合风险分析师辩论，给出最终交易决策。

{instrument_context}

---

**评级标准**（必须使用其中一个）:
- **Buy**: 强烈看多，建议买入或增加仓位
- **Overweight**: 偏积极，建议逐步增加敞口
- **Hold**: 维持当前仓位，暂不行动
- **Underweight**: 偏谨慎，建议降低敞口或部分止盈
- **Sell**: 建议卖出、退出或避免进入

**上下文:**
- 研究经理投资计划: **{research_plan}**
- 交易员交易方案: **{trader_plan}**
{lessons_line}
**风险分析师辩论历史:**
{history}

---

请保持明确、可执行，并基于分析师报告中的具体证据给出结论。必须包含中文执行摘要、投资逻辑、目标价或说明目标价依据。{get_language_instruction()}"""

        final_trade_decision = invoke_structured_or_freetext(
            structured_llm,
            llm,
            prompt,
            render_pm_decision,
            "Portfolio Manager",
        )

        new_risk_debate_state = {
            "judge_decision": final_trade_decision,
            "history": risk_debate_state["history"],
            "risky_history": risk_debate_state.get(
                "risky_history",
                risk_debate_state.get("aggressive_history", ""),
            ),
            "aggressive_history": risk_debate_state.get(
                "aggressive_history",
                risk_debate_state.get("risky_history", ""),
            ),
            "safe_history": risk_debate_state.get(
                "safe_history",
                risk_debate_state.get("conservative_history", ""),
            ),
            "conservative_history": risk_debate_state.get(
                "conservative_history",
                risk_debate_state.get("safe_history", ""),
            ),
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_risky_response": risk_debate_state.get(
                "current_risky_response",
                risk_debate_state.get("current_aggressive_response", ""),
            ),
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response",
                risk_debate_state.get("current_risky_response", ""),
            ),
            "current_safe_response": risk_debate_state.get(
                "current_safe_response",
                risk_debate_state.get("current_conservative_response", ""),
            ),
            "current_conservative_response": risk_debate_state.get(
                "current_conservative_response",
                risk_debate_state.get("current_safe_response", ""),
            ),
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
        }

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": final_trade_decision,
        }

    return portfolio_manager_node
