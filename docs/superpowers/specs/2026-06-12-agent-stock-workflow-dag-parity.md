# 研究 Agent 单股分析 Workflow 完整复刻 DAG 规格说明

日期：2026-06-12

## 结论先行

本规格的目标是：**在研究 Agent 内实现一套新的单股分析 workflow，完整复刻原 TradingAgents LangGraph DAG 的功能、节点顺序、条件边、状态字段和报告生成格式，但不得在 Agent workflow 中直接调用旧 DAG 的 `TradingAgentsGraph.propagate()` 或 compiled LangGraph。**

这不是以下方案：

- 不是把 Agent 工具改回旧 DAG 队列提交。
- 不是在 Agent 内调用 `TradingAgentsGraph.propagate()`。
- 不是继续使用当前 `agent_native` 简化分析。
- 不是只生成 `market_report`、`fundamentals_report`、`news_report`、`sentiment_report`、`final_trade_decision` 五段报告。
- 不是用一个最终 LLM prompt 汇总替代原 DAG 的多角色辩论。

正确方向是：**用新的 workflow runner 显式执行旧 DAG 中每一个节点对应的 node handler，按旧 DAG 的边和条件边推进状态，并复用旧报告抽取与保存契约。**

## 背景与问题

当前 Agent 单股分析走 `backend/app/services/research/agent/native.py` 的 `run_native_stock_workflow`。这条路径只做行情快照、简单收益指标、基础信息、新闻缓存和一个确定性 `_decision()`，并写入 `source = "agent_native"` 的简化报告。

这与原 DAG 报告差距很大。原 DAG 会运行：

- 分析师阶段：Market / Sentiment / News / Fundamentals。
- 投资研究辩论：Bull Researcher / Bear Researcher / Research Manager。
- 交易计划：Trader。
- 风险辩论：Risky / Safe / Neutral。
- 最终风险裁决：Risk Judge 或 Portfolio Manager。
- 报告抽取：从 `AgentState` 和 debate state 中提取完整报告字段。

因此当前实现属于错误方向：它没有复刻原 DAG，只是写了一套简化 workflow。

## 文档取代关系

本规格取代旧的 `docs/superpowers/specs/stock.md` 中关于单股分析 workflow 迁移的具体方案。旧文件已经改为索引和废弃说明，不再作为实现依据。

本规格不是“再补一份说明”，而是后续实现的准入契约。任何计划、任务拆分或代码实现，如果没有逐项满足本规格中的节点映射、边映射、状态契约和报告契约，都不能进入开发。

## 旧 DAG、当前 workflow、目标 workflow 三者关系

| 项目 | 旧 DAG | 当前 Agent workflow | 目标 Agent workflow |
| --- | --- | --- | --- |
| 主入口 | `TradingAgentsGraph.propagate()` | `StockAnalysisWorkflow.run_single()` -> `run_native_stock_workflow()` | `StockAnalysisWorkflow.run_single()` -> `StockDagParityWorkflow.run()` |
| 执行器 | LangGraph compiled graph | 手写简化函数 | 手写 DAG parity runner |
| 是否可在 Agent 中调用 | 不允许作为 Agent 主执行器 | 当前正在调用，必须移除 | 必须调用 |
| 节点粒度 | 每个 analyst/tool/clear/research/risk 都是节点 | 只有粗粒度 stage | 必须还原每个旧 DAG 节点 |
| 边语义 | `add_edge` + `add_conditional_edges` | 无完整边模型 | 必须显式建模普通边和条件边 |
| 条件判断 | `ConditionalLogic` | 基本没有等价逻辑 | 必须逐函数等价 |
| 状态结构 | `AgentState` + debate state | 自定义 report dict 和 snapshot | 必须兼容 `AgentState` |
| 报告抽取 | `build_analysis_result()` | 手写简化 `reports` | 必须复用或等价复刻 `build_analysis_result()` |
| 报告字段数量 | 完整配置约 14 个字段 | 约 5 个字段 | 与旧 DAG 完整配置一致 |
| 进度语义 | LangGraph stream node chunk | 自造 stage event | stage event + node event 双层记录 |
| 正确性判定 | final state + decision | completed 即写报告 | final state、decision、reports、node events 全部通过 parity 测试 |

当前 workflow 不能通过“继续补几个报告段落”修好。它缺失的是 DAG 的执行模型：node handler、tool loop、condition routing、debate loop、risk loop 和 final state extraction。因此实现必须从 DAG parity runner 开始，而不是在 `native.py` 上继续加 if/else。

## 硬性要求

1. Agent workflow 必须独立运行，不得调用 `TradingAgentsGraph.propagate()`。
2. Agent workflow 不得调用旧 analysis queue/worker 作为主执行路径。
3. Agent workflow 必须复用旧 DAG 的 node handler 工厂，例如 `create_market_analyst`、`create_bull_researcher`、`create_trader`、`create_risk_manager`。
4. Agent workflow 必须复用旧 DAG 的状态结构，包括 `AgentState`、`investment_debate_state`、`risk_debate_state`。
5. Agent workflow 必须按旧 DAG 边和条件边推进，不能用简化顺序替代。
6. Agent workflow 必须生成与旧 DAG 等价的 `analysis_reports.reports` 字段集合。
7. Agent workflow 必须复用 `build_analysis_result()` 或抽取出同等逻辑，不能重新定义报告字段。
8. `agent_native` 当前简化报告逻辑必须从单股分析主路径移除或降级为明确不可用 fallback；默认路径不得再写 `source = "agent_native"` 的简化报告。
9. 任一旧 DAG 节点或边没有映射到新 workflow，实施计划不得开始。
10. 任一报告字段缺失，验收不得通过。
11. 任一旧 ToolNode 绑定工具没有进入新 workflow 的 tool inventory，验收不得通过。
12. `checkpoint_enabled`、`selected_analysts` 顺序、`final_decision_engine`、`max_debate_rounds`、`max_risk_discuss_rounds` 等旧 DAG 配置项必须有显式等价实现或显式阻断错误；不得静默降级。

## 术语

- **旧 DAG**：`backend/trader/graph/setup.py` 使用 `StateGraph(AgentState)` 构建的 LangGraph DAG，以及 `TradingAgentsGraph.propagate()` 的运行路径。
- **新 workflow**：研究 Agent 内的新执行器，负责按旧 DAG 语义执行节点和条件边，但不编译或调用 LangGraph。
- **节点 handler**：旧 DAG 中 `workflow.add_node(...)` 绑定的 Python callable。
- **条件边**：旧 DAG 中 `workflow.add_conditional_edges(...)` 绑定的判断函数和目标节点。
- **报告契约**：`backend/app/services/analysis/simple/result.py::build_analysis_result()` 从 final state 抽取出的报告字段和最终 decision 结构。

## 原 DAG 的节点与边

原 DAG 的图构建位置：

- `backend/trader/graph/setup.py::GraphSetup.setup_graph`
- `backend/trader/graph/conditions.py::ConditionalLogic`
- `backend/trader/graph/propagation.py::Propagator.create_initial_state`

旧 DAG 的实际运行位置：

- `backend/trader/graph/trading/base.py::TradingAgentsGraph.propagate`

旧 DAG 的报告抽取位置：

- `backend/app/services/analysis/simple/result.py::build_analysis_result`
- `backend/app/services/analysis/simple/reports.py`

旧 DAG 的运行不是只有 `setup_graph()`。完整行为由以下部分共同定义：

1. `GraphSetup.setup_graph()` 定义节点和边。
2. `Propagator.create_initial_state()` 定义初始 state。
3. `ConditionalLogic` 定义条件边。
4. `TradingAgentsGraph.propagate()` 定义 stream、进度、性能统计、final state、decision 处理和 memory 写入。
5. `build_analysis_result()` 定义 reports 字段抽取。
6. reports 保存层定义报告文件名和报告页兼容格式。

新 workflow 必须覆盖这六类行为。只覆盖第 1 类或第 5 类都不算完整复刻。

### 旧 DAG 节点清单

分析师节点由 `selected_analysts` 动态决定，但每个被选择的分析师都会产生三个节点：

| 旧 DAG 节点 | 旧 node handler / 来源 | 旧 state 输出 | 新 workflow 对应 component |
| --- | --- | --- | --- |
| `START` | LangGraph start | 无 | `StockDagParityWorkflow.start()` |
| `Market Analyst` | `create_market_analyst(quick_llm, toolkit)` | `market_report`, `messages`, `market_tool_call_count` | `AnalystStageRunner.run_agent("market")` |
| `tools_market` | `self.tool_nodes["market"]` | tool messages, market data | `AnalystStageRunner.run_tools("market")` |
| `Msg Clear Market` | `create_msg_delete()` | 清理 tool messages | `AnalystStageRunner.clear_messages("market")` |
| `Sentiment Analyst` | `create_social_media_analyst(quick_llm, toolkit)` | `sentiment_report`, `messages`, `sentiment_tool_call_count` | `AnalystStageRunner.run_agent("social")` |
| `tools_social` | `self.tool_nodes["social"]` | tool messages, sentiment/social data | `AnalystStageRunner.run_tools("social")` |
| `Msg Clear Social` | `create_msg_delete()` | 清理 tool messages | `AnalystStageRunner.clear_messages("social")` |
| `News Analyst` | `create_news_analyst(quick_llm, toolkit)` | `news_report`, `messages`, `news_tool_call_count` | `AnalystStageRunner.run_agent("news")` |
| `tools_news` | `self.tool_nodes["news"]` | tool messages, news data | `AnalystStageRunner.run_tools("news")` |
| `Msg Clear News` | `create_msg_delete()` | 清理 tool messages | `AnalystStageRunner.clear_messages("news")` |
| `Fundamentals Analyst` | `create_fundamentals_analyst(quick_llm, toolkit)` | `fundamentals_report`, `messages`, `fundamentals_tool_call_count` | `AnalystStageRunner.run_agent("fundamentals")` |
| `tools_fundamentals` | `self.tool_nodes["fundamentals"]` | tool messages, fundamentals data | `AnalystStageRunner.run_tools("fundamentals")` |
| `Msg Clear Fundamentals` | `create_msg_delete()` | 清理 tool messages | `AnalystStageRunner.clear_messages("fundamentals")` |
| `Bull Researcher` | `create_bull_researcher(quick_llm, bull_memory)` | `investment_debate_state.bull_history`, `history`, `current_response`, `count` | `ResearchDebateRunner.run_bull()` |
| `Bear Researcher` | `create_bear_researcher(quick_llm, bear_memory)` | `investment_debate_state.bear_history`, `history`, `current_response`, `count` | `ResearchDebateRunner.run_bear()` |
| `Research Manager` | `create_research_manager(deep_llm, invest_judge_memory)` | `investment_debate_state.judge_decision`, `investment_plan` | `ResearchDebateRunner.run_manager()` |
| `Trader` | `create_trader(quick_llm, trader_memory)` | `trader_investment_plan` | `TraderDecisionRunner.run_trader()` |
| `Risky Analyst` | `create_risky_debator(quick_llm)` | `risk_debate_state.risky_history`, `current_risky_response`, `latest_speaker`, `count` | `RiskDebateRunner.run_risky()` |
| `Safe Analyst` | `create_safe_debator(quick_llm)` | `risk_debate_state.safe_history`, `current_safe_response`, `latest_speaker`, `count` | `RiskDebateRunner.run_safe()` |
| `Neutral Analyst` | `create_neutral_debator(quick_llm)` | `risk_debate_state.neutral_history`, `current_neutral_response`, `latest_speaker`, `count` | `RiskDebateRunner.run_neutral()` |
| `Risk Judge` | `create_risk_manager(deep_llm, risk_manager_memory)` | `risk_debate_state.judge_decision`, `final_trade_decision` | `RiskDecisionRunner.run_risk_manager()` |
| `Portfolio Manager` | `create_portfolio_manager(deep_llm)` when `final_decision_engine == "portfolio_manager"` | `risk_debate_state.judge_decision`, `final_trade_decision` | `RiskDecisionRunner.run_portfolio_manager()` |
| `END` | LangGraph end | final state | `StockDagParityWorkflow.finish()` |

### 旧 node handler 状态更新契约

新 workflow 不能只按节点名调用 handler，还必须按旧 LangGraph 的 state merge 语义应用每个 handler 返回的 update。特别是 `messages` 必须按 `MessagesState` / `add_messages` 语义合并，`RemoveMessage` 必须删除对应历史消息，不能简单覆盖或拼接字符串。

| 旧 DAG 节点 | 旧 handler 返回 / 修改 | 新 workflow 必须复刻 |
| --- | --- | --- |
| `Market Analyst` | `messages`, `market_report`, `market_tool_call_count` | 合并 AI/tool/final messages；写 `market_report`；按旧 handler 返回值更新计数 |
| `Sentiment Analyst` | `messages`, `sentiment_report`, `sentiment_tool_call_count` | 合并消息；写 `sentiment_report`；按旧 handler 返回值更新计数 |
| `News Analyst` | `messages`, `news_report`, `news_tool_call_count` | 合并消息；写 `news_report`；按旧 handler 返回值更新计数 |
| `Fundamentals Analyst` | `messages` 可选，`fundamentals_report`, `fundamentals_tool_call_count` | 合并消息；写 `fundamentals_report`；注意旧 handler 会根据 `ToolMessage` 数量修正计数，不能只做 `+1` |
| `tools_*` | LangGraph `ToolNode` 生成 `ToolMessage` | 仅执行当前 AIMessage 的 `tool_calls`；把每个工具结果作为 `ToolMessage` 合并到 `messages` |
| `Msg Clear *` | `[RemoveMessage(id=m.id) for m in messages] + [HumanMessage(placeholder)]` | 删除旧 messages，并追加占位 `HumanMessage`，内容包含 `instrument_context` 和 `trade_date` |
| `Bull Researcher` | `investment_debate_state.history += "\nBull Analyst: ..."`, `bull_history += ...`, `current_response = argument`, `count += 1` | 保留 `bear_history`；更新 bull/history/current/count；`current_response` 前缀必须是 `Bull Analyst:`，因为条件边依赖 `startswith("Bull")` |
| `Bear Researcher` | `investment_debate_state.history += "\nBear Analyst: ..."`, `bear_history += ...`, `current_response = argument`, `count += 1` | 保留 `bull_history`；更新 bear/history/current/count；`current_response` 前缀必须是 `Bear Analyst:` |
| `Research Manager` | `investment_debate_state.judge_decision = investment_plan`, `current_response = investment_plan`, `investment_plan` | 保留 bull/bear/history/count；同时写顶层 `investment_plan` |
| `Trader` | `messages: [AIMessage(content=trader_plan)]`, `trader_investment_plan`, `sender = "Trader"` | 合并 trader message；写 `trader_investment_plan`；写 `sender` |
| `Risky Analyst` | `risk_debate_state.history += "\nRisky Analyst: ..."`, `risky_history/aggressive_history += ...`, `latest_speaker = "Risky"`, `current_risky_response/current_aggressive_response = argument`, `count += 1` | 同步 risky/aggressive alias；保留 safe/conservative/neutral；更新 latest/count |
| `Safe Analyst` | `safe_history/conservative_history += ...`, `latest_speaker = "Safe"`, `current_safe_response/current_conservative_response = argument`, `count += 1` | 同步 safe/conservative alias；保留 risky/aggressive/neutral；更新 latest/count |
| `Neutral Analyst` | `neutral_history += ...`, `latest_speaker = "Neutral"`, `current_neutral_response = argument`, `count += 1` | 保留 risky/aggressive/safe/conservative；更新 neutral/latest/count |
| `Risk Judge` | `risk_debate_state.judge_decision = response`, `latest_speaker = "Judge"`, `final_trade_decision = response` | 保留全部风险辩论历史和 alias 字段；写顶层 `final_trade_decision` |
| `Portfolio Manager` | `risk_debate_state.judge_decision = final_trade_decision`, `latest_speaker = "Judge"`, `final_trade_decision` | 与 `Risk Judge` 同等输出契约，handler 不同，配置选择不同 |
| `END` | final state | 进入 `finish()`，执行 performance、state log、memory、signal、report persistence |

验收要求：

- fake node 测试必须断言每个 node update 被按旧 state merge 语义应用。
- `Msg Clear *` 测试必须断言旧消息被 `RemoveMessage` 清除，并生成包含同一 `instrument_context` / `trade_date` 的 placeholder。
- debate/risk loop 测试必须断言 `count`、`current_response`、`latest_speaker` 的值会驱动下一条条件边，不能只断言报告字段存在。

### 旧 ToolNode 工具清单与新 workflow 映射

`tools_*` 不是抽象占位符。旧 DAG 在 `backend/trader/graph/trading/common.py::_create_tool_nodes()` 中为每个 ToolNode 绑定了具体工具。新 workflow 的 `ToolRunner` 必须绑定同一组 callable，名称、顺序和可调用对象都要可测试。

| 旧 ToolNode | 旧绑定工具 | 新 workflow 对应 |
| --- | --- | --- |
| `tools_market` | `get_stock_market_data_unified` | `ToolInventory.market[0]` |
| `tools_market` | `get_yfin_data_online` | `ToolInventory.market[1]` |
| `tools_market` | `get_stockstats_indicators_report_online` | `ToolInventory.market[2]` |
| `tools_market` | `get_yfin_data` | `ToolInventory.market[3]` |
| `tools_market` | `get_stockstats_indicators_report` | `ToolInventory.market[4]` |
| `tools_social` | `get_stock_sentiment_unified` | `ToolInventory.social[0]` |
| `tools_social` | `get_stock_news_openai` | `ToolInventory.social[1]` |
| `tools_social` | `get_reddit_stock_info` | `ToolInventory.social[2]` |
| `tools_news` | `get_stock_news_unified` | `ToolInventory.news[0]` |
| `tools_news` | `get_global_news_openai` | `ToolInventory.news[1]` |
| `tools_news` | `get_google_news` | `ToolInventory.news[2]` |
| `tools_news` | `get_finnhub_news` | `ToolInventory.news[3]` |
| `tools_news` | `get_reddit_news` | `ToolInventory.news[4]` |
| `tools_fundamentals` | `get_stock_fundamentals_unified` | `ToolInventory.fundamentals[0]` |
| `tools_fundamentals` | `get_finnhub_company_insider_sentiment` | `ToolInventory.fundamentals[1]` |
| `tools_fundamentals` | `get_finnhub_company_insider_transactions` | `ToolInventory.fundamentals[2]` |
| `tools_fundamentals` | `get_simfin_balance_sheet` | `ToolInventory.fundamentals[3]` |
| `tools_fundamentals` | `get_simfin_cashflow` | `ToolInventory.fundamentals[4]` |
| `tools_fundamentals` | `get_simfin_income_stmt` | `ToolInventory.fundamentals[5]` |
| `tools_fundamentals` | `get_china_stock_data` | `ToolInventory.fundamentals[6]` |
| `tools_fundamentals` | `get_china_fundamentals` | `ToolInventory.fundamentals[7]` |

验收要求：

- 新 workflow 必须能从 `Toolkit` 构造上述同名 callable。
- `ToolRunner.run_tools(key)` 必须只执行当前 AIMessage 的 `tool_calls`，但可执行工具集合必须与旧 ToolNode 完全一致。
- 不允许用 `lookup_market_snapshot()`、`_load_news()`、snapshot basic info 或其它 native helper 替代旧 ToolNode。
- 静态测试必须比较旧 `_create_tool_nodes()` 工具名集合和新 `ToolInventory` 工具名集合，任一缺失或多出都失败。

### 当前 workflow 差距清单

下表描述“原 DAG 节点”和“当前 workflow”之间的真实差距。后续实现必须把“当前状态”列中的缺失全部补齐。

| 旧 DAG 节点/能力 | 当前 workflow 对应 | 当前状态 | 必须改成 |
| --- | --- | --- | --- |
| `START` | `run_native_stock_workflow()` 创建 `task_id` | 只有 task/report 初始化，没有旧 `AgentState` 初始化 | `StockDagParityWorkflow.start()` 调用 state factory，生成与 `Propagator.create_initial_state()` 等价的 state |
| `Market Analyst` | `_market_report(snapshot, metrics)` | 错误替代：不是旧 analyst node，不会 tool loop，不使用旧 prompt/memory/messages | 调用 `create_market_analyst(...)` 生成的 node handler |
| `tools_market` | `lookup_market_snapshot(...)` | 错误替代：直接取 snapshot，不执行旧 ToolNode | 执行旧 `self.tool_nodes["market"]` 等价 tool runner |
| `Msg Clear Market` | 无 | 缺失 | 调用 `create_msg_delete()` 等价 clear step |
| `Sentiment Analyst` | `_sentiment_report(news)` | 错误替代：只统计新闻 sentiment，不是旧 social media analyst | 调用 `create_social_media_analyst(...)` |
| `tools_social` | 无 | 缺失 | 执行旧 `self.tool_nodes["social"]` 等价 tool runner；不可用时按旧数据源行为失败或跳过 |
| `Msg Clear Social` | 无 | 缺失 | 调用 `create_msg_delete()` 等价 clear step |
| `News Analyst` | `_news_report(news, include_sentiment)` | 错误替代：只列新闻标题，不是旧 news analyst | 调用 `create_news_analyst(...)` |
| `tools_news` | `_load_news(...)` | 错误替代：不是旧 ToolNode | 执行旧 `self.tool_nodes["news"]` 等价 tool runner |
| `Msg Clear News` | 无 | 缺失 | 调用 `create_msg_delete()` 等价 clear step |
| `Fundamentals Analyst` | `_fundamentals_report(snapshot)` | 错误替代：只列 basic_info 字段，不是旧 fundamentals analyst | 调用 `create_fundamentals_analyst(...)` |
| `tools_fundamentals` | snapshot basic info | 错误替代：不是旧 ToolNode，缺少旧工具调用上限语义 | 执行旧 `self.tool_nodes["fundamentals"]` 等价 tool runner |
| `Msg Clear Fundamentals` | 无 | 缺失 | 调用 `create_msg_delete()` 等价 clear step |
| `Bull Researcher` | 无 | 完全缺失 | 调用 `create_bull_researcher(...)` |
| `Bear Researcher` | 无 | 完全缺失 | 调用 `create_bear_researcher(...)` |
| `Research Manager` | 无 | 完全缺失 | 调用 `create_research_manager(...)`，写 `investment_plan` |
| `Trader` | 无 | 完全缺失 | 调用 `create_trader(...)`，写 `trader_investment_plan` |
| `Risky Analyst` | 无 | 完全缺失 | 调用 `create_risky_debator(...)` |
| `Safe Analyst` | 无 | 完全缺失 | 调用 `create_safe_debator(...)` |
| `Neutral Analyst` | 无 | 完全缺失 | 调用 `create_neutral_debator(...)` |
| `Risk Judge` | `_decision(...)` | 错误替代：简单分数模型，不是风险经理裁决 | 调用 `create_risk_manager(...)` |
| `Portfolio Manager` | 无 | 缺失 | 当配置为 portfolio manager 时调用 `create_portfolio_manager(...)` |
| `END` | 手写 insert report | 错误替代：不基于 old final state/report extractor | `finish()` 调 `process_signal` 等价逻辑和 `build_analysis_result()` |

结论：当前 workflow 与旧 DAG 的对应关系不是“已迁移但不完整”，而是“大部分节点缺失或被错误替代”。后续实现不能在当前 `native.py` 上修补，必须新建 DAG parity runner。

### 旧 DAG 到目标 workflow 的完整对应关系

| 旧 DAG 概念 | 旧实现位置 | 目标 workflow 组件 | 迁移要求 | 验收方式 |
| --- | --- | --- | --- | --- |
| Analyst plan | `trader/graph/analysts.py::build_analyst_execution_plan` | `flow/graph.py` | 复用同一函数或输出完全一致的 plan | 静态 plan 测试 |
| Node factory | `GraphSetup.setup_graph` lines creating `create_*` handlers | `flow/context.py` | 构造同一批 node handler，不编译 LangGraph | factory 注入测试 |
| Initial state | `Propagator.create_initial_state` | `flow/state.py` | 字段、嵌套 debate state、messages 语义一致 | state parity 测试 |
| Analyst condition | `ConditionalLogic.should_continue_*` | `AnalystStageRunner.should_continue` | 返回目标 node 名必须一致 | condition fixture 测试 |
| Debate condition | `should_continue_debate` | `ResearchDebateRunner.next_node` | count 和 current_response 语义一致 | condition fixture 测试 |
| Risk condition | `should_continue_risk_analysis` | `RiskDebateRunner.next_node` | count 和 latest_speaker 语义一致 | condition fixture 测试 |
| Stream chunk progress | `propagate()` stream loop | `events.py` | 每个节点发 node event，stage 聚合由映射表生成 | event snapshot 测试 |
| Node timing | `node_timings` in `propagate()` | `runner.py` timing collector | 记录每个旧 DAG node 耗时 | performance payload 测试 |
| Performance metrics | `_build_performance_data` | `runner.py` 或复用 helper | 分类语义一致 | metrics key 测试 |
| Final state log | `_log_state` | `reports.py` 或 state log helper | 保存同等 state 字段 | final state snapshot 测试 |
| Memory decision log | `memory_log.store_decision` | `runner.py` finish hook | 若旧配置启用 memory，保持写入行为 | memory mock 测试 |
| Signal processing | `process_signal(final_trade_decision, company)` | `runner.py` finish hook | decision 结构兼容 | decision schema 测试 |
| Report extraction | `build_analysis_result` | `stages/reports.py` | 必须复用或等价抽取 | reports key 测试 |
| Report files | `simple/reports.py` | report persistence adapter | 文件名和 metadata 兼容 | reports view 测试 |

### 旧 DAG 上下文组件与新 workflow 映射

旧 DAG 的功能不是只由 graph node 决定，还依赖 `TradingAgentsGraph` 初始化时创建的一组上下文组件。新 workflow 不能实例化旧 `TradingAgentsGraph` 作为执行器，但必须构造等价上下文。

| 旧组件 | 旧来源 / 语义 | 新 workflow 对应 | 验收要求 |
| --- | --- | --- | --- |
| `quick_thinking_llm` | 供 Market/Sentiment/News/Fundamentals、Bull/Bear、Trader、Risky/Safe/Neutral、SignalProcessor 使用 | `WorkflowContext.quick_llm` | fake LLM 注入测试断言这些节点使用 quick LLM |
| `deep_thinking_llm` | 供 Research Manager、Risk Judge / Portfolio Manager 使用，并生成 `model_info` | `WorkflowContext.deep_llm` | fake LLM 注入测试断言 manager/final risk 使用 deep LLM |
| `Toolkit(config)` | 分析师和 ToolNode 的工具来源 | `WorkflowContext.toolkit` | ToolInventory 测试断言 callable 来自同一 toolkit |
| `FinancialSituationMemory("bull_memory")` | `memory_enabled=True` 时传给 Bull Researcher | `WorkflowContext.bull_memory` | memory enabled/disabled 两组 factory 测试 |
| `FinancialSituationMemory("bear_memory")` | `memory_enabled=True` 时传给 Bear Researcher | `WorkflowContext.bear_memory` | memory enabled/disabled 两组 factory 测试 |
| `FinancialSituationMemory("trader_memory")` | `memory_enabled=True` 时传给 Trader | `WorkflowContext.trader_memory` | memory enabled/disabled 两组 factory 测试 |
| `FinancialSituationMemory("invest_judge_memory")` | `memory_enabled=True` 时传给 Research Manager | `WorkflowContext.invest_judge_memory` | memory enabled/disabled 两组 factory 测试 |
| `FinancialSituationMemory("risk_manager_memory")` | `memory_enabled=True` 时传给 Risk Judge | `WorkflowContext.risk_manager_memory` | memory enabled/disabled 两组 factory 测试 |
| `ConditionalLogic(max_debate_rounds, max_risk_discuss_rounds)` | 条件边轮次控制 | `WorkflowContext.conditional_logic` | config fixture 断言轮次上限一致 |
| `Propagator(max_recur_limit=100)` | 初始 state 和 stream args | `StateFactory` + `WorkflowRuntimeConfig.recursion_limit` | 初始 state / recursion limit 测试 |
| `Reflector(quick_llm)` | `_resolve_pending_entries()` 中处理过往 pending memory outcome | `WorkflowMemoryAdapter.reflector` | pending entries fixture 测试 |
| `TradingMemoryLog(config)` | `get_past_context()`、`store_decision()`、pending entries | `WorkflowMemoryAdapter.memory_log` | past context、store decision、pending entries mock 测试 |
| `SignalProcessor(quick_llm)` | `process_signal(final_trade_decision, company)` | `DecisionAdapter.signal_processor` | decision schema 测试 |
| `self.ticker` / `log_states_dict` | `_log_state()` 写 eval log 时使用 | `WorkflowContext.symbol` / `StateLogAdapter` | state log 路径和内容测试 |

如果实现计划没有这张表对应的 context factory，说明它只复制了 DAG 图结构，没有复制旧 DAG 的执行环境。

### `propagate()` 运行时语义复刻要求

不能只复刻 `setup_graph()` 的节点和边。旧 `TradingAgentsGraph.propagate()` 还定义了运行时行为，新 workflow 必须给出对应实现。

| 旧 `propagate()` 行为 | 旧实现语义 | 新 workflow 对应 | 验收要求 |
| --- | --- | --- | --- |
| 设置 `self.ticker` | 当前分析标的进入 graph instance | `WorkflowContext.symbol` | event、task、report 中 symbol 一致 |
| `_resolve_pending_entries(company_name)` | 处理 memory 中待解析条目 | `WorkflowMemoryAdapter.resolve_pending_entries()` | memory mock 断言被调用 |
| `memory_log.get_past_context(company_name)` | 给初始 state 注入历史上下文 | `StateFactory.create(..., past_context=...)` | state 中 `past_context` 一致 |
| `resolve_instrument_context(company_name, asset_type)` | 给初始 state 注入标的上下文 | `StateFactory.create(..., instrument_context=...)` | state 中 `instrument_context` 一致 |
| `checkpoint_enabled` | 旧 DAG 可启用 checkpoint，使用 `get_checkpointer()`、`thread_id()`、`checkpoint_step()` | `WorkflowCheckpointAdapter` | 开启 checkpoint 时必须保存/恢复同一 `thread_id(company, date)` 的 workflow checkpoint；如果本轮实现没有 checkpoint adapter，则必须阻断启动并返回配置错误，不能静默忽略 |
| `get_graph_args(stream_mode)` | 有 progress callback 时用 updates，否则 values | 新 workflow 不使用 LangGraph stream，但必须发同等 node event | node event 顺序等价 |
| chunk 更新 final state | 每个 node update merge 到 final state | `Runner.apply_node_update()` | fake node 更新合并测试 |
| `_send_progress_update(chunk)` | node 名映射为进度消息 | `events.emit_node()` + `events.emit_stage()` | 旧 node 名可在 UI 追踪 |
| `node_timings` | 记录每个 node 耗时 | `TimingCollector` | `performance_metrics.node_timings` 存在 |
| `_build_performance_data` | 分类 analyst/tool/clear/research/trader/risk | `PerformanceAdapter` | 分类 key 与旧结构一致 |
| `_log_state(trade_date, final_state)` | 保存 final state 日志 | `StateLogAdapter` | final state snapshot 可测试 |
| `memory_log.store_decision(...)` | 保存最终交易决策到 memory | `WorkflowMemoryAdapter.store_decision()` | final decision 写入 mock |
| `process_signal(final_trade_decision, company)` | 生成 decision dict | `DecisionAdapter.process_signal()` | action/confidence/risk/target/reasoning 结构一致 |
| 返回 `(final_state, decision)` | service 后续调用 `build_analysis_result()` | `StockDagParityWorkflowResult(state, decision)` | reports 层只消费该结果 |

如果后续计划没有覆盖这张表，说明只迁移了图结构，没有迁移运行时行为。

### 节点输出字段与报告字段映射

旧 DAG 的报告不是从“阶段名字”生成，而是从 final state 中指定字段抽取。新 workflow 必须维持同样的字段来源。

| 旧 DAG 节点 | 必须写入/保留的 state 字段 | 报告抽取字段 | 当前 workflow 状态 | 新 workflow 验收 |
| --- | --- | --- | --- | --- |
| `Market Analyst` | `market_report` | `reports.market_report` | 当前 `_market_report` 是错误替代 | report 内容来自旧 market node output |
| `Sentiment Analyst` | `sentiment_report` | `reports.sentiment_report` | 当前 `_sentiment_report` 是错误替代 | report 内容来自旧 social node output |
| `News Analyst` | `news_report` | `reports.news_report` | 当前 `_news_report` 是错误替代 | report 内容来自旧 news node output |
| `Fundamentals Analyst` | `fundamentals_report` | `reports.fundamentals_report` | 当前 `_fundamentals_report` 是错误替代 | report 内容来自旧 fundamentals node output |
| `Bull Researcher` | `investment_debate_state.bull_history` | `reports.bull_researcher` | 缺失 | 字段包含 `Bull Analyst:` 历史 |
| `Bear Researcher` | `investment_debate_state.bear_history` | `reports.bear_researcher` | 缺失 | 字段包含 `Bear Analyst:` 历史 |
| `Research Manager` | `investment_debate_state.judge_decision`, `investment_plan` | `reports.research_team_decision`, `reports.investment_plan` | 缺失 | 两个字段都存在且内容一致来源正确 |
| `Trader` | `trader_investment_plan` | `reports.trader_investment_plan` | 缺失 | 字段来自 trader node |
| `Risky Analyst` | `risk_debate_state.risky_history`, `aggressive_history`, `latest_speaker`, `current_risky_response`, `count` | `reports.risky_analyst` | 缺失 | 字段包含 `Risky Analyst:` 历史 |
| `Safe Analyst` | `risk_debate_state.safe_history`, `conservative_history`, `latest_speaker`, `current_safe_response`, `count` | `reports.safe_analyst` | 缺失 | 字段包含 `Safe Analyst:` 历史 |
| `Neutral Analyst` | `risk_debate_state.neutral_history`, `latest_speaker`, `current_neutral_response`, `count` | `reports.neutral_analyst` | 缺失 | 字段包含 `Neutral Analyst:` 历史 |
| `Risk Judge` | `risk_debate_state.judge_decision`, `final_trade_decision` | `reports.risk_management_decision`, `reports.final_trade_decision` | 当前 `_decision` 是错误替代 | 字段来自 risk manager node |
| `Portfolio Manager` | `risk_debate_state.judge_decision`, `final_trade_decision` | `reports.risk_management_decision`, `reports.final_trade_decision` | 缺失 | 配置切换后字段来自 portfolio manager node |

实现时禁止把 `final_trade_decision` 作为唯一报告来源反推其它字段。旧 DAG 的各报告字段必须来自对应 node 写入的 state。

### 旧进度节点到新 UI stage 的映射

旧 `_send_progress_update()` 会对部分节点发送进度消息，对工具节点和清理节点跳过 UI progress。新 workflow 的右侧栏可以聚合 stage，但 node event 不能丢。

| 旧 node | 旧 progress 文案 | 新 stage | 新 node event 是否必须记录 | UI 是否默认展示 |
| --- | --- | --- | --- | --- |
| `Market Analyst` | 市场分析师 | `market_analysis` | 是 | 是 |
| `tools_market` | 跳过 | `market_analysis` | 是 | 可折叠 |
| `Msg Clear Market` | 跳过 | `market_analysis` | 是 | 可折叠 |
| `Fundamentals Analyst` | 基本面分析师 | `fundamentals_analysis` | 是 | 是 |
| `tools_fundamentals` | 跳过 | `fundamentals_analysis` | 是 | 可折叠 |
| `Msg Clear Fundamentals` | 跳过 | `fundamentals_analysis` | 是 | 可折叠 |
| `News Analyst` | 新闻分析师 | `news_analysis` | 是 | 是 |
| `tools_news` | 跳过 | `news_analysis` | 是 | 可折叠 |
| `Msg Clear News` | 跳过 | `news_analysis` | 是 | 可折叠 |
| `Sentiment Analyst` / `Social Analyst` | 社交媒体分析师 | `sentiment_analysis` | 是 | 是 |
| `tools_social` | 跳过 | `sentiment_analysis` | 是 | 可折叠 |
| `Msg Clear Social` | 跳过 | `sentiment_analysis` | 是 | 可折叠 |
| `Bull Researcher` | 看涨研究员 | `research_debate` | 是 | 是 |
| `Bear Researcher` | 看跌研究员 | `research_debate` | 是 | 是 |
| `Research Manager` | 研究经理 | `research_manager` | 是 | 是 |
| `Trader` | 交易员决策 | `trader_decision` | 是 | 是 |
| `Risky Analyst` | 激进风险评估 | `risk_debate` | 是 | 是 |
| `Safe Analyst` | 保守风险评估 | `risk_debate` | 是 | 是 |
| `Neutral Analyst` | 中性风险评估 | `risk_debate` | 是 | 是 |
| `Risk Judge` | 风险经理 | `final_risk_decision` | 是 | 是 |
| `Portfolio Manager` | 投资组合经理 | `final_risk_decision` | 是 | 是 |
| `__end__` / `END` | 生成报告 | `report_generation` | 是 | 是 |

这张表的含义是：UI 可以不把 tool/clear 节点展开给普通用户看，但测试和审计必须能看到它们。否则无法证明条件边和工具循环被完整复刻。

### 旧 DAG 边清单与新 workflow 映射

#### 分析师阶段动态边

旧 DAG 通过 `build_analyst_execution_plan(selected_analysts)` 生成 `plan.specs`。每个 `spec` 含：

- `agent_node`
- `tool_node`
- `clear_node`
- `report_key`

新 workflow 必须保留同样的动态计划，不允许写死为当前简化顺序。默认 analyst 顺序必须以旧 DAG `GraphSetup.setup_graph(selected_analysts=["market", "social", "news", "fundamentals"])` 为准，即：

```python
["market", "social", "news", "fundamentals"]
```

如果用户配置 `selected_analysts`，必须按用户提供顺序传给 `build_analyst_execution_plan()`，并按 `plan.specs` 顺序串行执行节点。`AnalystExecutionPlan.concurrency_limit` 必须保留在 plan 中用于兼容旧配置和指标，但不得因此把 analyst 阶段改成并发执行，除非旧 DAG 也实际并发执行同一组边。

| 旧 DAG 边 | 旧条件 | 新 workflow 映射 |
| --- | --- | --- |
| `START -> plan.specs[0].agent_node` | 无 | `WorkflowCursor.goto(first_selected_analyst.agent_node)` |
| `{Analyst} -> tools_{analyst}` | `should_continue_{analyst}` 返回 tool node | `AnalystStageRunner` 检测 AIMessage tool_calls 后执行同类 tool node |
| `{Analyst} -> Msg Clear {Analyst}` | `should_continue_{analyst}` 返回 clear node | `AnalystStageRunner` 在报告生成、无 tool_calls 或工具调用上限后清理消息 |
| `tools_{analyst} -> {Analyst}` | 无 | tool 结果写入 state 后回到同一 analyst node |
| `Msg Clear {Analyst_i} -> {Analyst_{i+1}}` | 当 i 不是最后一个 analyst | `WorkflowCursor.goto(next_selected_analyst.agent_node)` |
| `Msg Clear {Last Analyst} -> Bull Researcher` | 最后一个 analyst 完成 | `WorkflowCursor.goto("Bull Researcher")` |

#### Market Analyst 条件边

旧条件函数：`ConditionalLogic.should_continue_market`

必须复刻：

- 读取 `state["messages"][-1]`。
- 读取 `state["market_tool_call_count"]`。
- 最大工具调用次数为 `3`。
- 如果 `market_tool_call_count >= 3`，进入 `Msg Clear Market`。
- 如果 `market_report` 长度大于 `100`，进入 `Msg Clear Market`。
- 如果 last message 有 `tool_calls`，进入 `tools_market`。
- 否则进入 `Msg Clear Market`。

新 workflow 对应：

- `AnalystStageRunner.should_continue("market")`
- `AnalystStageRunner.run_tools("market")`
- `AnalystStageRunner.clear_messages("market")`

#### Sentiment Analyst 条件边

旧条件函数：`ConditionalLogic.should_continue_social`

必须复刻：

- 读取 `state["sentiment_tool_call_count"]`。
- 最大工具调用次数为 `3`。
- 如果 `sentiment_tool_call_count >= 3`，进入 `Msg Clear Social`。
- 如果 `sentiment_report` 长度大于 `100`，进入 `Msg Clear Social`。
- 如果 last message 有 `tool_calls`，进入 `tools_social`。
- 否则进入 `Msg Clear Social`。

新 workflow 对应：

- `AnalystStageRunner.should_continue("social")`
- `AnalystStageRunner.run_tools("social")`
- `AnalystStageRunner.clear_messages("social")`

#### News Analyst 条件边

旧条件函数：`ConditionalLogic.should_continue_news`

必须复刻：

- 读取 `state["news_tool_call_count"]`。
- 最大工具调用次数为 `3`。
- 如果 `news_tool_call_count >= 3`，进入 `Msg Clear News`。
- 如果 `news_report` 长度大于 `100`，进入 `Msg Clear News`。
- 如果 last message 有 `tool_calls`，进入 `tools_news`。
- 否则进入 `Msg Clear News`。

新 workflow 对应：

- `AnalystStageRunner.should_continue("news")`
- `AnalystStageRunner.run_tools("news")`
- `AnalystStageRunner.clear_messages("news")`

#### Fundamentals Analyst 条件边

旧条件函数：`ConditionalLogic.should_continue_fundamentals`

必须复刻：

- 读取 `state["fundamentals_tool_call_count"]`。
- 最大工具调用次数为 `1`。
- 如果 `fundamentals_report` 长度大于 `100`，进入 `Msg Clear Fundamentals`。
- 如果 last message 有 `tool_calls` 且 `fundamentals_tool_call_count < 1`，进入 `tools_fundamentals`。
- 如果 last message 有 `tool_calls` 但调用次数已经达到上限，进入 `Msg Clear Fundamentals`。
- 否则进入 `Msg Clear Fundamentals`。

新 workflow 对应：

- `AnalystStageRunner.should_continue("fundamentals")`
- `AnalystStageRunner.run_tools("fundamentals")`
- `AnalystStageRunner.clear_messages("fundamentals")`

#### 投资研究辩论条件边

旧条件函数：`ConditionalLogic.should_continue_debate`

旧 DAG 边：

| 旧 DAG 当前节点 | 条件返回 | 目标节点 | 新 workflow 映射 |
| --- | --- | --- | --- |
| `Bull Researcher` | `Bear Researcher` | `Bear Researcher` | `ResearchDebateRunner.next_after_bull()` |
| `Bull Researcher` | `Research Manager` | `Research Manager` | `ResearchDebateRunner.goto_manager()` |
| `Bear Researcher` | `Bull Researcher` | `Bull Researcher` | `ResearchDebateRunner.next_after_bear()` |
| `Bear Researcher` | `Research Manager` | `Research Manager` | `ResearchDebateRunner.goto_manager()` |

必须复刻：

- `current_count = state["investment_debate_state"]["count"]`
- `max_count = 2 * max_debate_rounds`
- `current_speaker = state["investment_debate_state"]["current_response"]`
- 当 `current_count >= max_count`，进入 `Research Manager`。
- 否则如果 `current_speaker.startswith("Bull")`，进入 `Bear Researcher`。
- 否则进入 `Bull Researcher`。

注意：这意味着第一次进入辩论时从 `Bull Researcher` 开始；之后按旧条件函数交替，不允许自由改成并发辩论或一次性总结。

#### 研究经理到交易员

旧 DAG 边：

```text
Research Manager -> Trader
```

新 workflow 映射：

```text
ResearchDebateRunner.run_manager()
  -> TraderDecisionRunner.run_trader()
```

必须复刻：

- `Research Manager` 输出 `investment_debate_state.judge_decision`。
- 同时写 `investment_plan`。
- `Trader` 的输入必须包含 `investment_plan` 和四类 analyst report。
- `Trader` 输出 `trader_investment_plan`。

#### 风险辩论条件边

旧条件函数：`ConditionalLogic.should_continue_risk_analysis`

旧 DAG 边：

| 旧 DAG 当前节点 | 条件返回 | 目标节点 | 新 workflow 映射 |
| --- | --- | --- | --- |
| `Trader` | 无条件 | `Risky Analyst` | `RiskDebateRunner.run_risky()` |
| `Risky Analyst` | `Safe Analyst` | `Safe Analyst` | `RiskDebateRunner.next_after_risky()` |
| `Risky Analyst` | `Risk Judge` | final risk node | `RiskDecisionRunner.run_final()` |
| `Safe Analyst` | `Neutral Analyst` | `Neutral Analyst` | `RiskDebateRunner.next_after_safe()` |
| `Safe Analyst` | `Risk Judge` | final risk node | `RiskDecisionRunner.run_final()` |
| `Neutral Analyst` | `Risky Analyst` | `Risky Analyst` | `RiskDebateRunner.next_after_neutral()` |
| `Neutral Analyst` | `Risk Judge` | final risk node | `RiskDecisionRunner.run_final()` |
| `Risk Judge` / `Portfolio Manager` | 无条件 | `END` | `StockDagParityWorkflow.finish()` |

必须复刻：

- `current_count = state["risk_debate_state"]["count"]`
- `max_count = 3 * max_risk_discuss_rounds`
- `latest_speaker = state["risk_debate_state"]["latest_speaker"]`
- 当 `current_count >= max_count`，进入 final risk node。
- 否则如果 `latest_speaker.startswith("Risky")`，进入 `Safe Analyst`。
- 否则如果 `latest_speaker.startswith("Safe")`，进入 `Neutral Analyst`。
- 否则进入 `Risky Analyst`。

final risk node 的选择必须复刻：

- 默认 `final_decision_engine = "risk_manager"`，使用 `Risk Judge`。
- 当 `final_decision_engine == "portfolio_manager"`，使用 `Portfolio Manager`。

## 新 workflow 模块设计

### 必须新增或重构的模块

必须拆分为以下合规模块，避免再出现一个大而简化的 `native.py`。`flow` 是真实单词，新增目录和文件名符合仓库 AGENTS.md 的单词命名约束；业务含义由类名和函数名表达，不通过下划线文件名表达。

```text
backend/app/services/research/agent/flow/
  __init__.py
  runner.py
  context.py
  graph.py
  state.py
  events.py
  checkpoint.py
  stages/
    analysts.py
    conditions.py
    research.py
    trader.py
    risk.py
    decision.py
    reports.py
```

职责：

- `runner.py`：新 workflow 的主状态机，不调用 LangGraph。
- `graph.py`：把旧 DAG 的 node/edge/conditional edge 显式建模为 Python plan。
- `state.py`：创建和校验与旧 `AgentState` 兼容的 state。
- `events.py`：把每个 node 运行映射到 Agent 右侧执行步骤事件。
- `checkpoint.py`：处理检查点配置；未完整实现检查点恢复时必须显式阻断，不能静默忽略。
- `stages/analysts.py`：执行 Market/Sentiment/News/Fundamentals 及其 tool loop。
- `stages/conditions.py`：适配旧 `ConditionalLogic` 条件边。
- `stages/research.py`：执行 Bull/Bear/Research Manager。
- `stages/trader.py`：执行 Trader。
- `stages/risk.py`：执行 Risky/Safe/Neutral。
- `stages/decision.py`：执行 Risk Judge 或 Portfolio Manager。
- `stages/reports.py`：调用 `build_analysis_result()` 并保存报告。

### 允许复用的旧代码

允许复用：

- `trader.agents.create_*` node factory。
- `trader.agents.utils.states.AgentState`、`InvestDebateState`、`RiskDebateState`。
- `trader.agents.utils.utils.Toolkit`。
- `trader.graph.analysts.build_analyst_execution_plan` 和 `ANALYST_NODE_SPECS`。
- `trader.graph.conditions.ConditionalLogic`，或逐行等价迁移。
- `trader.graph.propagation.Propagator.create_initial_state`，或逐字段等价迁移。
- `app.services.analysis.simple.result.build_analysis_result`。
- 现有报告保存 helper，只要保存结果字段与旧路径一致。

禁止复用为主执行入口：

- `TradingAgentsGraph.propagate()`。
- `self.workflow.compile(...)`。
- LangGraph `StateGraph` 在 Agent workflow 中作为执行器。
- 旧 Redis queue / analysis worker 作为 Agent workflow 主路径。

## 状态契约

新 workflow 的 state 必须至少包含以下字段，且字段名和语义必须与旧 DAG 一致：

```python
{
    "messages": [...],
    "company_of_interest": symbol,
    "asset_type": "stock",
    "instrument_context": "...",
    "trade_date": "YYYY-MM-DD",
    "past_context": "...",
    "sender": "",
    "investment_debate_state": {
        "bull_history": "",
        "bear_history": "",
        "history": "",
        "current_response": "",
        "judge_decision": "",
        "count": 0,
    },
    "risk_debate_state": {
        "risky_history": "",
        "aggressive_history": "",
        "safe_history": "",
        "conservative_history": "",
        "neutral_history": "",
        "history": "",
        "latest_speaker": "",
        "current_risky_response": "",
        "current_aggressive_response": "",
        "current_safe_response": "",
        "current_conservative_response": "",
        "current_neutral_response": "",
        "judge_decision": "",
        "count": 0,
    },
    "market_report": "",
    "fundamentals_report": "",
    "sentiment_report": "",
    "news_report": "",
    "market_tool_call_count": 0,
    "news_tool_call_count": 0,
    "sentiment_tool_call_count": 0,
    "fundamentals_tool_call_count": 0,
    "investment_plan": "",
    "trader_investment_plan": "",
    "final_trade_decision": "",
}
```

新 workflow 可以增加 `workflow_run_id`、`attempt_id`、`stage_events` 等 Agent 字段，但不得改名或删除旧报告相关字段。

注意：`AgentState` 的静态类型中包含 `sender`、`investment_plan`、`trader_investment_plan`、`final_trade_decision`。旧 `Propagator.create_initial_state()` 不一定在初始 dict 中填充后三个字段，但旧 DAG 后续节点会写入。新 workflow 的 state validator 必须允许这些字段从空值过渡到节点输出值，最终态必须包含它们。

## 报告格式契约

新 workflow 完成后，必须调用旧报告抽取契约。`analysis_reports.reports` 至少应在完整配置下包含：

- `market_report`
- `sentiment_report`
- `news_report`
- `fundamentals_report`
- `investment_plan`
- `trader_investment_plan`
- `final_trade_decision`
- `bull_researcher`
- `bear_researcher`
- `research_team_decision`
- `risky_analyst`
- `safe_analyst`
- `neutral_analyst`
- `risk_management_decision`

同时，保存到 `analysis_reports` / 报告详情接口的顶层结果必须兼容 `build_analysis_result()` 返回结构，至少包含并保持语义一致：

- `analysis_id`
- `stock_code`
- `stock_symbol`
- `analysis_date`
- `summary`
- `recommendation`
- `confidence_score`
- `risk_level`
- `key_points`
- `detailed_analysis`
- `execution_time`
- `tokens_used`
- `state`
- `analysts`
- `research_depth`
- `reports`
- `decision`
- `model_info`
- `performance_metrics`

其中 `decision` 必须来自旧 `process_signal(final_trade_decision, company)` 等价逻辑，并包含 `action`、`confidence`、`risk_score`、`target_price`、`reasoning`。`model_info` 必须保持旧 `propagate()` 语义：由 deep thinking LLM 类型和模型名组成，无法读取时才为 `Unknown`。`performance_metrics` 必须保持 `_build_performance_data()` 的分类结构。

如果用户显式跳过某类 analyst 或关闭风险评估：

- 被跳过字段可以缺失，但必须有 `stage_events` 说明 `skipped` 原因。
- 不得用空字符串、伪造文本或 native 简化结论填充。
- 最终报告必须披露哪些阶段未运行。

文件报告格式必须兼容旧报告页，尤其是：

- `market_report.md`
- `sentiment_report.md`
- `news_report.md`
- `fundamentals_report.md`
- `investment_plan.md`
- `trader_investment_plan.md`
- `final_trade_decision.md`
- `research_team_decision.md`
- `risk_management_decision.md`
- `analysis_metadata.json`

## Agent 事件与右侧执行步骤

右侧执行步骤不能只显示粗粒度阶段。为了证明 workflow 复刻 DAG，事件至少分两层：

### Stage 层

用于 UI 聚合：

- `validate_input`
- `prepare_state`
- `market_analysis`
- `sentiment_analysis`
- `news_analysis`
- `fundamentals_analysis`
- `research_debate`
- `research_manager`
- `trader_decision`
- `risk_debate`
- `final_risk_decision`
- `report_generation`
- `agent_summary`

### Node 层

用于审计和测试，必须记录旧 DAG 节点名：

- `Market Analyst`
- `tools_market`
- `Msg Clear Market`
- `Sentiment Analyst`
- `tools_social`
- `Msg Clear Social`
- `News Analyst`
- `tools_news`
- `Msg Clear News`
- `Fundamentals Analyst`
- `tools_fundamentals`
- `Msg Clear Fundamentals`
- `Bull Researcher`
- `Bear Researcher`
- `Research Manager`
- `Trader`
- `Risky Analyst`
- `Safe Analyst`
- `Neutral Analyst`
- `Risk Judge` 或 `Portfolio Manager`
- `END`

每个 node event 必须包含：

```json
{
  "event_type": "stock_analysis.node",
  "node": "Bull Researcher",
  "stage": "research_debate",
  "status": "running|completed|failed|skipped",
  "edge_from": "Msg Clear Fundamentals",
  "edge_to": "Bear Researcher",
  "report_keys_added": ["bull_researcher"],
  "task_id": "...",
  "analysis_id": "...",
  "attempt_id": "..."
}
```

## 验收测试要求

### 1. 静态映射测试

新增测试必须读取新 workflow 的 node/edge plan，并断言：

- 旧 DAG 所有节点都存在映射。
- 旧 DAG 所有普通边都存在映射。
- 旧 DAG 所有条件边都存在映射。
- 旧 DAG 每个 `tools_*` 的工具 inventory 与新 workflow 完全一致。
- 默认 `selected_analysts` 顺序为 `["market", "social", "news", "fundamentals"]`。
- `Risk Judge` 和 `Portfolio Manager` 两种 final risk node 都有映射。
- 没有任何 node 映射到 `agent_native` 简化函数。

### 1.1 Context factory 等价测试

新增测试必须构造旧 DAG context fixture 和新 workflow context fixture，并断言：

- quick/deep LLM 分别注入到旧 DAG 相同节点类别。
- `Toolkit` 生成的工具 callable 与旧 `_create_tool_nodes()` 使用同一组工具。
- `memory_enabled=True` 时 bull/bear/trader/invest_judge/risk_manager memory 均创建并传入对应 node factory。
- `memory_enabled=False` 时上述 role memory 均为 `None`，但节点仍按旧 factory 参数构造。
- `ConditionalLogic` 的 `max_debate_rounds`、`max_risk_discuss_rounds` 来自同一配置。
- `SignalProcessor` 使用 quick LLM，`model_info` 使用 deep LLM。

### 2. 状态初始化等价测试

对比 `Propagator.create_initial_state()` 与新 workflow state factory：

- 必填字段一致。
- `investment_debate_state` 初始字段一致。
- `risk_debate_state` 初始字段一致。
- tool call count 初始值一致。

### 3. 条件边等价测试

为以下条件函数构造 state fixture：

- `should_continue_market`
- `should_continue_social`
- `should_continue_news`
- `should_continue_fundamentals`
- `should_continue_debate`
- `should_continue_risk_analysis`

新 workflow 的 condition 结果必须与旧 `ConditionalLogic` 一致。

### 4. Node handler 调用测试

用 fake node handlers 替换旧 `create_*` 工厂，断言新 workflow 按旧 DAG 顺序调用：

```text
Market Analyst
tools_market
Market Analyst
Msg Clear Market
...
Bull Researcher
Bear Researcher
Research Manager
Trader
Risky Analyst
Safe Analyst
Neutral Analyst
Risk Judge
END
```

测试不得调用 `TradingAgentsGraph.propagate()`。

同时必须断言每类 node update 的 state merge 语义：

- Analyst update 中的 `messages`、`*_report`、`*_tool_call_count` 被合并到 state。
- `tools_*` update 生成的 `ToolMessage` 被追加到 `messages`，然后边回到同一个 analyst。
- `Msg Clear *` update 中的 `RemoveMessage` 生效，旧消息被删除，只保留新的 placeholder `HumanMessage`。
- `Bull Researcher` / `Bear Researcher` 更新 `investment_debate_state.history`、对应 history、`current_response` 和 `count`，下一条边由这些字段决定。
- `Risky` / `Safe` / `Neutral` 更新 `risk_debate_state.history`、对应 history、alias history、`latest_speaker`、current response 和 `count`，下一条边由这些字段决定。
- `Trader` 写入 `sender = "Trader"` 和 `trader_investment_plan`。
- `Risk Judge` / `Portfolio Manager` 写入 `risk_debate_state.judge_decision`、`latest_speaker = "Judge"` 和 `final_trade_decision`。

### 5. 报告字段等价测试

构造一个完整 final state，分别调用旧 `build_analysis_result()` 与新 workflow 报告保存层，断言：

- `reports.keys()` 一致。
- `bull_researcher` 来自 `investment_debate_state.bull_history`。
- `bear_researcher` 来自 `investment_debate_state.bear_history`。
- `research_team_decision` 来自 `investment_debate_state.judge_decision`。
- `risky_analyst` 来自 `risk_debate_state.risky_history`。
- `safe_analyst` 来自 `risk_debate_state.safe_history`。
- `neutral_analyst` 来自 `risk_debate_state.neutral_history`。
- `risk_management_decision` 来自 `risk_debate_state.judge_decision`。
- 顶层 `analysis_id`、`stock_code`、`stock_symbol`、`analysis_date`、`summary`、`recommendation`、`confidence_score`、`risk_level`、`key_points`、`detailed_analysis`、`execution_time`、`tokens_used`、`state`、`analysts`、`research_depth`、`decision`、`model_info`、`performance_metrics` 均存在且语义与旧结果一致。
- `performance_metrics.category_timings` 至少包含 `analyst_team`、`tool_calls`、`message_clearing`、`research_team`、`trader_team`、`risk_management_team`、`other`。

### 5.1 Checkpoint 等价测试

开启 `checkpoint_enabled` 时必须测试：

- 新 workflow 使用 `thread_id(company_name, trade_date)` 作为 checkpoint 标识。
- 中断后重新运行能从 checkpoint 继续，或在未实现 checkpoint adapter 时启动即返回明确 `config_required` / `unsupported_checkpoint`，不得继续跑一个无 checkpoint 的“成功”任务。
- 任务完成后沿用旧清理语义，必要时调用 `clear_checkpoint(data_cache_dir, ticker, date)`。

### 6. 禁止回归测试

必须有测试明确失败以下行为：

- `stock_analysis` 调用 `run_native_stock_workflow`。
- `stock_analysis` 只返回五段简化 reports。
- Agent workflow 直接调用 `TradingAgentsGraph.propagate()`。
- Agent workflow 直接提交旧 analysis queue 并把旧 worker 当主执行器。

### 7. 最小真实链路测试

在可控 fake LLM / fake tool 环境中跑一轮完整 workflow，断言：

- `analysis_tasks.status == "completed"`。
- `analysis_reports.source == "agent_workflow_dag_parity"`。
- `analysis_reports.reports` 包含完整报告字段。
- `stage_events` 和 `node_events` 都存在。
- `/reports/view/{task_id}` 能读取新 workflow 保存的报告。

## 实施顺序

1. 新增静态 DAG 映射表，不执行任何真实节点。
2. 新增 state factory，先通过状态等价测试。
3. 新增 condition adapter，先通过条件边等价测试。
4. 新增 fake-node workflow runner，先通过节点顺序测试。
5. 接入旧 node handler 工厂，但仍用 fake LLM/tool 做测试。
6. 接入报告抽取和保存，先通过报告字段等价测试。
7. 替换 `StockAnalysisWorkflow.run_single()` 的主路径。
8. 移除或隔离 `run_native_stock_workflow` 的默认调用。
9. 更新 Agent prompt 和工具说明，明确这是 `Agent workflow DAG parity`。
10. 做一次真实单股分析 smoke test，对比旧 DAG 报告字段集合。

## 明确不做

- 不在 Agent workflow 中调用 `TradingAgentsGraph.propagate()`。
- 不把旧 DAG worker 作为 Agent workflow 的主路径。
- 不删除旧 DAG。
- 不删除旧单股分析页面。
- 不用 native 简化报告冒充 DAG 结果。
- 不在 spec 外新增报告字段名替代旧字段名。
- 不把所有节点合成一个 LLM prompt。

## 成功标准

一轮完整配置的 Agent 单股分析完成后，数据库最新报告应满足：

```text
source = "agent_workflow_dag_parity"
reports keys 至少包含：
  market_report
  sentiment_report
  news_report
  fundamentals_report
  investment_plan
  trader_investment_plan
  final_trade_decision
  bull_researcher
  bear_researcher
  research_team_decision
  risky_analyst
  safe_analyst
  neutral_analyst
  risk_management_decision
```

同时，Agent attempt 的 node events 能完整还原旧 DAG 的运行路径。任何人只看事件日志，就能回答：

- 旧 DAG 的哪个节点已经运行？
- 它对应新 workflow 的哪个 component？
- 它走了哪条边？
- 它写入了哪些 state 字段？
- 它最终贡献了哪个报告字段？

如果不能回答这些问题，说明 workflow 没有完整复刻 DAG。
