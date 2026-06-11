# Agent 内嵌股票分析配置与阶段化 Skill 规格说明

日期：2026-06-11

## 摘要

当前研究 Agent 已经可以调用现有单股分析 DAG，但交互仍然是“用户输入自然语言，模型推断参数后直接调用工具”。这导致用户无法像原“单股分析”页面一样明确选择市场、日期、分析深度、分析师团队、情绪/风险选项和模型配置，也导致右侧执行步骤只能看到一个黑盒工具调用，不能清楚展示分析卡在哪个阶段。

本规格的目标是：在 `/agent` 中加入结构化的单股/批量分析配置入口，并把股票分析执行从“整块 DAG 黑盒”逐步改造成 `stock_analysis_skill` 阶段化 workflow。用户点击 `+` 后选择“单股分析”或“批量分析”，先在中间对话区填写或确认完整参数，再提交给 Agent。后端按固定阶段执行股票分析 skill，每个阶段写入标准进度事件，Agent 负责展示步骤、等待、读取报告和解释结果，而不是让模型凭提示词猜参数。

## 背景与问题

### 原单股分析页面能力

`/analysis/single` 目前提供完整表单：

- 市场类型：A股、港股、美股。
- 股票代码输入和规范化。
- 分析日期。
- 1-5 级分析深度：快速、基础、标准、深度、全面。
- 分析师团队：市场、基本面、新闻、社媒。
- A 股禁用社媒分析的提示和约束。
- 情绪分析开关。
- 风险评估开关。
- 快速分析模型。
- 深度决策模型。
- 提交后进入现有分析队列。

这些选项决定了真实 DAG 的执行范围、模型成本、耗时和报告内容。

### 当前 Agent 体验问题

当前 `/agent` 中的股票分析存在以下问题：

- `+` 菜单更像快捷提示词菜单，不是配置入口。
- 单股分析由 LLM 从自然语言中推断参数，用户不能显式确认。
- 后端工具支持部分参数，但前端没有暴露完整选择控件。
- 用户无法确认本次到底使用了哪些分析师、深度和模型。
- 同一个 Agent 会话中，股票分析和普通聊天混在一起，缺少“本次分析配置摘要”。
- 现有 `single_stock_analysis` 更接近“提交整块 DAG 并等待结果”，右侧执行步骤无法稳定展示 DAG 内部阶段。
- 现有 DAG 进度字段和 Agent 事件流不是同一套机制，需要明确桥接或重构为阶段化 skill。
- 批量分析工具不应在未接入真实批量分析队列前作为完整功能开放。

## 目标

- 在研究 Agent 中完整迁移原单股分析的可选项。
- 让用户在提交 Agent 股票分析前明确选择或确认参数。
- 保留原 `/analysis/single` 和 `/analysis/batch` 页面。
- 前端通过结构化 payload 调用 Agent 工具，避免靠自然语言猜参。
- 后端以 `stock_analysis_skill` 作为 Agent 股票分析的执行入口，按固定阶段顺序推进。
- 阶段内部可以复用现有 DAG 节点、分析师实现、数据准备、任务状态和报告系统。
- 每个阶段发出标准 Agent 事件和任务进度，右侧栏能展示当前阶段、进度和失败原因。
- Agent 继续负责对话上下文、等待完成、读取报告和生成解释。
- 每次 Agent attempt 都记录当时的股票分析配置，便于历史会话复现。
- 批量分析第一版只在真实接入原批量队列后开放。

## 非目标

- 第一版不删除 TradingAgents DAG；先把它包到可观察的 skill/workflow 边界里，再逐步拆分节点。
- 不删除原单股分析或批量分析页面。
- 不把 Agent 模型和股票分析模型混成同一个配置项。
- 不允许 Agent 在 pending、failed 或缺数据时编造分析结果。
- 不把长耗时分析同步阻塞在前端请求里无限等待。
- 不在第一版实现新的选股、调仓、下单或交易执行能力。
- 不让 LLM 自由决定股票分析阶段顺序；阶段顺序必须由代码定义。

## 推荐方案

采用“中间对话区配置卡片 + 阶段化 `stock_analysis_skill`”方案。

核心原则：

- 配置 UI 不占用右侧执行栏。
- 用户用表单选择参数，系统把参数原样交给后端 skill，不让大模型改参数。
- 后端 skill 以确定性阶段推进，阶段内部可以调用现有 DAG 节点或 helper。
- 右侧执行栏展示 skill 阶段，而不是只展示一个黑盒工具。

页面结构：

```text
┌──────────────┬────────────────────────────────────────┬─────────────────┐
│ 会话列表      │ 对话区                                  │ 执行步骤          │
│              │                                        │                 │
│ + 新会话      │ ┌ 单股分析配置 ──────────────────────┐   │ 股票分析 Skill    │
│ 历史会话 A    │ │ 股票代码 [600519]                   │   │ 1. 校验股票 完成  │
│ 历史会话 B    │ │ 市场 [A股] 日期 [2026/06/11]         │   │ 2. 数据准备 完成  │
│              │ │ 深度 [快速][基础][标准✓][深度][全面] │   │ 3. 市场分析 运行中│
│              │ │ 分析师 [市场✓][基本面✓][新闻]        │   │ 4. 报告生成 等待中│
│              │ │ 模型 [快速模型] [深度模型]           │   │                 │
│              │ │ [取消]                    [开始分析] │   │ 当前研究目标      │
│              │ └────────────────────────────────────┘   │                 │
├──────────────┴────────────────────────────────────────┴─────────────────┤
│ [+]  输入框：例如：分析贵州茅台估值和风险                      [发送]     │
└──────────────────────────────────────────────────────────────────────────┘
```

### 入口

`/agent` 输入框左侧 `+` 菜单改为动作入口：

- 研究目标
- 单股分析
- 批量分析（第一版可禁用，直到后端真实 batch 队列接通）
- 上传/引用文件
- 其他快捷提示词

点击“单股分析”或“批量分析”时只在中间对话区打开配置卡片，不直接发送消息、不直接运行 Agent。右侧栏始终保留给执行步骤和当前研究目标，不被配置 UI 覆盖。

### 单股分析配置卡片

面板字段与原单股分析保持一致：

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| 股票代码 | 输入框 | 空 | 支持 A 股、港股、美股格式识别和规范化 |
| 市场类型 | 下拉框 | 自动识别，兜底 A股 | A股、港股、美股 |
| 分析日期 | 日期选择 | 今天 | 使用本地日期 |
| 分析深度 | 单选卡片 | 标准 | 1-5 级 |
| 分析师团队 | 多选卡片 | 市场、基本面 | 支持市场、基本面、新闻、社媒 |
| 情绪分析 | 开关 | 开 | 传给 `include_sentiment` |
| 风险评估 | 开关 | 开 | 传给 `include_risk` |
| 快速分析模型 | 下拉框 | 系统已启用模型 | 传给 `quick_analysis_model` |
| 深度决策模型 | 下拉框 | 系统已启用模型 | 传给 `deep_analysis_model` |
| 补充问题 | 文本框 | 空 | 传给 `custom_prompt` |
| 等待完成 | 开关 | 开 | 默认最多等待 10 分钟 |

约束：

- A 股默认禁用社媒分析，并展示原因。
- 如果没有启用模型，不显示不可用的示例模型作为可提交选项；应提示去配置模型。
- 股票代码校验必须和原单股分析页面保持一致或提取为共享逻辑。
- 提交前展示一行配置摘要，例如：`600519 / A股 / 标准 / 市场+基本面 / 情绪+风险 / minimax-text-01 -> minimax-reasoning`。
- 配置卡片提交后变成会话中的用户消息摘要，历史会话可回看当时配置。

### 批量分析配置卡片

批量分析第一版字段。后端真实 batch 队列未接通前，菜单项应禁用并提示“批量分析正在接入真实队列”，不能展示为可执行入口。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| 股票列表 | 多行输入 | 空 | 支持逗号、空格、换行分隔 |
| 市场类型 | 下拉框 | 自动识别或用户选择 | 初版建议同一批次使用同一市场 |
| 分析日期 | 日期选择 | 今天 | 传给每个任务 |
| 分析深度 | 单选卡片 | 标准 | 与单股一致 |
| 分析师团队 | 多选卡片 | 市场、基本面 | 与单股一致 |
| 情绪分析 | 开关 | 开 | 与单股一致 |
| 风险评估 | 开关 | 开 | 与单股一致 |
| 快速分析模型 | 下拉框 | 系统已启用模型 | 与单股一致 |
| 深度决策模型 | 下拉框 | 系统已启用模型 | 与单股一致 |
| 批次标题 | 输入框 | 自动生成 | 传给 batch |
| 批次说明 | 文本框 | 空 | 传给 batch description |
| 等待完成 | 开关 | 开 | 默认最多等待 2 分钟，只总结已完成项 |

约束：

- 保留现有最多 10 只股票限制。
- 第一版强制同市场批量分析；如果检测到混合市场，应要求用户拆批次。
- 批量分析必须接入真实批量队列后才能在菜单开放；如果后端仍是占位，不应展示为可执行入口。

## 股票分析 Skill 设计

`stock_analysis_skill` 是 Agent 股票分析的后端工作流入口。它不是一段让 LLM 自由发挥的 prompt，而是一套由代码定义的固定阶段 workflow。

### 阶段顺序

单股分析阶段：

1. 输入校验：校验股票代码、市场、日期、模型配置和权限。
2. 数据准备：准备行情、基础信息、新闻等必要数据。
3. 分析师阶段：按用户选择运行市场、基本面、新闻、社媒分析。
4. 研究辩论阶段：运行多空研究员和研究经理。
5. 交易决策阶段：生成交易员视角的策略判断。
6. 风险评估阶段：运行激进、保守、中性和风险经理评估。
7. 报告生成阶段：整理结构化报告并保存到现有报告系统。
8. Agent 总结阶段：Agent 读取真实报告，生成会话内解释。

大阶段按顺序推进；分析师阶段内部可以并行，避免把原 DAG 全部强行串行化导致耗时显著增加。

### 阶段事件

每个阶段至少发出：

```json
{
  "event": "stock_analysis.stage",
  "attempt_id": "attempt-id",
  "task_id": "task-id",
  "stage": "market_analysis",
  "title": "市场分析师",
  "status": "running",
  "progress": 35,
  "message": "正在分析市场趋势和成交结构"
}
```

状态枚举：

- `pending`
- `running`
- `completed`
- `failed`
- `skipped`

右侧执行步骤基于这些事件渲染。现有 `progress/current_step/message` 可以作为过渡数据源，但最终应统一到 Agent attempt 事件流。

### 与现有 DAG 的关系

第一阶段不要求一次性重写现有 DAG。实现路径：

1. 先在 `stock_analysis_skill` 外层包裹现有 DAG，补齐阶段事件。
2. 能从现有 runner/progress callback 获得的节点进度，映射到 skill 阶段。
3. 对无法精确映射的黑盒段，显示为“DAG 执行中”，附当前 `progress/current_step/message`。
4. 后续逐步把数据准备、分析师、辩论、风险、报告生成拆为明确函数或节点。

目标是逐步从“黑盒 DAG”迁移到“可观察 workflow”，而不是一次性推翻现有分析引擎。

## 交互流程

### 单股分析

1. 用户点击 `+`。
2. 用户选择“单股分析”。
3. 前端在中间对话区打开配置卡片。
4. 用户填写股票代码并选择参数。
5. 用户点击“开始分析”。
6. 前端把结构化请求追加到当前 Agent 会话。
7. 消息区展示用户可读摘要，而不是裸 JSON：
   `请按以下配置运行单股分析：600519，A股，标准深度，市场+基本面，包含情绪和风险。`
8. Agent attempt 中记录完整 structured payload。
9. 后端启动 `stock_analysis_skill`。
10. 右侧执行步骤展示 skill 阶段、状态、task_id、当前进度和报告链接。
11. 如果等待窗口内完成，Agent 读取报告并总结。
12. 如果超时仍在执行，Agent 返回任务链接和当前阶段，并说明可稍后继续询问。

### 批量分析

1. 用户点击 `+`。
2. 用户选择“批量分析”。
3. 前端在中间对话区打开批量配置卡片。
4. 用户输入股票列表和统一参数。
5. 前端校验数量、格式、市场。
6. 后端创建 batch，并为每只股票启动独立 `stock_analysis_skill` 或等价真实分析任务。
7. Agent 展示 batch_id、任务列表、状态链接。
8. 完成项可以总结；未完成项必须标记 pending。

### 自然语言兜底

用户仍可直接输入“帮我分析 600519”。处理策略：

- 如果只缺少非关键参数，使用默认配置并在回答中明确说明。
- 如果缺少股票代码、模型不可用、市场无法识别，应追问或返回配置缺口。
- 如果用户明确说“按默认配置分析”，可以直接调用工具。
- 如果用户说“打开单股分析配置”，前端应打开配置卡片，而不是发送给模型猜测。

## 前端设计

### 与现有 React 逻辑的统一

确定性 workflow 不应和 React 页面逻辑冲突。二者边界如下：

- React 负责 UI 草稿状态：用户正在填写的股票代码、市场、日期、深度、分析师、模型和补充问题。
- React 负责把表单值转换成结构化 payload，并展示用户可读摘要。
- React 不负责决定分析阶段顺序，也不在前端实现股票分析状态机。
- 后端 `stock_analysis_skill` 是 workflow 状态源，负责创建任务、推进阶段、保存报告和发出事件。
- 前端右侧执行栏只订阅和渲染后端事件：`stage/status/progress/message/task_id/report_url`。
- 原 `/analysis/single` 页面、Agent 配置卡片、任务中心应逐步共用同一套参数 schema 和状态事件，而不是各自维护一套分析流程。

统一后的数据流：

```text
React 表单草稿
  ↓ 用户点击开始分析
结构化 payload
  ↓
后端 stock_analysis_skill
  ↓
stage event / task status / report
  ↓
React 执行步骤栏、任务中心、报告页统一展示
```

这意味着 React 可以继续使用现有组件和 hook，但它只能是 workflow 的“输入和显示层”，不能成为 workflow 的第二个执行引擎。

### 共享配置模块

从 `single-analysis-page.tsx` 中抽出共享模块：

- `analysisOptions.ts`
  - 市场类型枚举。
  - 分析深度选项。
  - 分析师选项。
  - 分析师中文名和工具 id 映射。
- `stockSymbol.ts`
  - 股票代码识别。
  - 股票代码规范化。
  - 股票代码提示文案。
- `analysisPayload.ts`
  - 表单值转 `AnalysisToolPayload`。
  - payload 转用户可读摘要。

原单股分析页面和 Agent 配置面板都引用这些共享模块，避免两套逻辑漂移。

### 新组件

建议新增组件：

- `AgentStockAnalysisCard`
  - 渲染中间对话区的配置卡片。
  - 支持 `mode="single" | "batch"`。
- `StockAnalysisConfigForm`
  - 复用单股字段。
  - 输出结构化 payload。
- `BatchStockAnalysisConfigForm`
  - 批量股票列表和批次字段。
- `AnalysisModelSelect`
  - 统一加载已启用模型。
- `AnalysisConfigSummary`
  - 提交前摘要。

### Agent 页面改动

`research-agent-page.tsx` 需要：

- `+` 菜单点击股票分析项时在中间对话区插入配置卡片。
- 新增 `runStructuredToolPrompt(payload)` 或等价函数。
- structured payload 应进入 `appendMessage.metadata`。用户看到的是配置摘要；机器执行参数保存在 metadata。例如：

```json
{
  "source": "research-agent-page",
  "mode": "structured_tool",
  "tool_name": "stock_analysis_skill",
  "tool_arguments": {
    "symbol": "600519",
    "market_type": "A股",
    "analysis_date": "2026-06-11",
    "research_depth": "标准",
    "selected_analysts": ["market", "fundamentals"],
    "include_sentiment": true,
    "include_risk": true,
    "language": "zh-CN",
    "quick_analysis_model": "minimax-text-01",
    "deep_analysis_model": "minimax-reasoning",
    "custom_prompt": "重点解释估值和风险",
    "wait_for_completion": true
  }
}
```

用户消息 content 保持可读文本，metadata 保存机器可执行参数。右侧栏只读取执行事件，不承载配置 UI。

## 后端设计

### 结构化 Skill 执行

Agent 后端需要识别 `appendMessage.metadata.mode === "structured_tool"` 或后续更明确的 `mode === "stock_analysis_skill"`。

当 metadata 包含 `tool_name` 和 `tool_arguments` 时：

1. 校验当前用户是否有 skill/tool 权限。
2. 创建或绑定真实 `task_id`。
3. 启动 `stock_analysis_skill`。
4. 每个阶段写入标准 stage event。
5. 阶段内部调用现有 DAG/helper/分析服务。
6. 保存现有任务状态和报告。
7. 把真实报告交给模型生成最终自然语言总结；如果模型不可用，使用确定性摘要兜底。

这样可以避免模型把参数改错、漏传或 hallucinate。

### 工具参数

单股 skill 至少支持：

```json
{
  "symbol": "600519",
  "market_type": "A股",
  "analysis_date": "2026-06-11",
  "research_depth": "标准",
  "selected_analysts": ["market", "fundamentals"],
  "include_sentiment": true,
  "include_risk": true,
  "language": "zh-CN",
  "quick_analysis_model": "minimax-text-01",
  "deep_analysis_model": "minimax-reasoning",
  "custom_prompt": "重点解释估值和风险",
  "wait_for_completion": true,
  "wait_timeout_seconds": 600,
  "poll_interval_seconds": 5
}
```

批量 skill 至少支持：

```json
{
  "symbols": ["600519", "000001"],
  "market_type": "A股",
  "analysis_date": "2026-06-11",
  "research_depth": "标准",
  "selected_analysts": ["market", "fundamentals"],
  "include_sentiment": true,
  "include_risk": true,
  "language": "zh-CN",
  "quick_analysis_model": "minimax-text-01",
  "deep_analysis_model": "minimax-reasoning",
  "title": "A股组合批量分析",
  "description": "比较白酒和银行",
  "wait_for_completion": true
}
```

### 等待策略

- 单股默认等待 10 分钟，仍未完成则返回当前阶段、进度、任务链接和报告链接占位。
- 批量默认等待 2 分钟，只总结已完成项，未完成项显示当前阶段和 pending/running 状态。
- 超时不是失败，应返回 `wait_timed_out: true`、当前状态和链接。
- 如果 worker 未运行，应明确提示检查 worker，而不是让前端一直 pending。

## 数据与事件

每次 structured tool attempt 应保存：

- `attempt_id`
- `session_id`
- `tool_name`
- `tool_arguments`
- `skill_stages`
- 用户可读摘要
- `task_id` 或 `batch_id`
- 工具结果
- 生成的最终回答

右侧执行步骤必须按当前 attempt 过滤，不能显示同一会话第一次请求的旧步骤。股票分析阶段事件应在当前 attempt 下展示，而不是混入全局任务事件。

## 错误处理

- 股票代码格式错误：在前端阻止提交，并给出市场对应示例。
- 市场识别冲突：提示用户选择市场。
- 没有启用模型：阻止提交，引导去模型配置页。
- 模型 API Key 缺失：后端返回 `config_required`，前端展示明确原因。
- 数据源无历史数据：返回“无可用历史数据/可能停牌/退市/代码不支持”，不要泛化成网络错误。
- worker 未运行：返回“分析任务已入队但 worker 未处理”，附检查建议。
- 批量部分失败：展示每只股票状态，不能整体伪装成成功。

## 测试计划

### 前端单元测试

- `+` 菜单点击“单股分析”只打开配置面板，不直接发送。
- 配置卡片显示在中间对话区，不遮盖右侧执行栏。
- 单股表单能提交完整 payload。
- A 股选择时社媒分析禁用。
- 模型未配置时提交按钮禁用。
- 股票代码规范化覆盖 A 股、港股、美股。
- 配置摘要包含股票、市场、深度、分析师和模型。

### 后端单元测试

- structured tool metadata 能直接调用指定工具。
- structured tool 保留原始 `tool_arguments`，不经过 LLM 改写。
- 权限不足时拒绝执行。
- `stock_analysis_skill` 接收完整参数并创建或绑定真实任务。
- `stock_analysis_skill` 按固定阶段发出 stage event。
- 单股等待完成后读取真实报告。
- wait timeout 返回任务链接，不标记为 failed。
- 批量工具在未真实接入前不能返回假成功。

### 集成测试

- 在 `/agent` 通过配置面板提交 600519 标准分析。
- 右侧执行步骤只显示当前 attempt 的股票分析阶段。
- 任务进入 `/tasks` 并可查看状态。
- 完成后 Agent 能读取 `/reports/view/{task_id}` 对应报告并总结。
- 历史会话重新打开后能看到当时配置和结果。

### 回归测试

- 原 `/analysis/single` 仍可提交任务。
- 原 `/analysis/batch` 仍可提交任务。
- 原任务列表、报告详情、报告下载不受影响。

## 实施顺序

1. 抽出原单股分析页面的共享选项和校验逻辑。
2. 在 Agent 前端实现中间对话区单股分析配置卡片，但先不改后端执行路径。
3. 后端支持 structured metadata 启动 `stock_analysis_skill`。
4. 第一阶段用 skill 外层包裹现有 DAG，并映射现有进度到 stage event。
5. 接通单股 structured skill 提交流程。
6. 为单股路径补齐前后端测试。
7. 逐步把 DAG 中的数据准备、分析师、辩论、风险、报告生成拆成明确阶段。
8. 确认批量分析后端真实队列能力，修复或实现批量 skill。
9. 开放 Agent 批量分析配置卡片。
10. 做端到端验证并保留旧页面。

## 验收标准

- 用户在 `/agent` 中可以不写提示词，直接通过“单股分析”面板完成一次完整单股分析提交。
- 提交 payload 包含原单股页面所有关键选项。
- Agent 不再依赖 LLM 猜股票分析参数。
- 股票分析执行阶段能在右侧执行栏显示，不只是一个黑盒工具调用。
- 配置错误在提交前或工具执行前明确暴露。
- 右侧执行步骤、任务中心、报告详情三处状态一致。
- 原单股分析页面继续工作。
- 批量分析未真实接入前不展示为可用功能；接入后必须使用真实 batch 队列。

## 待 Review 的关键选择

1. `stock_analysis_skill` 第一版是否只包裹现有 DAG，还是直接拆出数据准备和分析师阶段？
2. 现有 DAG progress callback 到 Agent stage event 的映射表是否需要先写成配置表？
3. 旧 `/analysis/single` 是否也改为调用 `stock_analysis_skill`，还是先保留原执行路径？
4. 批量分析是否一开始就使用多个单股 skill 并发，还是继续沿用现有 batch service？
