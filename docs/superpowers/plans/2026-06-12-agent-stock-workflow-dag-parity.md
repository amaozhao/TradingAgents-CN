# 研究智能体单股分析有向无环图对齐工作流实施计划

> **给执行智能体：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，按任务逐项实施。所有步骤使用复选框（`- [ ]`）跟踪。

**目标：** 在研究智能体内实现新的单股分析工作流，完整复刻旧 TradingAgents LangGraph 有向无环图（DAG）的节点、边、条件边、工具、状态、运行时副作用和报告格式，但不在智能体工作流中调用 `TradingAgentsGraph.propagate()` 或已编译的 LangGraph。

**架构：** 新增 `backend/app/services/research/agent/flow/`，把旧 DAG 的图计划、上下文工厂、状态合并、工具执行器、阶段执行器、收尾钩子和报告持久化显式拆开。`flow` 是真实单词，符合仓库新增文件/目录命名规则；业务含义放在 `StockDagParityWorkflow` 等代码符号中表达。`StockAnalysisWorkflow.run_single()` 切到 `StockDagParityWorkflow.run()`，旧 `run_native_stock_workflow()` 只保留为隔离的非默认后备路径。旧 `/analysis/single` 和旧 DAG 保留作为基线，不被删除或改写。

**技术栈：** Python 3.13、FastAPI 服务模块、LangChain 消息类、现有 `trader.agents.create_*` 工厂、现有 `Toolkit`、现有 `ConditionalLogic`、现有 `build_analysis_result`、pytest、monkeypatch、假 LLM、假工具夹具。

---

## 来源规格

本计划实现：

- `docs/superpowers/specs/2026-06-12-agent-stock-workflow-dag-parity.md`

旧 `docs/superpowers/specs/stock.md` 只是索引和废弃说明，不作为实现依据。

## 硬性约束

- 不调用 `TradingAgentsGraph.propagate()`。
- 不调用 `self.workflow.compile(...)`。
- 不把 LangGraph `StateGraph` 作为智能体工作流执行器。
- 不把旧 Redis 队列 / 分析工作进程作为智能体工作流主路径。
- 不继续默认调用 `run_native_stock_workflow()`。
- 不用原生辅助函数伪造 `market_report`、`fundamentals_report`、`news_report`、`sentiment_report`、`final_trade_decision`。
- 不用一个最终 LLM 提示词替代 Bull/Bear/Research Manager/Trader/风险辩论。
- 不在规格外发明报告字段替代旧字段。
- 不删除旧 DAG，不删除旧单股分析页面。

## 文件地图

### 新增后端模块

- 新增： `backend/app/services/research/agent/flow/__init__.py`
  - 导出 `StockDagParityWorkflow`、`StockDagParityWorkflowResult`。
- 新增： `backend/app/services/research/agent/flow/context.py`
  - 构建等价于旧 `TradingAgentsGraph` 初始化的工作流上下文：快/深两类 LLM、工具包、角色记忆、条件逻辑、信号处理器、记忆日志、反思器、标的、日期和配置。
- 新增： `backend/app/services/research/agent/flow/graph.py`
  - 建模旧 DAG 节点、普通边、条件边、默认分析师顺序、最终风险节点选择和节点到阶段映射。
- 新增： `backend/app/services/research/agent/flow/state.py`
  - 创建等价于 `Propagator.create_initial_state()` 的初始状态。
  - 按 LangGraph `MessagesState` 语义合并节点更新，包括 `RemoveMessage` 和 `ToolMessage`。
- 新增： `backend/app/services/research/agent/flow/events.py`
  - 为当前智能体执行尝试发出节点事件并聚合阶段事件。
- 新增： `backend/app/services/research/agent/flow/checkpoint.py`
  - 实现 `WorkflowCheckpointAdapter`；如果本阶段不实现检查点，则在 `checkpoint_enabled=True` 时显式报不支持。
- 新增： `backend/app/services/research/agent/flow/runner.py`
  - 主确定性工作流状态机、游标、计时收集和收尾钩子。
- 新增： `backend/app/services/research/agent/flow/stages/__init__.py`
  - 阶段包标记文件。
- 新增： `backend/app/services/research/agent/flow/stages/analysts.py`
  - 分析师角色 / 工具 / 清理循环执行器和 `ToolInventory`。
- 新增： `backend/app/services/research/agent/flow/stages/research.py`
  - Bull/Bear/Research Manager 循环。
- 新增： `backend/app/services/research/agent/flow/stages/trader.py`
  - Trader 节点执行器。
- 新增： `backend/app/services/research/agent/flow/stages/risk.py`
  - Risky/Safe/Neutral 循环。
- 新增： `backend/app/services/research/agent/flow/stages/decision.py`
  - Risk Judge / Portfolio Manager 执行器。
- 新增： `backend/app/services/research/agent/flow/stages/reports.py`
  - `build_analysis_result()` 适配器和报告持久化。

### 修改后端模块

- 修改： `backend/app/services/research/agent/stock.py`
  - 把默认 `run_native_stock_workflow()` 调用替换为 `StockDagParityWorkflow.run()`。
  - 保留标的代码和模型归一化行为。
  - 保留任务和报告链接。
- 修改： `backend/app/services/research/agent/native.py`
  - 不删除；隔离为非默认后备路径，并用测试保证 `stock_analysis` 默认路径不能调用它。
- 修改： `backend/app/services/research/agent/stage.py`
  - 如果现有常量和规格文档中的 DAG 对齐阶段列表不一致，则对齐阶段标识符和节点事件聚合。
- 修改： `backend/app/services/research/agent/tools/analysis.py`
  - 更新工具描述和提示词元数据，让智能体明确单股分析执行 DAG 对齐工作流。
- 修改： `backend/app/services/research/agent/registry.py`
  - 仅在注册元数据需要补充来源或工具描述时修改。

### 新增后端测试

- 新增： `backend/tests/regression/research/agent/flow/graph/test.py`
- 新增： `backend/tests/regression/research/agent/flow/context/test.py`
- 新增： `backend/tests/regression/research/agent/flow/state/test.py`
- 新增： `backend/tests/regression/research/agent/flow/tools/test.py`
- 新增： `backend/tests/regression/research/agent/flow/conditions/test.py`
- 新增： `backend/tests/regression/research/agent/flow/runner/test.py`
- 新增： `backend/tests/regression/research/agent/flow/reports/test.py`
- 新增： `backend/tests/regression/research/agent/flow/checkpoint/test.py`
- 新增： `backend/tests/regression/research/agent/flow/integration/test.py`
- 修改： `backend/tests/regression/research/agent/analysis/test.py`
  - 增加默认路径禁止回归断言。

## 任务 1: 静态图计划对齐

**规格覆盖：** 硬性要求 1-5、9、12；旧 DAG 节点列表；旧 DAG 边列表；默认分析师顺序；最终风险节点选择；关闭风险评估时的真实绕行边。

**文件：**

- 新增： `backend/app/services/research/agent/flow/graph.py`
- 测试： `backend/tests/regression/research/agent/flow/graph/test.py`

- [x] **步骤 1: 编写默认图节点和分析师顺序的失败测试**

测试期望：

```python
plan = build_stock_dag_parity_plan(
    selected_analysts=None,
    final_decision_engine="risk_manager",
)

assert [spec.key for spec in plan.analyst_specs] == [
    "market",
    "social",
    "news",
    "fundamentals",
]
assert plan.first_node == "Market Analyst"
assert plan.final_risk_node == "Risk Judge"
assert plan.nodes == [
    "Market Analyst",
    "tools_market",
    "Msg Clear Market",
    "Sentiment Analyst",
    "tools_social",
    "Msg Clear Social",
    "News Analyst",
    "tools_news",
    "Msg Clear News",
    "Fundamentals Analyst",
    "tools_fundamentals",
    "Msg Clear Fundamentals",
    "Bull Researcher",
    "Bear Researcher",
    "Research Manager",
    "Trader",
    "Risky Analyst",
    "Safe Analyst",
    "Neutral Analyst",
    "Risk Judge",
    "END",
]
```

- [x] **步骤 2: 编写普通边和条件边的失败测试**

测试期望：

```python
assert ("START", "Market Analyst") in plan.normal_edges
assert ("tools_market", "Market Analyst") in plan.normal_edges
assert ("Msg Clear Market", "Sentiment Analyst") in plan.normal_edges
assert ("Msg Clear Social", "News Analyst") in plan.normal_edges
assert ("Msg Clear News", "Fundamentals Analyst") in plan.normal_edges
assert ("Msg Clear Fundamentals", "Bull Researcher") in plan.normal_edges
assert ("Research Manager", "Trader") in plan.normal_edges
assert ("Trader", "Risky Analyst") in plan.normal_edges
assert ("Risk Judge", "END") in plan.normal_edges

assert plan.conditional_edges["Market Analyst"].targets == [
    "tools_market",
    "Msg Clear Market",
]
assert plan.conditional_edges["Bull Researcher"].target_map == {
    "Bear Researcher": "Bear Researcher",
    "Research Manager": "Research Manager",
}
assert plan.conditional_edges["Risky Analyst"].target_map == {
    "Safe Analyst": "Safe Analyst",
    "Risk Judge": "Risk Judge",
}
```

- [x] **步骤 3: 编写 `Portfolio Manager` 最终风险模式的失败测试**

测试期望：

```python
plan = build_stock_dag_parity_plan(
    selected_analysts=["market"],
    final_decision_engine="portfolio_manager",
)

assert plan.nodes[-2:] == ["Portfolio Manager", "END"]
assert ("Risky Analyst", "Portfolio Manager") in plan.resolved_conditional_targets
assert ("Safe Analyst", "Portfolio Manager") in plan.resolved_conditional_targets
assert ("Neutral Analyst", "Portfolio Manager") in plan.resolved_conditional_targets
```

- [x] **步骤 4: 编写 `include_risk=False` 的真实绕行边失败测试**

该测试不是只检查跳过事件，而是检查执行图本身不包含风险执行路径。

```python
plan = build_stock_dag_parity_plan(
    selected_analysts=["market"],
    final_decision_engine="risk_manager",
    include_risk=False,
)

assert ("Trader", "END") in plan.normal_edges
assert ("Trader", "Risky Analyst") not in plan.normal_edges
assert "Risky Analyst" in plan.skipped_nodes
assert "Safe Analyst" in plan.skipped_nodes
assert "Neutral Analyst" in plan.skipped_nodes
assert "Risk Judge" in plan.skipped_nodes
assert "Portfolio Manager" in plan.skipped_nodes
assert plan.stage_status_overrides["risk_debate"] == "skipped"
assert plan.stage_status_overrides["final_risk_decision"] == "skipped"
```

执行器必须按这个图计划运行；关闭风险评估时不能执行 `Risky Analyst`、`Safe Analyst`、`Neutral Analyst`、`Risk Judge`、`Portfolio Manager` 后再隐藏结果。

- [x] **步骤 5: 实现图计划数据类**

实现：

- `AnalystPlanNode`
- `ConditionalEdge`
- `StockDagParityPlan`
- `build_stock_dag_parity_plan(selected_analysts, final_decision_engine, analyst_concurrency_limit=1, include_risk=True)`

实现必须复用 `trader.graph.analysts.build_analyst_execution_plan()` 和 `ANALYST_NODE_SPECS`。

- [x] **步骤 6: 运行图计划测试**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/flow/graph/test.py -q
```

期望：全部测试通过。

## 任务 2: 上下文工厂对齐

**规格覆盖：** 旧 DAG 上下文组件；快/深两类 LLM 映射；`Toolkit`；角色记忆；`ConditionalLogic`；`Propagator`；`Reflector`；`TradingMemoryLog`；`SignalProcessor`。

**文件：**

- 新增： `backend/app/services/research/agent/flow/context.py`
- 测试： `backend/tests/regression/research/agent/flow/context/test.py`

- [x] **步骤 1: 编写上下文构建失败测试**

使用假的快/深两类 LLM 对象，并在需要时通过 monkeypatch 替换工厂。

期望断言：

```python
context = build_stock_workflow_context(
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

assert context.quick_llm is fake_quick_llm
assert context.deep_llm is fake_deep_llm
assert context.conditional_logic.max_debate_rounds == 2
assert context.conditional_logic.max_risk_discuss_rounds == 3
assert context.runtime_config.recursion_limit == 100
assert context.bull_memory is not None
assert context.bear_memory is not None
assert context.trader_memory is not None
assert context.invest_judge_memory is not None
assert context.risk_manager_memory is not None
assert context.signal_processor.quick_thinking_llm is fake_quick_llm
```

- [x] **步骤 2: 编写关闭记忆时的失败测试**

期望断言：

```python
context = build_stock_workflow_context(
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
```

- [x] **步骤 3: 实现 `StockWorkflowContext` 和工厂函数**

必需字段：

- `symbol`
- `trade_date`
- `asset_type`
- `config`
- `quick_llm`
- `deep_llm`
- `toolkit`
- `bull_memory`
- `bear_memory`
- `trader_memory`
- `invest_judge_memory`
- `risk_manager_memory`
- `conditional_logic`
- `signal_processor`
- `memory_log`
- `reflector`
- `attempt_id`
- `task_id`
- `principal`

不要实例化 `TradingAgentsGraph`。

- [x] **步骤 4: 运行上下文测试**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/flow/context/test.py -q
```

期望：全部测试通过。

## 任务 3: 状态工厂和 LangGraph 等价合并语义

**规格覆盖：** `Propagator.create_initial_state`；`AgentState`；`MessagesState`；`RemoveMessage`；`ToolMessage`；`sender`；最终状态字段。

**文件：**

- 新增： `backend/app/services/research/agent/flow/state.py`
- 测试： `backend/tests/regression/research/agent/flow/state/test.py`

- [x] **步骤 1: 编写初始状态对齐失败测试**

和 `Propagator.create_initial_state()` 对比：

```python
old_state = Propagator().create_initial_state(
    "600519",
    "2026-06-12",
    asset_type="stock",
    past_context="past",
    instrument_context="instrument",
)
new_state = create_stock_initial_state(
    "600519",
    "2026-06-12",
    asset_type="stock",
    past_context="past",
    instrument_context="instrument",
)

assert new_state["company_of_interest"] == old_state["company_of_interest"]
assert new_state["asset_type"] == old_state["asset_type"]
assert new_state["instrument_context"] == old_state["instrument_context"]
assert new_state["trade_date"] == old_state["trade_date"]
assert new_state["past_context"] == old_state["past_context"]
assert new_state["investment_debate_state"] == old_state["investment_debate_state"]
assert new_state["risk_debate_state"] == old_state["risk_debate_state"]
assert new_state["market_tool_call_count"] == 0
assert new_state["news_tool_call_count"] == 0
assert new_state["sentiment_tool_call_count"] == 0
assert new_state["fundamentals_tool_call_count"] == 0
```

- [x] **步骤 2: 编写消息合并失败测试**

期望断言：

```python
state = create_stock_initial_state("600519", "2026-06-12")
first = state["messages"][0]
ai = AIMessage(content="analysis", id="ai-1")

apply_node_update(state, {"messages": [ai]})
assert [message.id for message in state["messages"]] == [first.id, "ai-1"]

apply_node_update(
    state,
    {
        "messages": [
            RemoveMessage(id=first.id),
            RemoveMessage(id="ai-1"),
            HumanMessage(content="继续分析，不要改变分析标的。", id="placeholder"),
        ]
    },
)
assert [message.id for message in state["messages"]] == ["placeholder"]
```

- [x] **步骤 3: 编写标量字段和嵌套状态合并失败测试**

期望断言：

```python
apply_node_update(
    state,
    {
        "market_report": "market report",
        "market_tool_call_count": 1,
        "investment_debate_state": {
            "history": "\nBull Analyst: text",
            "bull_history": "\nBull Analyst: text",
            "bear_history": "",
            "current_response": "Bull Analyst: text",
            "count": 1,
        },
    },
)

assert state["market_report"] == "market report"
assert state["market_tool_call_count"] == 1
assert state["investment_debate_state"]["current_response"].startswith("Bull")
assert state["investment_debate_state"]["count"] == 1
```

- [x] **步骤 4: 实现状态工厂和更新应用逻辑**

实现：

- `create_stock_initial_state(...)`
- `apply_node_update(state, update)`
- `validate_final_state(state)`

`validate_final_state()` 必须要求最终状态包含：

- `investment_plan`
- `trader_investment_plan`
- `final_trade_decision`
- `performance_metrics`

- [x] **步骤 5: 运行状态测试**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/flow/state/test.py -q
```

期望：全部测试通过。

## 任务 4: 工具清单和工具执行器对齐

**规格覆盖：** 旧 `ToolNode` 工具清单；工具执行当前 `AIMessage` 工具调用；禁止用原生辅助函数替代。

**文件：**

- 新增或修改： `backend/app/services/research/agent/flow/stages/analysts.py`
- 测试： `backend/tests/regression/research/agent/flow/tools/test.py`

- [x] **步骤 1: 编写工具清单失败测试**

期望工具名：

```python
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
```

- [x] **步骤 2: 编写工具执行器执行失败测试**

使用一个带 `tool_call` 的 `AIMessage` 和假的工具包可调用对象。

期望断言：

```python
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
assert len(update["messages"]) == 1
assert isinstance(update["messages"][0], ToolMessage)
assert update["messages"][0].tool_call_id == "call-1"
```

- [x] **步骤 3: 实现 `ToolInventory` 和 `ToolRunner`**

实现必须从 `context.toolkit` 构造可调用对象列表。

不得导入或调用：

- `lookup_market_snapshot`
- `_load_news`
- `_market_report`
- `_fundamentals_report`
- `_news_report`
- `_sentiment_report`
- `_decision`

- [x] **步骤 4: 运行工具清单测试**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/flow/tools/test.py -q
```

期望：全部测试通过。

## 任务 5: 条件边对齐

**规格覆盖：** 所有 `ConditionalLogic` 函数和条件目标名称。

**文件：**

- 新增或修改： `backend/app/services/research/agent/flow/stages/analysts.py`
- 新增或修改： `backend/app/services/research/agent/flow/stages/research.py`
- 新增或修改： `backend/app/services/research/agent/flow/stages/risk.py`
- 测试： `backend/tests/regression/research/agent/flow/conditions/test.py`

- [x] **步骤 1: 编写条件夹具测试**

每个条件都要对比旧实现和新实现结果：

```python
old = ConditionalLogic(max_debate_rounds=1, max_risk_discuss_rounds=1)
new = WorkflowConditionAdapter(old)

assert new.should_continue_market(market_state) == old.should_continue_market(market_state)
assert new.should_continue_social(social_state) == old.should_continue_social(social_state)
assert new.should_continue_news(news_state) == old.should_continue_news(news_state)
assert new.should_continue_fundamentals(fundamentals_state) == old.should_continue_fundamentals(fundamentals_state)
assert new.should_continue_debate(debate_state) == old.should_continue_debate(debate_state)
assert new.should_continue_risk_analysis(risk_state) == old.should_continue_risk_analysis(risk_state)
```

夹具必须覆盖：

- 无工具调用 -> 清理节点
- 工具调用未达到上限 -> 工具节点
- 报告长度大于 100 -> 清理节点
- 工具调用次数达到上限 -> 清理节点
- 辩论计数低于和达到上限
- 风险计数低于和达到上限
- `latest_speaker` 取值 `Risky`、`Safe`、`Neutral`、空字符串

- [x] **步骤 2: 实现条件适配器**

优先直接复用 `trader.graph.conditions.ConditionalLogic`，不要重新手写逻辑。若确实无法直接复用，必须用逐行等价测试锁定复制行为。

- [x] **步骤 3: 运行条件测试**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/flow/conditions/test.py -q
```

期望：全部测试通过。

## 任务 6: 分析师阶段执行器

**规格覆盖：** 市场、情绪、新闻、基本面角色节点；工具循环；消息清理；选中分析师顺序；阶段事件和节点事件。

**文件：**

- 新增或修改： `backend/app/services/research/agent/flow/stages/analysts.py`
- 新增或修改： `backend/app/services/research/agent/flow/events.py`
- 测试： `backend/tests/regression/research/agent/flow/runner/test.py`

- [x] **步骤 1: 编写假分析师循环测试**

使用假处理器：

- 第一次 `Market Analyst` 返回带工具调用的 `AIMessage`
- `tools_market` 返回 `ToolMessage`
- 第二次 `Market Analyst` 返回长度大于 100 的 `market_report`
- `Msg Clear Market` 返回 `RemoveMessages` 和 placeholder

期望节点顺序：

```python
assert recorder.nodes == [
    "Market Analyst",
    "tools_market",
    "Market Analyst",
    "Msg Clear Market",
]
assert state["market_report"].startswith("M" * 101)
assert state["market_tool_call_count"] == 1
assert len(state["messages"]) == 1
assert isinstance(state["messages"][0], HumanMessage)
```

- [x] **步骤 2: 编写选中分析师链路测试**

使用选中分析师 `["market", "news"]`。

期望节点顺序：

```python
assert recorder.nodes == [
    "Market Analyst",
    "Msg Clear Market",
    "News Analyst",
    "Msg Clear News",
]
assert next_node == "Bull Researcher"
```

- [x] **步骤 3: 实现 `AnalystStageRunner`**

方法：

- `run_agent(key, state)`
- `run_tools(key, state)`
- `clear_messages(key, state)`
- `run_selected_analysts(state, plan)`

必须使用旧 factories：

- `create_market_analyst(context.quick_llm, context.toolkit)`
- `create_social_media_analyst(context.quick_llm, context.toolkit)`
- `create_news_analyst(context.quick_llm, context.toolkit)`
- `create_fundamentals_analyst(context.quick_llm, context.toolkit)`
- `create_msg_delete()`

- [x] **步骤 4: 运行分析师执行器测试**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/flow/runner/test.py::test_analyst_stage_runner_tool_loop -q
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/flow/runner/test.py::test_analyst_stage_runner_selected_order -q
```

期望：两个测试都通过。

## 任务 7: 研究辩论执行器

**规格覆盖：** 多头/空头循环；`should_continue_debate`；研究经理；`investment_plan`；辩论状态字段。

**文件：**

- 新增： `backend/app/services/research/agent/flow/stages/research.py`
- 测试： `backend/tests/regression/research/agent/flow/runner/test.py`

- [x] **步骤 1: 编写假辩论循环测试**

当 `max_debate_rounds=1` 时，期望顺序：

```python
assert recorder.nodes == [
    "Bull Researcher",
    "Bear Researcher",
    "Research Manager",
]
assert state["investment_debate_state"]["count"] == 2
assert state["investment_debate_state"]["bull_history"].startswith("\nBull Analyst:")
assert state["investment_debate_state"]["bear_history"].startswith("\nBear Analyst:")
assert state["investment_debate_state"]["judge_decision"] == "investment plan"
assert state["investment_plan"] == "investment plan"
```

- [x] **步骤 2: 实现 `ResearchDebateRunner`**

方法：

- `run_bull(state)`
- `run_bear(state)`
- `run_manager(state)`
- `run_until_manager(state)`

必须使用旧 factories：

- `create_bull_researcher(context.quick_llm, context.bull_memory)`
- `create_bear_researcher(context.quick_llm, context.bear_memory)`
- `create_research_manager(context.deep_llm, context.invest_judge_memory)`

- [x] **步骤 3: 运行研究辩论测试**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/flow/runner/test.py::test_research_debate_runner_matches_old_loop -q
```

期望：通过。

## 任务 8: 交易员、风险辩论和最终决策执行器

**规格覆盖：** 交易员；激进/保守/中性循环；风险裁判；组合经理；风险别名字段；最终风险节点选择。

**文件：**

- 新增： `backend/app/services/research/agent/flow/stages/trader.py`
- 新增： `backend/app/services/research/agent/flow/stages/risk.py`
- 新增： `backend/app/services/research/agent/flow/stages/decision.py`
- 测试： `backend/tests/regression/research/agent/flow/runner/test.py`

- [x] **步骤 1: 编写交易员测试**

期望断言：

```python
runner.run_trader(state)
assert recorder.nodes[-1] == "Trader"
assert state["trader_investment_plan"] == "trader plan"
assert state["sender"] == "Trader"
```

- [x] **步骤 2: 编写风险循环测试**

当 `max_risk_discuss_rounds=1` 时，期望顺序：

```python
assert recorder.nodes == [
    "Risky Analyst",
    "Safe Analyst",
    "Neutral Analyst",
    "Risk Judge",
]
assert state["risk_debate_state"]["count"] == 3
assert state["risk_debate_state"]["latest_speaker"] == "Judge"
assert state["risk_debate_state"]["risky_history"].startswith("\nRisky Analyst:")
assert state["risk_debate_state"]["aggressive_history"] == state["risk_debate_state"]["risky_history"]
assert state["risk_debate_state"]["safe_history"].startswith("\nSafe Analyst:")
assert state["risk_debate_state"]["conservative_history"] == state["risk_debate_state"]["safe_history"]
assert state["risk_debate_state"]["neutral_history"].startswith("\nNeutral Analyst:")
assert state["final_trade_decision"] == "final decision"
```

- [x] **步骤 3: 编写组合经理最终节点测试**

期望断言：

```python
plan = build_stock_dag_parity_plan(["market"], "portfolio_manager")
runner.run_final(state, plan)
assert recorder.nodes[-1] == "Portfolio Manager"
assert state["risk_debate_state"]["latest_speaker"] == "Judge"
assert state["final_trade_decision"] == "portfolio decision"
```

- [x] **步骤 4: 编写 `include_risk=False` 的执行器绕行测试**

该测试必须证明关闭风险评估时执行器没有运行任何风险节点。

```python
plan = build_stock_dag_parity_plan(
    selected_analysts=["market"],
    final_decision_engine="risk_manager",
    include_risk=False,
)
runner.run_after_trader(state, plan)

assert "Risky Analyst" not in recorder.nodes
assert "Safe Analyst" not in recorder.nodes
assert "Neutral Analyst" not in recorder.nodes
assert "Risk Judge" not in recorder.nodes
assert "Portfolio Manager" not in recorder.nodes
assert recorder.edges[-1] == ("Trader", "END")
assert "risk_management_decision" not in state.get("reports", {})
```

- [x] **步骤 5: 实现阶段执行器**

使用旧 factories：

- `create_trader(context.quick_llm, context.trader_memory)`
- `create_risky_debator(context.quick_llm)`
- `create_safe_debator(context.quick_llm)`
- `create_neutral_debator(context.quick_llm)`
- `create_risk_manager(context.deep_llm, context.risk_manager_memory)`
- `create_portfolio_manager(context.deep_llm)`

- [x] **步骤 6: 运行交易员/风险测试**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/flow/runner/test.py::test_trader_runner_updates_state -q
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/flow/runner/test.py::test_risk_debate_runner_matches_old_loop -q
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/flow/runner/test.py::test_portfolio_manager_final_node -q
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/flow/runner/test.py::test_include_risk_false_bypasses_risk_nodes -q
```

期望：全部通过。

## 任务 9: 运行时收尾钩子、计时、记忆、信号和检查点

**规格覆盖：** `propagate()` 运行时语义；`_resolve_pending_entries`；`get_past_context`；`node_timings`；`_build_performance_data`；`_log_state`；`memory_log.store_decision`；`process_signal`；检查点行为。

**文件：**

- 新增或修改： `backend/app/services/research/agent/flow/runner.py`
- 新增或修改： `backend/app/services/research/agent/flow/checkpoint.py`
- 测试： `backend/tests/regression/research/agent/flow/checkpoint/test.py`
- 测试： `backend/tests/regression/research/agent/flow/integration/test.py`

- [x] **步骤 1: 编写计时和性能测试**

期望 `performance_metrics` 字段：

```python
metrics = state["performance_metrics"]
assert metrics["node_count"] == len(metrics["node_timings"])
assert set(metrics["category_timings"]) == {
    "analyst_team",
    "tool_calls",
    "message_clearing",
    "research_team",
    "trader_team",
    "risk_management_team",
    "other",
}
assert metrics["llm_config"]["provider"] == config.get("llm_provider", "unknown")
```

- [x] **步骤 2: 编写记忆和信号测试**

期望断言：

```python
assert memory_log.get_past_context_called_with == "600519"
assert memory_log.store_decision_called_with == {
    "ticker": "600519",
    "trade_date": "2026-06-12",
    "final_trade_decision": state["final_trade_decision"],
}
assert result.decision["model_info"].startswith("FakeDeepLLM")
assert {"action", "confidence", "risk_score", "target_price", "reasoning"} <= set(result.decision)
```

- [x] **步骤 3: 编写检查点守卫测试**

如果本里程碑不完整实现适配器：

```python
with pytest.raises(UnsupportedCheckpointError):
    StockDagParityWorkflow(context_with_checkpoint_enabled).run()
```

如果实现适配器：

```python
assert adapter.thread_id == thread_id("600519", "2026-06-12")
assert adapter.resume_step == checkpoint_step(data_cache_dir, "600519", "2026-06-12")
```

合并前必须二选一：完整实现或显式不支持。禁止检查点被忽略但静默成功。

- [x] **步骤 4: 实现 `StockDagParityWorkflow.run()` 收尾钩子**

收尾顺序：

1. 确保最终状态存在。
2. 附加 `performance_metrics`。
3. 保存 `context.curr_state`。
4. 通过 `StateLogAdapter` 写入状态日志。
5. 通过 `WorkflowMemoryAdapter` 保存最终决策。
6. 通过 `DecisionAdapter` 处理信号。
7. 返回 `StockDagParityWorkflowResult(state, decision, events, task_id)`。

- [x] **步骤 5: 运行运行时测试**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/flow/checkpoint/test.py -q
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/flow/integration/test.py::test_finish_hooks_match_old_runtime_contract -q
```

期望：全部通过。

## 任务 10: 报告提取和持久化对齐

**规格覆盖：** `build_analysis_result`；报告键；顶层结果字段；报告文件；来源；`/reports/view/{task_id}` 兼容性。

**文件：**

- 新增： `backend/app/services/research/agent/flow/stages/reports.py`
- 测试： `backend/tests/regression/research/agent/flow/reports/test.py`

- [x] **步骤 1: 编写报告提取对齐测试**

构造所有报告字段长度都大于 10 的最终状态。

期望报告键：

```python
assert set(result["reports"]) == {
    "market_report",
    "sentiment_report",
    "news_report",
    "fundamentals_report",
    "investment_plan",
    "trader_investment_plan",
    "final_trade_decision",
    "bull_researcher",
    "bear_researcher",
    "research_team_decision",
    "risky_analyst",
    "safe_analyst",
    "neutral_analyst",
    "risk_management_decision",
}
```

期望顶层字段：

```python
for key in [
    "analysis_id",
    "stock_code",
    "stock_symbol",
    "analysis_date",
    "summary",
    "recommendation",
    "confidence_score",
    "risk_level",
    "key_points",
    "detailed_analysis",
    "execution_time",
    "tokens_used",
    "state",
    "analysts",
    "research_depth",
    "reports",
    "decision",
    "model_info",
    "performance_metrics",
]:
    assert key in result
```

- [x] **步骤 2: 编写来源和持久化测试**

期望持久化报告：

```python
assert report_doc["source"] == "agent_workflow_dag_parity"
assert report_doc["task_id"] == task_id
assert report_doc["user_id"] == context.principal.user_id
assert report_doc["reports"]["final_trade_decision"] == state["final_trade_decision"]
```

- [x] **步骤 3: 编写报告文件兼容性测试**

期望生成的报告产物文件名：

```python
assert set(report_files) >= {
    "market_report.md",
    "sentiment_report.md",
    "news_report.md",
    "fundamentals_report.md",
    "investment_plan.md",
    "trader_investment_plan.md",
    "final_trade_decision.md",
    "research_team_decision.md",
    "risk_management_decision.md",
    "analysis_metadata.json",
}
```

`analysis_metadata.json` 内容必须包含：

```python
assert metadata["source"] == "agent_workflow_dag_parity"
assert metadata["task_id"] == task_id
assert metadata["stock_code"] == "600519"
assert metadata["analysis_date"] == "2026-06-12"
```

- [x] **步骤 4: 实现报告适配器**

使用 `app.services.analysis.simple.result.build_analysis_result()` 做提取。如果持久化需要调用现有辅助函数，只能在确认它会保留 `source = "agent_workflow_dag_parity"` 后调用。

- [x] **步骤 5: 运行报告测试**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/flow/reports/test.py -q
```

期望：全部测试通过。

## 任务 11: 智能体事件和右侧栏节点/阶段语义

**规格覆盖：** 节点事件；阶段事件；当前执行尝试轨迹；工具节点和清理节点可审计，但界面可以折叠显示。

**文件：**

- 新增或修改： `backend/app/services/research/agent/flow/events.py`
- 修改： `backend/app/services/research/agent/stage.py`
- 测试： `backend/tests/regression/research/agent/flow/integration/test.py`

- [x] **步骤 1: 编写节点事件测试**

期望事件结构：

```python
assert event["event_type"] == "stock_analysis.node"
assert event["node"] == "Bull Researcher"
assert event["stage"] == "research_debate"
assert event["status"] in {"running", "completed", "failed", "skipped"}
assert event["edge_from"] == "Msg Clear Fundamentals"
assert event["edge_to"] == "Bear Researcher"
assert event["task_id"] == task_id
assert event["analysis_id"] == analysis_id
assert event["attempt_id"] == attempt_id
```

- [x] **步骤 2: 编写阶段聚合测试**

期望阶段包含：

```python
assert [stage["stage"] for stage in stage_events] == [
    "validate_input",
    "prepare_state",
    "market_analysis",
    "sentiment_analysis",
    "news_analysis",
    "fundamentals_analysis",
    "research_debate",
    "research_manager",
    "trader_decision",
    "risk_debate",
    "final_risk_decision",
    "report_generation",
    "agent_summary",
]
```

- [x] **步骤 3: 编写跳过阶段事件测试**

使用选中分析师 `["market"]`，验证被省略的分析师会产生明确的跳过阶段事件，且不会伪造报告内容：

```python
assert {"sentiment_analysis", "news_analysis", "fundamentals_analysis"} <= {
    event["stage"] for event in stage_events if event["status"] == "skipped"
}
assert "sentiment_report" not in result.report["reports"]
assert "news_report" not in result.report["reports"]
assert "fundamentals_report" not in result.report["reports"]
assert all("native" not in event.get("message", "").lower() for event in stage_events)
```

当请求载荷包含 `include_risk=False` 时，验证风险阶段被跳过：

```python
assert any(
    event["stage"] == "risk_debate" and event["status"] == "skipped"
    for event in stage_events
)
assert "risk_management_decision" not in result.report["reports"]
```

- [x] **步骤 4: 实现事件发射器**

事件发射器必须：

- 发出节点运行中、已完成、失败状态
- 发出边元数据
- 收集 `report_keys_added`
- 按节点映射发出阶段状态
- 保持事件只属于当前执行尝试 `attempt_id`
- 对被省略的分析师阶段和风险阶段发出跳过阶段事件，但不得伪造报告字段

- [x] **步骤 5: 运行事件测试**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/flow/integration/test.py::test_node_and_stage_events_are_attempt_scoped -q
```

期望：通过。

## 任务 12: 替换智能体单股分析默认路径

**规格覆盖：** 默认路径必须是 DAG 对齐工作流；原生路径隔离；禁止回归；任务和报告链接。

**文件：**

- 修改： `backend/app/services/research/agent/stock.py`
- 修改： `backend/app/services/research/agent/native.py`
- 修改： `backend/app/services/research/agent/tools/analysis.py`
- 测试： `backend/tests/regression/research/agent/analysis/test.py`

- [x] **步骤 1: 编写禁止默认路径回退测试**

用 monkeypatch 让 `run_native_stock_workflow` 抛错：

```python
def fail_native(*args, **kwargs):
    raise AssertionError("native workflow must not be default")
```

期望：

```python
result = await StockAnalysisWorkflow(context).run_single(payload)
assert result["source"] == "agent_workflow_dag_parity"
assert result["links"]["report"] == f"/reports/view/{result['task_id']}"
```

- [x] **步骤 2: 编写直接工具调用测试**

期望：

```python
result = await stock_analysis_tool.run(context, {"mode": "single", "symbol": "600519"})
assert result["tool"] == "stock_analysis"
assert result["mode"] == "single"
assert result["status"] == "completed"
assert result["source"] == "agent_workflow_dag_parity"
```

- [x] **步骤 3: 修改 `StockAnalysisWorkflow.run_single()`**

流程：

1. 使用现有辅助函数归一化标的、市场和模型配置。
2. 构建 `AnalysisParameters`。
3. 创建或绑定 `task_id`。
4. 构建 `StockWorkflowContext`。
5. 运行 `StockDagParityWorkflow`。
6. 持久化报告。
7. 返回已完成或失败状态和链接。

- [x] **步骤 4: 更新工具描述**

确保工具元数据明确说明它运行智能体 DAG 对齐工作流，不是原生摘要，也不是提交到旧队列。

- [x] **步骤 5: 运行智能体分析测试**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/analysis/test.py -q
```

期望：测试通过。

## 任务 13: 假 LLM / 假工具端到端工作流

**规格覆盖：** 最小真实链路；所有节点；报告；事件；`/reports/view/{task_id}`。

**文件：**

- 测试： `backend/tests/regression/research/agent/flow/integration/test.py`

- [x] **步骤 1: 编写完整工作流集成测试**

使用假 LLM 响应和假工具，确保不需要网络或 BaoStock 调用。

期望：

```python
result = await workflow.run()

assert result.status == "completed"
assert result.source == "agent_workflow_dag_parity"
assert result.state["market_report"]
assert result.state["sentiment_report"]
assert result.state["news_report"]
assert result.state["fundamentals_report"]
assert result.state["investment_plan"]
assert result.state["trader_investment_plan"]
assert result.state["final_trade_decision"]
assert result.report["reports"]["risk_management_decision"]
assert result.node_events
assert result.stage_events
```

- [x] **步骤 2: 断言完整节点顺序**

完整默认配置下的期望顺序：

```python
assert result.node_names == [
    "Market Analyst",
    "Msg Clear Market",
    "Sentiment Analyst",
    "Msg Clear Social",
    "News Analyst",
    "Msg Clear News",
    "Fundamentals Analyst",
    "Msg Clear Fundamentals",
    "Bull Researcher",
    "Bear Researcher",
    "Research Manager",
    "Trader",
    "Risky Analyst",
    "Safe Analyst",
    "Neutral Analyst",
    "Risk Judge",
    "END",
]
```

当假分析师返回工具调用时，期望顺序必须在分析师调用之间包含 `tools_*`。

- [x] **步骤 3: 运行集成测试**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/flow/integration/test.py -q
```

期望：通过。

## 任务 14: 防简化回归守卫

**规格覆盖：** 默认路径不得回退到原生实现；不得退回五段报告简化实现；不得走旧队列或工作进程；不得直接 `propagate()`。

**文件：**

- 修改： `backend/tests/regression/research/agent/analysis/test.py`
- 测试： `backend/tests/regression/research/agent/flow/integration/test.py`

- [x] **步骤 1: 增加源码扫描守卫**

测试扫描智能体股票分析工作流模块，遇到禁用调用就失败：

```python
for path in workflow_source_files:
    source = path.read_text()
    assert "TradingAgentsGraph(" not in source
    assert ".propagate(" not in source
    assert ".workflow.compile(" not in source
    assert "run_native_stock_workflow(" not in source
```

- [x] **步骤 2: 增加报告完整性守卫**

期望：

```python
assert len(result.report["reports"]) >= 14
assert "bull_researcher" in result.report["reports"]
assert "risk_management_decision" in result.report["reports"]
```

- [x] **步骤 3: 运行回归守卫测试**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/analysis/test.py backend/tests/regression/research/agent/flow/integration/test.py -q
```

期望：通过。

## 任务 15: 文档、工具提示词和操作说明

**规格覆盖：** 实施交接说明；提示词和工具描述；报告来源；已知非目标。

**文件：**

- 修改： `backend/app/services/research/agent/tools/analysis.py`
- 修改： `docs/superpowers/specs/stock.md`，仅当索引需要更新计划引用。
- 新增或修改： `docs/superpowers/execution/agent-stock-workflow-dag-parity.md`

- [x] **步骤 1: 增加执行说明**

记录：

- 默认来源是 `agent_workflow_dag_parity`
- 旧 DAG 仍存在，旧单股页面仍使用旧路径
- 智能体工作流不调用 `TradingAgentsGraph.propagate()`
- 原生工作流不是默认路径
- 检查点行为要么已实现，要么在启用时显式阻断

- [x] **步骤 2: 更新工具提示词和描述**

工具描述必须说明：

```text
stock_analysis 运行智能体单股分析工作流；该工作流复刻原 TradingAgents DAG 的节点、工具、辩论、风险评审和报告 schema。它不提交到旧 analysis queue，也不使用简化 native workflow。
```

- [x] **步骤 3: 运行 doc/link 检查**

运行：

```bash
rg -n "agent_native|run_native_stock_workflow|agent_workflow_dag_parity|TradingAgentsGraph\\.propagate|flow" docs backend/app/services/research/agent
```

期望：

- `agent_native` 只出现在废弃、后备路径或禁止回归语境。
- `agent_workflow_dag_parity` 出现在报告持久化和文档中。
- `TradingAgentsGraph.propagate` 只在文档、规格或测试中作为禁用项或基线引用出现。

## 任务 16: 验证门

**规格覆盖：** 全部对齐测试；聚焦智能体测试；无格式问题。

**文件：**

- 除非测试暴露失败，否则不需要修改源文件。

- [x] **步骤 1: 运行股票工作流对齐测试组**

运行：

```bash
PYTHONPATH=backend python -m pytest backend/tests/regression/research/agent/flow -q
```

期望：通过。

- [x] **步骤 2: 运行现有图基线测试**

运行：

```bash
PYTHONPATH=backend python -m pytest \
  backend/tests/trader/graph/analysts/test.py \
  backend/tests/trader/graph/conditions/test.py \
  backend/tests/trader/graph/propagation/test.py \
  backend/tests/trader/graph/setup/test.py \
  backend/tests/trader/graph/signals/test.py \
  backend/tests/trader/graph/trading/test.py \
  -q
```

期望：通过。

- [x] **步骤 3: 运行聚焦智能体回归测试**

运行：

```bash
PYTHONPATH=backend python -m pytest \
  backend/tests/regression/research/agent/analysis/test.py \
  backend/tests/regression/research/agent/routes/test.py \
  backend/tests/regression/research/agent/permissions/test.py \
  -q
```

期望：通过。

- [x] **步骤 4: 运行本仓库使用的格式和静态检查**

运行仓库当前后端检查。如果确切命令已经变化，检查 `backend/pyproject.toml` 并使用已配置命令。

最低期望命令：

```bash
cd backend
python -m ruff check app tests trader
python -m pyright app trader
```

期望：通过；如果失败，只能是已明确记录文件路径的既存无关失败。

执行结果：

- 新增/修改范围 ruff 已通过。
- `python -m pyright app trader` 退出码为 0，但存在既存警告。
- 全量 `python -m ruff check app tests trader` 失败在既存 `trader/factors/zoo/...` 大量未使用导入 / 变量名问题，不属于本次 DAG 对齐工作流改动。

## 规格覆盖矩阵

| 规格要求 | 规划任务 |
| --- | --- |
| 不调用 `TradingAgentsGraph.propagate()` / 不使用已编译 LangGraph | 任务 12、14 |
| 不走旧队列或工作进程主路径 | 任务 12、14 |
| 复用旧节点处理器工厂 | 任务 6、7、8 |
| 复用旧状态结构 | 任务 3 |
| 重建普通边和条件边 | 任务 1、5 |
| 完整报告键 | 任务 10 |
| 复用或等价实现 `build_analysis_result()` | 任务 10 |
| 移除原生默认路径 | 任务 12、14 |
| `ToolNode` 工具清单对齐 | 任务 4 |
| 运行时配置对齐 | 任务 2、9 |
| 节点处理器状态更新语义 | 任务 3、6、7、8 |
| 上下文组件快/深 LLM、工具包、记忆和信号 | 任务 2 |
| 初始状态对齐 | 任务 3 |
| `propagate()` 运行时收尾行为 | 任务 9 |
| 检查点行为 | 任务 9 |
| 报告持久化和 `/reports/view/{task_id}` | 任务 10、13 |
| 节点和阶段事件 | 任务 11 |
| 禁止回归测试 | 任务 14 |
| 最小假对象完整工作流 | 任务 13 |
| 保留现有旧 DAG | 任务 12、14、16 |

## 自审清单

- [x] 每个旧 DAG 节点都有对应任务：Market、tools_market、Msg Clear Market、Sentiment、tools_social、Msg Clear Social、News、tools_news、Msg Clear News、Fundamentals、tools_fundamentals、Msg Clear Fundamentals、Bull、Bear、Research Manager、Trader、Risky、Safe、Neutral、Risk Judge、Portfolio Manager、END。
- [x] 每条旧普通边都有图计划测试。
- [x] 每条旧条件边都有条件夹具测试。
- [x] 每个旧 `ToolNode` 可调用对象都出现在 `ToolInventory` 测试中。
- [x] 每个旧角色记忆组件都出现在上下文测试中。
- [x] 每个辩论/风险状态控制字段都出现在状态合并测试中。
- [x] 每个报告键都出现在报告对齐测试中。
- [x] 每个顶层 `build_analysis_result()` 字段都出现在报告对齐测试中。
- [x] 运行时收尾钩子覆盖性能、状态日志、记忆日志、信号处理和检查点。
- [x] 智能体默认路径不能静默回退到原生工作流。
- [x] 验证命令包含新增对齐测试和现有图基线测试。
