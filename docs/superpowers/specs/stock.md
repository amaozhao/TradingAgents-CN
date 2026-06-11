# 研究 Agent 单股分析 Workflow 迁移规格说明

日期：2026-06-11

## 摘要

本规格合并并取代以下两份旧规格：

- `2026-06-11-agent-analysis-config-panel.md`
- `2026-06-11-research-agent-stock-analysis-consolidation.md`

第一阶段只迁移 **单股分析入口和 Agent 体验** 到研究 Agent 的 Workflow-first, Skill-backed 实现。其它分析形态不进入本规格范围。

新的方向：

- **Agent** 负责理解用户意图、收集或确认参数、启动 workflow、展示进度、读取真实结果并解释报告。
- **StockAnalysisWorkflow** 负责确定性编排、阶段顺序、状态推进、等待窗口、超时、任务/报告绑定和事件上报。
- **Stage modules** 负责具体阶段能力，例如输入校验、数据准备、市场分析、基本面分析、新闻分析、研究辩论、风险评估和报告生成。

该方案不是把所有逻辑塞进 Agent，也不是修改原有 LangGraph DAG。旧 DAG 必须作为不可变基线保留，用于回归测试和结果对比；新 Agent workflow 只能通过 adapter 旁路调用旧入口或实现新阶段。

## 当前代码基线

### 已存在能力

- 旧单股页面仍然存在：`/analysis/single`。
- 旧单股分析体系已有：
  - `AnalysisParameters`
  - `SingleAnalysisRequest`
  - `analysis_tasks`
  - 任务队列
  - 状态查询
  - 报告读取和下载
- 研究 Agent 已有：
  - session
  - message
  - attempt
  - event
  - artifact
  - 工具注册和权限体系
  - 右侧执行步骤展示
- 当前 Agent 单股工具已经接入真实单股分析任务：
  - `single_stock_analysis`
  - `stock_analysis_status`
  - `stock_analysis_report`

### 当前实现事实

- 当前 `single_stock_analysis` 仍然提交旧 TradingAgents LangGraph DAG 到现有分析队列。
- 当前工具会创建真实 `task_id`，并通过队列启动后台任务。
- 当前工具默认 `wait_for_completion=true`。
- 当前默认等待上限是 900 秒，最大允许 1800 秒。
- 当前默认轮询间隔是 2 秒，最大允许 30 秒。
- 当前任务状态来自现有任务系统，主要包括 `pending`、`processing`、`completed`、`failed`、`cancelled`。
- 当前报告读取通过 `analysis_reports`，并按 `context.principal.user_id` 过滤。
- 编写本规格前没有 `stock_analysis` 统一工具；第一阶段实现后必须补齐并纳入回归测试。
- 编写本规格前没有独立的 `StockAnalysisWorkflow` 服务；第一阶段实现后必须作为工具层外的 Agent-facing 编排外壳存在。
- 编写本规格前没有按股票分析阶段持久化的 `stock_analysis.stage` 事件；第一阶段实现后右侧执行栏必须能消费该事件。
- 当前前端 `/agent` 的 `+` 菜单更像快捷提示词入口，不是结构化配置入口。
- 当前前端没有把单股配置 payload 作为机器可读 metadata 直接交给后端执行指定工具的完整链路。

### 不可变基线

第一阶段必须把现有单股分析路径作为 golden baseline：

- 不修改旧 LangGraph DAG 的节点、边、状态字段、提示词、数据准备逻辑、报告生成逻辑或执行顺序。
- 不把旧 `/analysis/single` 切到新 workflow。
- 不重命名旧 DAG 相关模块、类、函数或报告字段。
- 不删除 `langgraph` 依赖。
- 只允许在旧入口外层新增 adapter、wrapper、测试和观测代码。
- 如果发现旧 DAG bug，必须单独开修复任务；不能混入本迁移。
- 新 Agent workflow 的第一阶段输出必须与旧 DAG baseline 做结构兼容性对比，而不是替代旧逻辑。

### 当前主要问题

- 单股分析当前仍是“Agent 工具包裹旧 LangGraph DAG”，对 Agent 右侧执行栏来说仍偏黑盒。
- 用户不能在 Agent 中明确确认市场、日期、分析深度、分析师团队、情绪/风险选项和模型配置。
- Agent 事件、旧任务进度、报告状态还不是统一状态源。
- 旧 LangGraph state 与 Agent attempt/event 体系并存，长期会造成双状态源。
- 结构化配置入口如果没有后端直达执行链路，仍可能被 LLM 改写参数。

## 目标

- 研究 Agent 成为单股分析的新主入口。
- 保留旧 `/analysis/single`、`/tasks`、`/reports`，直到新路径稳定。
- 用 `StockAnalysisWorkflow` 作为 Agent 单股入口的编排外壳；第一阶段不替代、不修改旧 LangGraph DAG。
- 用独立阶段模块实现每个分析阶段，避免新 workflow 变成另一个大黑盒。
- 单股分析复用现有参数 schema、任务状态、报告产物和权限隔离。
- Agent 不依赖 LLM 猜测关键分析参数；结构化入口提交时必须保留原始 payload。
- 右侧执行步骤展示当前 attempt 的真实阶段进度，而不是旧会话或全局任务状态。
- 任务 pending、processing、failed、timeout 时，Agent 必须明确说明真实状态，不能编造完成结论。
- 所有任务、报告、artifact 读取都必须使用当前用户身份过滤。
- 建立旧 DAG baseline 对比测试，确保新入口没有破坏旧单股分析的任务、状态、报告和权限行为。

## 非目标

- 第一阶段不删除旧单股页面。
- 第一阶段不一次性删除 LangGraph 相关代码。
- 第一阶段不修改旧 LangGraph DAG 内部实现。
- 第一阶段不把旧 `/analysis/single` 切换到新 workflow。
- 第一阶段不迁移 `/tasks`、`/reports` 的页面结构。
- 不把 Agent 模型配置和股票分析模型配置混成同一项。
- 不让 LLM 自由决定股票分析阶段顺序。
- 不把长耗时分析同步阻塞在前端请求中无限等待。
- 不新增交易下单、调仓或实盘执行能力。
- 不允许 pending、processing 或 failed 任务被总结成已完成报告。
- 不把“未来替换 LangGraph”作为第一阶段验收项。

## 核心架构

```text
用户
  ↓
/agent
  ↓
自然语言请求 或 单股结构化配置卡片
  ↓
stock_analysis / single_stock_analysis
  ↓
StockAnalysisWorkflow
  ↓
Stage modules
  ├─ validate_stock_input
  ├─ prepare_market_data
  ├─ run_market_analyst
  ├─ run_fundamentals_analyst
  ├─ run_news_analyst
  ├─ run_social_analyst
  ├─ run_research_debate
  ├─ run_trader_decision
  ├─ run_risk_review
  ├─ generate_report
  └─ summarize_for_agent
  ↓
analysis_tasks / analysis_reports / Agent events / artifacts
  ↓
右侧执行步骤、任务中心、报告页、Agent 最终解释
```

## 设计原则

- **Workflow 是状态源**：阶段顺序、阶段状态、超时、失败、跳过都由 workflow 决定。
- **Skill 是能力单元**：每个 skill 做一件事，输入输出结构化，可单测，可替换。
- **Agent 不管理复杂流程**：Agent 可以启动 workflow、追问缺参、读取结果、解释报告，但不自己维护股票分析状态机。
- **报告是事实来源**：最终投资建议必须来自真实报告或明确标注的已返回证据。
- **事件可恢复**：历史会话重开后，可以通过 persisted event + task/report 状态恢复执行步骤和结果。
- **兼容先行**：第一阶段必须保留现有单股任务、报告、下载和权限行为。
- **基线不可变**：旧 DAG 是对照组，不是本阶段改造对象。
- **布局确定**：Agent 配置入口、消息流和执行步骤的位置必须在 spec 中固定，不能由实现者自由发挥。

## Workflow 与 Skill 分工

### StockAnalysisWorkflow 负责

- 通过 adapter 创建或绑定 `task_id`，不得直接改旧 DAG 内部逻辑。
- 写入 attempt 关联信息。
- 维护阶段状态。
- 决定阶段顺序。
- 根据用户配置跳过阶段。
- 控制阶段并发。
- 控制 bounded wait 和 hard timeout。
- 写入 Agent event。
- 写入任务状态。
- 保存 report / artifact。
- 返回最终工具结果。

第一阶段的 workflow 是 Agent-facing orchestration shell：

- 可以调用现有 `single_stock_analysis` helper 或现有单股任务创建/队列入口。
- 不进入旧 DAG 节点内部做阶段拆分。
- 不改变旧 DAG 产出的 `analysis_tasks`、`analysis_reports` 字段语义。
- 只在 Agent attempt/event 层增加阶段展示和状态映射。

### Skill 负责

- `validate_stock_input`
  - 校验 symbol、market_type、analysis_date、模型配置、权限。
- `prepare_market_data`
  - 准备行情、基础信息、财务、新闻、可用数据源状态。
- `run_market_analyst`
  - 生成市场趋势、成交结构、技术面分析。
- `run_fundamentals_analyst`
  - 生成财务、估值、商业模式、竞争优势分析。
- `run_news_analyst`
  - 生成新闻、公告、事件驱动分析。
- `run_social_analyst`
  - 生成社媒或情绪分析；A 股默认禁用或降级，除非后端确认可用。
- `run_research_debate`
  - 运行多空研究员和研究经理阶段。
- `run_trader_decision`
  - 生成交易员视角的策略判断。
- `run_risk_review`
  - 运行激进、保守、中性风险评估和风险经理结论。
- `generate_report`
  - 生成结构化报告并保存到现有报告系统。
- `summarize_for_agent`
  - Agent 读取真实报告后生成会话内解释；模型不可用时返回确定性摘要。

## 阶段顺序

单股分析默认阶段：

1. `validate_input`
2. `prepare_data`
3. `market_analysis`
4. `fundamentals_analysis`
5. `news_analysis`
6. `social_analysis`
7. `research_debate`
8. `trader_decision`
9. `risk_review`
10. `report_generation`
11. `agent_summary`

阶段规则：

- `selected_analysts` 决定 market/fundamentals/news/social 是否执行。
- `include_risk=false` 时跳过 `risk_review`，但报告必须注明未执行风险评估。
- `include_sentiment=false` 时跳过情绪相关数据和总结。
- A 股默认跳过或禁用 `social_analysis`，并写入 `skipped` 阶段事件说明原因。
- 分析师阶段可以并发；辩论、交易决策、风险、报告生成必须按依赖顺序执行。
- 阶段失败必须写入 failed 事件，并决定 workflow 是终止还是降级继续。
- 旧任务状态 `processing` 在 Agent 阶段视图中可映射为 `running`，但原始状态必须保留。

## 工具设计

### 推荐工具命名

新增统一工具：

- `stock_analysis`

保留兼容工具：

- `single_stock_analysis`

独立读取工具：

- `stock_analysis_status`
- `stock_analysis_report`

兼容工具内部不应复制逻辑，应调用同一套 workflow/helper。

第一阶段落地顺序：

1. 保持当前 `single_stock_analysis` 可用。
2. 新增 `stock_analysis`，仅支持 `mode="single"` 或省略 `mode`。
3. 将 `single_stock_analysis` 改为调用 `stock_analysis` 的同一实现。
4. `stock_analysis_status` 和 `stock_analysis_report` 继续只读取当前用户自己的单股任务/报告。

### `stock_analysis` 输入

```json
{
  "mode": "single",
  "symbol": "600519",
  "market_type": "A股",
  "analysis_date": "2026-06-11",
  "research_depth": "标准",
  "selected_analysts": ["market", "fundamentals", "news"],
  "include_sentiment": true,
  "include_risk": true,
  "language": "zh-CN",
  "quick_analysis_model": "qwen-turbo",
  "deep_analysis_model": "qwen-max",
  "custom_prompt": "重点解释估值和风险",
  "wait_for_completion": true,
  "wait_timeout_seconds": 900,
  "poll_interval_seconds": 2
}
```

输入约束：

- `symbol` 必填；兼容 `stock_code` 作为旧字段。
- `market_type` 支持 `A股`、`港股`、`美股`。
- `research_depth` 支持 `快速`、`基础`、`标准`、`深度`、`全面`，并兼容 `1` 到 `5`。
- `selected_analysts` 支持 `market`、`fundamentals`、`news`、`social`。
- `wait_timeout_seconds` 默认 900，最大 1800。
- `poll_interval_seconds` 默认 2，最大 30。
- 不接受或信任 payload 中的 `user_id`。

### 单股输出

```json
{
  "tool": "stock_analysis",
  "mode": "single",
  "status": "completed",
  "wait_status": "completed",
  "task_id": "task-id",
  "symbol": "600519",
  "market_type": "A股",
  "stage": "agent_summary",
  "progress": 100,
  "links": {
    "task": "/tasks?task_id=task-id",
    "report": "/reports/view/task-id"
  },
  "report_summary": {
    "summary": "...",
    "recommendation": "...",
    "risk_level": "中等",
    "key_points": []
  }
}
```

超时但任务仍在执行时：

```json
{
  "tool": "stock_analysis",
  "mode": "single",
  "status": "processing",
  "wait_status": "timed_out",
  "wait_timed_out": true,
  "task_id": "task-id",
  "symbol": "600519",
  "progress": 40,
  "links": {
    "task": "/tasks?task_id=task-id",
    "report": "/reports/view/task-id"
  },
  "message": "单股分析任务仍在执行，已返回任务链接。"
}
```

## 状态读取工具

### `stock_analysis_status`

输入：

```json
{
  "task_id": "task-id"
}
```

要求：

- `task_id` 必填。
- 只能读取当前用户自己的任务。
- 不能接受或信任 payload 中的 `user_id`。
- pending 返回 pending。
- processing 返回当前阶段、progress、message。
- failed 返回错误原因。
- completed 返回报告链接或 `analysis_id`。
- not found 必须明确返回 `not_found`，不能让 Agent 猜测。

### `stock_analysis_report`

输入：

```json
{
  "task_id": "task-id"
}
```

要求：

- `task_id` 必填。
- 只能读取当前用户自己的报告。
- pending 或 processing 任务不能总结成 completed。
- 报告不存在时返回明确状态。
- 成功时返回摘要、评级、风险等级、关键观点、完整报告链接。
- Evidence Ledger 只保存引用和摘要，不复制完整报告。

## Agent 事件模型

每个 workflow 阶段至少写入：

```json
{
  "event_type": "stock_analysis.stage",
  "payload": {
    "attempt_id": "attempt-id",
    "task_id": "task-id",
    "tool_name": "stock_analysis",
    "mode": "single",
    "stage": "market_analysis",
    "title": "市场分析师",
    "status": "running",
    "raw_task_status": "processing",
    "progress": 35,
    "message": "正在分析市场趋势和成交结构",
    "started_at": "2026-06-11T10:00:00+08:00",
    "completed_at": null,
    "artifact_id": null,
    "report_url": null
  }
}
```

阶段状态枚举：

- `pending`
- `running`
- `completed`
- `failed`
- `skipped`

终态事件：

- `stock_analysis.completed`
- `stock_analysis.failed`
- `stock_analysis.timed_out`
- `stock_analysis.cancelled`

兼容当前 Agent UI 时，也可以继续发：

- `tool_started`
- `tool_progress`
- `tool_completed`
- `tool_failed`

但右侧执行栏最终应优先使用 `stock_analysis.stage`。

## 前端设计

### 页面布局契约

`/agent` 维持现有三栏结构：

```text
┌───────────────┬──────────────────────────────────────┬────────────────┐
│ SessionRail   │ Main conversation                     │ ToolRail       │
│ 会话列表       │ Header + messages + config + composer │ 执行步骤/证据    │
└───────────────┴──────────────────────────────────────┴────────────────┘
```

布局规则：

- 左栏 `SessionRail` 只负责会话列表、新建、重命名、删除，不放单股配置。
- 中间 `main` 是唯一的用户交互区域：消息流、单股配置卡片、composer 都在这里。
- 右栏 `ToolRail` 只负责展示执行步骤、阶段状态、耗时、报告链接和错误，不放可编辑配置表单。
- 单股配置卡片必须出现在中间消息流底部、composer 上方；打开配置卡片后 composer 仍可见但提交按钮应避免和卡片主提交动作冲突。
- desktop 维持左栏 288px、右栏 360px 的现有节奏；中间区域自适应。
- tablet/mobile 隐藏左右栏时，配置卡片仍在中间流中；执行步骤可以通过现有移动入口或后续抽屉展示，但不能挤占配置卡片。
- 配置卡片不是 modal。除非屏幕宽度不足，否则不要用全屏弹窗打断聊天上下文。

### `/agent` 入口

`+` 菜单包含：

- 研究目标
- 单股分析
- 上传/引用文件
- 其他快捷提示词

阶段性行为：

1. 第一阶段：点击单股分析打开中间对话区配置卡片，不自动发送。
2. 配置卡片提交后，前端发送用户可读摘要和机器可读 metadata。
3. 后端识别 metadata 后直接执行指定工具；在该链路完成前，不应把配置卡片标记为已完全绕过 LLM。

`+` 菜单交互：

- 菜单项使用图标 + 文案：研究目标、单股分析、上传/引用文件、快捷提示词。
- 点击“单股分析”关闭菜单并创建一个本地 `stockConfigDraft`。
- 如果当前正在运行 Agent，菜单项 disabled，并显示当前任务运行中。
- 如果已有未提交配置卡片，再次点击“单股分析”聚焦已有卡片，不创建第二张。

### 单股配置卡片字段

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| 股票代码 | 输入框 + 自动规范化提示 | 空 | 支持 A 股、港股、美股格式识别；失焦后展示规范化结果 |
| 市场类型 | 下拉框 | 自动识别，兜底 A 股 | A 股、港股、美股；用户可覆盖自动识别 |
| 分析日期 | 日期选择 | 今天 | 使用本地日期；不能晚于今天 |
| 分析深度 | 分段控件 | 标准 | 快速、基础、标准、深度、全面 |
| 分析师团队 | checkbox group | 市场、基本面 | 市场、基本面、新闻、社媒；至少选择一个 |
| 情绪分析 | switch | 开 | 传给 `include_sentiment` |
| 风险评估 | switch | 开 | 传给 `include_risk` |
| 快速分析模型 | select | 已启用模型 | 传给 `quick_analysis_model` |
| 深度决策模型 | select | 已启用模型 | 传给 `deep_analysis_model` |
| 补充问题 | textarea | 空 | 传给 `custom_prompt`，最多 1000 字 |
| 等待完成 | switch + 数字输入 | 开，900 秒 | 传给 `wait_for_completion` 和 `wait_timeout_seconds` |

约束：

- A 股默认禁用社媒分析，并展示原因。
- 没有启用模型时，提交按钮禁用，并提示去配置模型。
- 股票代码校验必须与当前 Agent 后端规范化逻辑一致，或抽为共享逻辑。
- 提交前展示配置摘要，例如：
  `600519 / A股 / 标准 / 市场+基本面 / 情绪+风险 / qwen-turbo -> qwen-max`
- 配置卡片提交后，在会话中显示用户可读摘要，完整 payload 存入 metadata。

### 配置卡片布局

卡片使用两段式布局，不嵌套卡片：

```text
┌────────────────────────────────────────────────────────────┐
│ 单股分析                                                     │
│ 600519 / A股 / 标准 / 市场+基本面 / 情绪+风险 / 模型摘要       │
├────────────────────────────────────────────────────────────┤
│ 股票代码        市场类型        分析日期                      │
│ 分析深度        分析师团队 checkbox group                    │
│ 情绪分析        风险评估        等待完成 + timeout             │
│ 快速模型        深度模型                                      │
│ 补充问题 textarea                                           │
├────────────────────────────────────────────────────────────┤
│ 取消       保存到输入框       开始分析                         │
└────────────────────────────────────────────────────────────┘
```

具体要求：

- 卡片标题行显示“单股分析”和当前摘要，不使用营销式说明文案。
- 第一行字段：股票代码、市场类型、分析日期。
- 第二行字段：分析深度、分析师团队。
- 第三行字段：情绪分析、风险评估、等待完成、等待秒数。
- 第四行字段：快速分析模型、深度决策模型。
- 补充问题 textarea 独占一行。
- 底部操作固定为：取消、保存到输入框、开始分析。
- “保存到输入框”只生成自然语言摘要，不调用工具。
- “开始分析”才提交 metadata direct invocation。
- 校验错误显示在对应字段下方；卡片顶部只显示阻断性摘要，例如模型未配置。
- 运行中卡片进入只读态，按钮变成“运行中”和“查看任务”。
- 完成后卡片显示 `task_id`、报告链接、最终状态；不在卡片中生成投资结论正文。

### Structured metadata

配置卡片提交时，用户消息 content 是可读摘要，机器参数进入 metadata：

```json
{
  "source": "research-agent-page",
  "mode": "stock_analysis_workflow",
  "tool_name": "stock_analysis",
  "tool_arguments": {
    "mode": "single",
    "symbol": "600519",
    "market_type": "A股",
    "analysis_date": "2026-06-11",
    "research_depth": "标准",
    "selected_analysts": ["market", "fundamentals"],
    "include_sentiment": true,
    "include_risk": true,
    "language": "zh-CN",
    "quick_analysis_model": "qwen-turbo",
    "deep_analysis_model": "qwen-max",
    "custom_prompt": "重点解释估值和风险",
    "wait_for_completion": true
  }
}
```

后端看到该 metadata 时应直接执行指定 workflow，不让 LLM 改写参数。实现时必须新增或扩展 Agent runtime 的 direct tool invocation 分支，否则这段 metadata 只是上下文提示，不能满足“不让 LLM 改写参数”的目标。

direct invocation 规则：

- metadata 中 `tool_name=stock_analysis` 且 `tool_arguments.mode=single` 时，runtime 直接调用 tool registry。
- direct invocation 必须创建普通 attempt、写入 user message、写入 tool events，保证历史回放一致。
- direct invocation 不向模型发送该配置消息来决定是否调用工具。
- 工具执行结果回来后，Agent 可以再用报告内容生成解释；如果报告未完成，只能说明状态。
- direct invocation 失败时返回结构化错误消息，不重新让 LLM 猜参数。

## React 与 Workflow 边界

React 负责：

- 表单草稿状态。
- 股票代码输入提示和提交前格式校验。
- 模型下拉框加载和禁用状态。
- A 股禁用社媒分析的 UI 约束。
- 把表单值转换为结构化 payload。
- 展示用户可读摘要。
- 渲染后端事件、任务状态、报告链接。

React 不负责：

- 推断下一阶段。
- 人工推进 progress。
- 本地把阶段标为 completed/failed。
- 在没有报告时拼接最终分析结论。
- 根据本地 timeout 认定任务失败。

## 后端设计

### Workflow 服务

建议新增或保留：

- `backend/app/services/research/agent/stock.py`

核心类：

- `StockAnalysisWorkflow`
- `StockAnalysisWorkflowContext`
- `StockAnalysisStageResult`
- `StockAnalysisWorkflowResult`

核心方法：

- `run_single(payload, context)`
- `emit_stage(stage, status, progress, message, ...)`
- `save_task_state(...)`
- `save_report_artifact(...)`
- `wait_bounded(...)`

第一阶段允许 `run_single` 内部通过 adapter 调用现有单股任务创建和队列提交逻辑，但必须把以下边界固定下来：

- 工具输入统一走同一个 payload normalize/validate helper。
- `single_stock_analysis` 和 `stock_analysis` 不复制两套参数处理逻辑。
- adapter 只能调用旧入口的公开函数或 service，不能修改旧 DAG 内部文件。
- wait timeout 只表示等待窗口结束，不代表任务失败。
- completed 后必须通过真实报告读取路径生成摘要。
- failed 后不能调用总结逻辑生成看似成功的结论。

### Baseline 对比

新增 baseline fixture，固定至少三组输入：

- A 股：`600519`，标准深度，market + fundamentals。
- 港股：`0700.HK` 或 `HK00700`，标准深度，market + news。
- 美股：`AAPL`，快速深度，market。

对比方式：

- 旧路径：通过现有 `single_stock_analysis` 或旧单股 service 提交任务。
- 新路径：通过 `stock_analysis` direct invocation 提交同等 payload。
- 不要求 LLM 文本逐字一致。
- 必须对比结构字段：`task_id`、`symbol`、`market_type`、status transition、progress、report URL、summary/recommendation/risk/key_points 字段存在性。
- 必须对比权限行为：用户 A 不能读用户 B 的 task/report。
- 必须保存 baseline fixture 的输入和预期结构，避免后续实现自由改语义。

### 阶段模块

第一阶段不新增阶段子目录、伪造合成词或其它多词目录。新增文件必须遵守命名约束，使用单个真实单词：

- `backend/app/services/research/agent/stock.py`：Agent-facing 单股 workflow 外壳，负责参数归一化、权限过滤、队列 adapter、等待窗口和结果绑定。
- `backend/app/services/research/agent/stage.py`：阶段计划和阶段标题，供后端事件与前端执行栏复用。
- `backend/app/services/research/agent/direct.py`：结构化 metadata 直达工具执行，避免 LLM 改写已确认参数。

每个阶段模块应满足：

- 输入输出结构化。
- 不读取或信任 payload.user_id。
- 失败返回明确错误类型。
- 可以单独测试。
- 不直接写前端状态，只通过 workflow 写事件和任务状态。

## 与旧 LangGraph 的迁移策略

### Phase 0：冻结旧 DAG 边界

- 保留旧 LangGraph DAG。
- 明确旧 DAG 当前产出的报告字段、状态字段和任务字段。
- 增加对当前单股分析结果结构的回归测试。
- 给旧 DAG 相关目录加测试保护和迁移说明：第一阶段禁止修改旧 DAG 内部实现。

### Phase 1：Agent 单股入口收敛

- 保持当前 `single_stock_analysis` 真实队列接入。
- 增加 `stock_analysis` 单股入口。
- `single_stock_analysis` 改为兼容别名，调用同一 helper/workflow。
- `stock_analysis_status` / `stock_analysis_report` 继续按 `task_id` 读取当前用户自己的任务和报告。
- 前端按本规格的三栏布局契约增加单股配置卡片。
- 后端支持 structured metadata direct tool invocation，避免 LLM 改写配置卡片参数。
- 新入口必须与旧 DAG baseline 做结构兼容性对比。

### Phase 2：Workflow 外壳

- 引入 `StockAnalysisWorkflow`。
- 第一版只能通过 adapter 调用旧 helper 或旧 service，不能改旧 DAG 内部实现。
- Workflow 必须发 `stock_analysis.stage` 事件。
- 右侧执行栏按当前 attempt 渲染阶段。

### Phase 3：Skill 化拆分

- 在新 workflow 旁路实现中逐步实现数据准备、分析师、辩论、风险、报告生成 skill。
- 每拆一个阶段，增加对应单元测试和集成测试。
- 新 skill 输出必须能生成现有报告系统需要的字段。
- 每个新 skill 必须与旧 DAG baseline 做结构兼容性对比。

### Phase 4：新旧并行验证

- 旧 `/analysis/single` 继续走旧路径，作为用户可见基线。
- `/agent` 走新 Agent workflow。
- 两条路径并行存在，直到用户明确批准切换。
- 并行期间任何差异必须记录为兼容、改进或回归。

### Phase 5：后续替换提案

本规格不批准删除或替换 LangGraph DAG。后续如要替换，必须单独提交提案，并至少满足：

- 单股标准路径结果字段与旧报告兼容。
- 任务中心、报告页、下载功能正常。
- 关键回归测试通过。
- 至少覆盖 A 股、港股、美股基本代码规范化。
- pending/processing/failed/timeout 不被总结成 completed。
- 用户明确批准切换旧 `/analysis/single`。

## 等待策略

- 单股默认 `wait_for_completion=true`。
- 默认等待 900 秒；最大等待 1800 秒。
- timeout 不是 failed，应返回 `wait_timed_out=true`。
- worker 未运行时，应提示“任务已入队但 worker 未处理”，并给出检查建议。
- Agent 最终回答必须明确区分：
  - 已提交
  - 等待中
  - 已完成并读取报告
  - 失败
  - 超时但仍在执行

## 权限和隔离

- 所有任务、报告、artifact 查询都必须使用 `context.principal.user_id`。
- 工具不能接受或信任 payload 里的 `user_id`。
- admin 在普通 Agent 模式下也不默认跨用户读取私有分析。
- report/task 链接不能暴露其他用户资源。
- structured metadata 中的 tool 参数必须走同样权限校验。

## 错误处理

- 股票代码缺失：返回 `config_required`，提示示例格式。
- 股票代码格式错误：前端阻止提交；后端也返回 `config_required`。
- 市场识别冲突：要求用户选择市场。
- 没有启用模型：前端禁用提交，后端返回 `config_required`。
- 模型 API Key 缺失：后端返回明确缺失模型和 provider。
- 数据源无数据：返回“无可用历史数据/可能停牌/退市/代码不支持”。
- worker 未运行：返回“任务已入队但 worker 未处理”。
- 阶段失败：写入 failed stage event 和错误原因。
- completed 但报告缺失：说明报告尚未生成或读取失败，不能生成最终投资结论。

## 共享前端模块

建议从旧单股页面和当前 Agent 页面抽出：

- `options.ts`
  - 市场类型枚举
  - 分析深度选项
  - 分析师选项
  - 分析师中文名和工具 id 映射
- `symbol.ts`
  - 股票代码识别
  - 股票代码规范化
  - 股票代码提示文案
- `payload.ts`
  - 表单值转 `StockAnalysisPayload`
  - payload 转用户可读摘要
- `models.ts`
  - 已启用模型读取
  - quick/deep 默认模型选择
  - 无模型配置时的禁用状态

旧单股页面和 Agent 配置卡片都引用这些模块，避免逻辑漂移。

## 测试计划

### 后端单元测试

- `stock_analysis` 创建真实单股 task。
- `single_stock_analysis` 兼容工具调用同一 helper/workflow。
- `stock_analysis` 不修改旧 DAG 模块，测试可用 import/path snapshot 或 mutation guard 覆盖关键文件。
- `stock_analysis_status` 只能读取当前用户任务。
- `stock_analysis_report` 只能读取当前用户报告。
- A 股、港股、美股代码规范化。
- A 股 social analyst 默认 skipped。
- 模型未配置返回 `config_required`。
- wait timeout 返回 pending/processing，不返回 failed。
- completed 后读取真实报告。
- failed 后不生成假总结。
- structured metadata direct invocation 不经过 LLM 改写参数。
- baseline fixture 覆盖 A 股、港股、美股三组输入。

### Workflow 测试

- 单股标准 workflow 阶段顺序正确。
- `selected_analysts` 能跳过未选分析师。
- `include_risk=false` 跳过风险阶段。
- 阶段事件包含 `attempt_id`、`task_id`、`stage`、`status`、`progress`。
- 阶段失败写入 failed event。
- 历史事件可恢复右侧步骤。

### 前端单元测试

- `+` 菜单点击单股分析打开配置卡片，不直接发送。
- 配置卡片位于中间消息流底部、composer 上方，不占用右侧执行栏。
- 再次点击“单股分析”聚焦已有卡片，不创建重复卡片。
- “保存到输入框”只填充自然语言摘要，不调用工具。
- “开始分析”提交 metadata direct invocation。
- 运行中卡片只读，并展示 task/report 链接。
- 单股表单提交完整 payload。
- A 股选择时社媒分析禁用。
- 模型未配置时提交按钮禁用。
- 股票代码规范化覆盖 A 股、港股、美股。
- 配置摘要包含股票、市场、深度、分析师和模型。
- 历史会话回放能显示当时配置和结果。

### 集成测试

- `/agent` 通过配置卡片提交 600519 标准分析。
- direct invocation 生成 user message、attempt、tool events，可历史回放。
- 右侧执行步骤只显示当前 attempt 的 stock analysis 阶段。
- 任务进入 `/tasks` 并可查看状态。
- 完成后 `/reports/view/{task_id}` 可打开报告。
- Agent 能读取报告并总结。
- pending 或 processing 任务不会被总结成已完成。
- 新路径与旧 DAG baseline 的结构字段兼容。

### 回归测试

- 旧 `/analysis/single` 仍可提交任务。
- 旧 `/analysis/single` 仍走旧 DAG 路径，没有被切到新 workflow。
- `/tasks` 任务列表不受影响。
- `/reports` 报告详情和下载不受影响。
- 当前 research-agent 普通聊天、web_search、Alpha、correlation、swarm 等工具不受影响。

## 验收标准

- 用户在 `/agent` 可以通过单股配置卡片提交一次完整单股分析。
- payload 包含旧单股页面的全部关键选项。
- Agent 不再依赖 LLM 猜关键股票分析参数。
- 用户可以在配置卡片中明确选择股票代码、市场、日期、深度、分析师、情绪、风险、quick/deep 模型、补充问题和等待策略。
- 单股 workflow 产生真实 `task_id`、阶段事件和报告链接。
- 旧 LangGraph DAG 内部实现无改动，并有 baseline 对比证据。
- 旧 `/analysis/single` 仍作为基线入口可用，没有被迁移或替换。
- 右侧执行栏展示当前 attempt 的阶段进度。
- 任务中心、Agent 右栏、报告页状态一致。
- pending/processing/failed/timeout 状态表达清楚。
- 用户不能读取其他用户的 task/report。
- 旧单股、任务、报告页面继续可用。
- 本阶段不删除、不替换 LangGraph DAG。

## Review 结论

该规格收敛为第一阶段只做单股分析迁移，并修正了旧合并稿的问题：

- 不再把“配置卡片”和“后端真实接入”混为同一阶段。
- 不再把“Skill”当作完整长流程的唯一实现方式。
- 不再让 Agent 自由管理股票分析阶段。
- 不再允许实现者自由发挥页面布局；配置卡片、三栏边界、提交流程都有明确契约。
- 明确了 Workflow 与 Skill 的分工。
- 明确当前实现仍是旧 LangGraph DAG 入队，迁移必须分阶段完成。
- 明确旧 DAG 是不可变 baseline，不是本阶段改造对象。
- 明确 structured metadata 必须有后端 direct tool invocation 支持，否则不能宣称参数绕过 LLM。
- 明确 LangGraph 删除或旧页面切换都不属于本规格授权范围。

推荐执行顺序：

1. 新增 `stock_analysis` 单股入口，并让 `single_stock_analysis` 共用同一 helper。
2. 后端支持 structured metadata direct tool invocation。
3. 前端增加单股配置卡片。
4. 建立旧 DAG baseline fixture 和结构兼容性对比。
5. 引入 `StockAnalysisWorkflow` 外壳和 stage events。
6. 在新 workflow 旁路阶段性实现 skills。
7. 保持旧单股页面和旧 DAG 作为对照组，直到另一个明确批准的替换提案出现。
