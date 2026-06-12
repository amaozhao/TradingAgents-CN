# 研究智能体单股分析 DAG 对齐工作流执行说明

## 默认路径

- `stock_analysis` 和 `single_stock_analysis` 默认运行 `StockDagParityWorkflow`。
- 报告 source 固定为 `agent_workflow_dag_parity`。
- 返回报告链接仍使用 `/reports/view/{task_id}`。
- 旧 Redis queue / analysis worker 不是智能体单股分析主路径。

## 保留边界

- 旧 TradingAgents LangGraph DAG 继续保留，旧单股分析页面仍可作为基线使用。
- 智能体工作流不调用 `TradingAgentsGraph.propagate()`。
- 智能体工作流不调用已编译 LangGraph，也不调用 `self.workflow.compile(...)`。
- `run_native_stock_workflow()` 只允许作为隔离的非默认后备实现存在，默认路径测试会禁止静默回退。

## 运行结构

- 图计划由 `backend/app/services/research/agent/flow/graph.py` 生成。
- 默认执行器由 `StockDagParityWorkflow.run()` 串联 analyst、research debate、trader、risk debate 和 final decision 阶段。
- 报告提取复用旧 `build_analysis_result()`，但持久化文档使用 `agent_workflow_dag_parity` source。
- 右侧栏阶段事件使用 DAG 对齐阶段：`validate_input`、`prepare_state`、`market_analysis`、`sentiment_analysis`、`news_analysis`、`fundamentals_analysis`、`research_debate`、`research_manager`、`trader_decision`、`risk_debate`、`final_risk_decision`、`report_generation`、`agent_summary`。

## 检查点行为

- 当前阶段不实现 checkpoint resume。
- 如果 workflow config 设置 `checkpoint_enabled=True`，`StockDagParityWorkflow` 会显式抛出 `UnsupportedCheckpointError`。
- 默认智能体单股分析路径会关闭 checkpoint，避免误用未实现的 resume 语义。
