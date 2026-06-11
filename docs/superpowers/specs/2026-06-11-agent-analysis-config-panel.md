# Agent 内嵌股票分析配置面板规格说明

日期：2026-06-11

## 摘要

当前研究 Agent 已经可以调用现有单股分析 DAG，但交互仍然是“用户输入自然语言，模型推断参数后直接调用工具”。这导致用户无法像原“单股分析”页面一样明确选择市场、日期、分析深度、分析师团队、情绪/风险选项和模型配置。

本规格的目标是：在 `/agent` 中加入结构化的单股/批量分析配置入口。用户点击 `+` 后选择“单股分析”或“批量分析”，先填写或确认完整参数，再提交给 Agent。提交时前端发送结构化工具请求，后端直接执行真实分析工具，Agent 负责等待、汇总和解释结果，而不是让模型凭提示词猜参数。

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
- 批量分析工具不应在未接入真实批量分析队列前作为完整功能开放。

## 目标

- 在研究 Agent 中完整迁移原单股分析的可选项。
- 让用户在提交 Agent 股票分析前明确选择或确认参数。
- 保留原 `/analysis/single` 和 `/analysis/batch` 页面。
- 前端通过结构化 payload 调用 Agent 工具，避免靠自然语言猜参。
- 后端复用现有单股/批量分析服务、队列、任务状态和报告系统。
- Agent 继续负责对话上下文、等待完成、读取报告和生成解释。
- 每次 Agent attempt 都记录当时的股票分析配置，便于历史会话复现。
- 批量分析第一版只在真实接入原批量队列后开放。

## 非目标

- 不重写 TradingAgents DAG。
- 不删除原单股分析或批量分析页面。
- 不把 Agent 模型和股票分析模型混成同一个配置项。
- 不允许 Agent 在 pending、failed 或缺数据时编造分析结果。
- 不把长耗时分析同步阻塞在前端请求里无限等待。
- 不在第一版实现新的选股、调仓、下单或交易执行能力。

## 推荐方案

采用“Agent 内嵌配置面板 + 结构化工具请求”方案。

### 入口

`/agent` 输入框左侧 `+` 菜单改为动作入口：

- 研究目标
- 单股分析
- 批量分析
- 上传/引用文件
- 其他快捷提示词

点击“单股分析”或“批量分析”时只打开配置面板，不直接发送消息、不直接运行 Agent。

### 单股分析配置面板

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
| 等待完成 | 开关 | 开 | 默认 bounded wait |

约束：

- A 股默认禁用社媒分析，并展示原因。
- 如果没有启用模型，不显示不可用的示例模型作为可提交选项；应提示去配置模型。
- 股票代码校验必须和原单股分析页面保持一致或提取为共享逻辑。
- 提交前展示一行配置摘要，例如：`600519 / A股 / 标准 / 市场+基本面 / 情绪+风险 / minimax-text-01 -> minimax-reasoning`。

### 批量分析配置面板

批量分析第一版字段：

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
| 等待完成 | 开关 | 开 | 有上限等待，不能无限阻塞 |

约束：

- 保留现有最多 10 只股票限制。
- 混合市场批量分析后续再做；第一版如果检测到混合市场，应要求用户拆批次或确认统一市场。
- 批量分析必须接入真实批量队列后才能在菜单开放；如果后端仍是占位，不应展示为可执行入口。

## 交互流程

### 单股分析

1. 用户点击 `+`。
2. 用户选择“单股分析”。
3. 前端打开配置面板。
4. 用户填写股票代码并选择参数。
5. 用户点击“开始分析”。
6. 前端把结构化请求追加到当前 Agent 会话。
7. 消息区展示用户可读摘要，而不是裸 JSON：
   `请按以下配置运行单股分析：600519，A股，标准深度，市场+基本面，包含情绪和风险。`
8. Agent attempt 中记录完整 structured payload。
9. 后端直接调用 `single_stock_analysis` 工具。
10. 右侧执行步骤展示真实工具调用、状态、task_id、报告链接。
11. 如果等待窗口内完成，Agent 读取报告并总结。
12. 如果超时仍在执行，Agent 返回任务链接，并说明可稍后继续询问。

### 批量分析

1. 用户点击 `+`。
2. 用户选择“批量分析”。
3. 前端打开批量配置面板。
4. 用户输入股票列表和统一参数。
5. 前端校验数量、格式、市场。
6. 后端创建 batch 和多个真实分析任务。
7. Agent 展示 batch_id、任务列表、状态链接。
8. 完成项可以总结；未完成项必须标记 pending。

### 自然语言兜底

用户仍可直接输入“帮我分析 600519”。处理策略：

- 如果只缺少非关键参数，使用默认配置并在回答中明确说明。
- 如果缺少股票代码、模型不可用、市场无法识别，应追问或返回配置缺口。
- 如果用户明确说“按默认配置分析”，可以直接调用工具。
- 如果用户说“打开单股分析配置”，前端应打开配置面板，而不是发送给模型猜测。

## 前端设计

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

- `AgentStockAnalysisDialog`
  - 管理弹窗/抽屉外壳。
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

- `+` 菜单点击股票分析项时打开配置面板。
- 新增 `runStructuredToolPrompt(payload)` 或等价函数。
- structured payload 应进入 `appendMessage.metadata`，例如：

```json
{
  "source": "research-agent-page",
  "mode": "structured_tool",
  "tool_name": "single_stock_analysis",
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

用户消息 content 保持可读文本，metadata 保存机器可执行参数。

## 后端设计

### 结构化工具执行

Agent 后端需要识别 `appendMessage.metadata.mode === "structured_tool"`。

当 metadata 包含 `tool_name` 和 `tool_arguments` 时：

1. 校验当前用户是否有工具权限。
2. 从工具注册表取工具。
3. 直接执行工具 handler。
4. 写入标准 tool_call / tool_result event。
5. 把工具结果交给模型生成最终自然语言总结，或使用 deterministic summary fallback。

这样可以避免模型把参数改错、漏传或 hallucinate。

### 工具参数

单股工具至少支持：

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

批量工具至少支持：

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

- 单股默认等待，但有硬超时。
- 批量默认等待较短窗口，只总结已完成项。
- 超时不是失败，应返回 `wait_timed_out: true`、当前状态和链接。
- 如果 worker 未运行，应明确提示检查 worker，而不是让前端一直 pending。

## 数据与事件

每次 structured tool attempt 应保存：

- `attempt_id`
- `session_id`
- `tool_name`
- `tool_arguments`
- 用户可读摘要
- `task_id` 或 `batch_id`
- 工具结果
- 生成的最终回答

右侧执行步骤必须按当前 attempt 过滤，不能显示同一会话第一次请求的旧步骤。

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
- 单股表单能提交完整 payload。
- A 股选择时社媒分析禁用。
- 模型未配置时提交按钮禁用。
- 股票代码规范化覆盖 A 股、港股、美股。
- 配置摘要包含股票、市场、深度、分析师和模型。

### 后端单元测试

- structured tool metadata 能直接调用指定工具。
- structured tool 保留原始 `tool_arguments`，不经过 LLM 改写。
- 权限不足时拒绝执行。
- 单股工具接收完整参数并入队。
- 单股等待完成后读取真实报告。
- wait timeout 返回任务链接，不标记为 failed。
- 批量工具在未真实接入前不能返回假成功。

### 集成测试

- 在 `/agent` 通过配置面板提交 600519 标准分析。
- 右侧执行步骤只显示当前 attempt 的工具步骤。
- 任务进入 `/tasks` 并可查看状态。
- 完成后 Agent 能读取 `/reports/view/{task_id}` 对应报告并总结。
- 历史会话重新打开后能看到当时配置和结果。

### 回归测试

- 原 `/analysis/single` 仍可提交任务。
- 原 `/analysis/batch` 仍可提交任务。
- 原任务列表、报告详情、报告下载不受影响。

## 实施顺序

1. 抽出原单股分析页面的共享选项和校验逻辑。
2. 在 Agent 前端实现单股分析配置面板，但先不改后端执行路径。
3. 后端支持 structured tool metadata 直调工具。
4. 接通单股 structured tool 提交流程。
5. 为单股路径补齐前后端测试。
6. 确认批量分析后端真实队列能力，修复或实现 `batch_stock_analysis`。
7. 开放 Agent 批量分析配置面板。
8. 做端到端验证并保留旧页面。

## 验收标准

- 用户在 `/agent` 中可以不写提示词，直接通过“单股分析”面板完成一次完整单股分析提交。
- 提交 payload 包含原单股页面所有关键选项。
- Agent 不再依赖 LLM 猜股票分析参数。
- 配置错误在提交前或工具执行前明确暴露。
- 右侧执行步骤、任务中心、报告详情三处状态一致。
- 原单股分析页面继续工作。
- 批量分析未真实接入前不展示为可用功能；接入后必须使用真实 batch 队列。

## 待 Review 的关键选择

1. Agent 中“单股分析”面板是弹窗还是右侧抽屉？
2. 批量分析第一版是否允许混合 A股/港股/美股，还是强制同市场？
3. structured tool 执行后是否仍调用 LLM 生成最终回答，还是先使用 deterministic summary？
4. 单股默认等待超时时间设置为 5 分钟、10 分钟还是跟随分析深度动态调整？
5. 旧 `/analysis/single` 是否增加“用 Agent 分析”按钮，还是先只保持原样？
