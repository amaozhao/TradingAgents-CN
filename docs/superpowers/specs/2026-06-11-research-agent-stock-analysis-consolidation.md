# 研究 Agent 合并单股/批量分析规格说明

日期：2026-06-11

## 摘要

TradingAgents-CN 需要把现有“单股分析”和“批量分析”逐步合并到研究 Agent 入口里。这里的“合并”不是重写股票分析引擎，而是让研究 Agent 成为统一交互入口，现有分析任务、队列、状态、报告和下载体系继续作为执行系统和事实来源。

第一版目标是：用户可以在 `/agent` 中自然语言请求单股或批量分析，Agent 调用真实分析服务提交任务，返回 `task_id` 或 `batch_id`、状态链接和报告链接；等任务完成后，用户可以继续让 Agent 读取真实报告并总结。

## 当前代码现状

- 旧前端入口：
  - `frontend/features/analysis/single-analysis-page.tsx`
  - `frontend/features/analysis/batch-analysis-page.tsx`
- 旧后端入口：
  - `backend/app/routers/analysis/single.py`
  - `backend/app/routers/analysis/list.py`
- 旧分析体系已有：
  - `SingleAnalysisRequest`
  - `BatchAnalysisRequest`
  - `AnalysisParameters`
  - `analysis_tasks`
  - `analysis_batches`
  - 队列提交
  - 任务状态查询
  - 报告查询和恢复
- 研究 Agent 已经有两个工具名：
  - `single_stock_analysis`
  - `batch_stock_analysis`
- 但这两个工具目前只是占位实现，只返回 payload，没有真正调用旧分析服务。
- 研究 Agent 目前已有：
  - session
  - message
  - event
  - attempt
  - artifact
  - 右侧执行步骤
- 最近已经修复了“执行步骤按 attempt 展示”的问题，所以后续股票分析工具事件必须继续带 `attempt_id`。

## 目标

- 让研究 Agent 成为单股/批量分析的首选入口。
- 复用现有分析服务，不在 Agent 里复制股票分析逻辑。
- 保留旧任务历史、任务状态页、报告页、报告下载、队列执行能力。
- 为研究 Agent 增加真实可用的股票分析工具：
  - 提交单股分析
  - 提交批量分析
  - 查询分析状态
  - 读取已完成报告
- 旧 `/analysis/single` 和 `/analysis/batch` 第一阶段继续可用。
- 所有任务、报告和 Agent 资源必须保持用户隔离。
- 长耗时分析必须异步执行，不能让一个 Agent 请求无限阻塞等待。

## 非目标

- 第一版不删除 `/analysis/single` 和 `/analysis/batch`。
- 不重写 `TradingAgentsGraph`。
- 不重写现有 simple analysis service。
- 不重写 queue service。
- 不重写 report storage。
- 不把 Agent 模型配置和股票分析的 `quick_analysis_model` / `deep_analysis_model` 混成一套。
- 不允许 Agent 在任务 pending 或 failed 时编造分析结论。
- 不让批量分析同步跑在 Agent 请求里。
- 不削弱用户隔离。

## 产品行为

### 单股分析流程

1. 用户打开 `/agent`。
2. 用户输入 `分析贵州茅台`，或点击 `单股分析` 快捷入口。
3. Agent 识别股票代码、市场、分析深度、分析师模块、情绪/风险选项、模型偏好。
4. Agent 调用股票分析工具的 single 模式。
5. 工具通过现有分析服务和队列创建真实分析任务。
6. Agent 返回：
   - 标准化股票代码；
   - `task_id`；
   - 当前状态；
   - 任务状态链接；
   - 报告链接，如果报告已存在；
   - 如果任务仍在执行，必须明确提示 pending。
7. 用户后续问 `总结刚才的分析` 时，Agent 必须读取真实任务/报告状态，再总结。

### 批量分析流程

1. 用户输入 `批量分析 AAPL, MSFT, NVDA`，或点击 `批量分析` 快捷入口。
2. Agent 校验股票列表，保持现有最多 10 只的批量限制。
3. Agent 调用股票分析工具的 batch 模式。
4. 工具创建 batch，并通过现有队列提交每只股票的分析任务。
5. Agent 返回：
   - `batch_id`；
   - 股票列表；
   - 每只股票对应的 `task_id`；
   - batch 当前状态；
   - 跳转到任务中心的链接。
6. 用户可以继续问：
   - `这个批量任务完成了吗？`
   - `谁的风险最大？`
   - `把已完成的报告做个对比总结。`
7. Agent 回答这些问题前，必须读取真实 task/report 状态。

### 旧页面迁移策略

第一阶段：

- 保留 `/analysis/single`。
- 保留 `/analysis/batch`。
- 在旧页面增加“用研究 Agent 分析”的辅助入口。
- 不改变旧页面已有提交行为。

第二阶段：

- Dashboard、股票详情、自选股、选股结果页的主入口逐步转向 `/agent?prompt=...`。
- 旧页面可以变成结构化 提示词 builder。

第三阶段：

- 等 Agent 路径稳定后，再决定是否隐藏旧菜单。
- 即使隐藏，也保留旧 URL 兼容历史链接。

## 后端设计

### 工具命名

建议引入一个统一工具：

- `stock_analysis`

同时保留兼容工具：

- `single_stock_analysis`
- `batch_stock_analysis`

兼容工具不再写重复逻辑，而是内部调用同一套 `stock_analysis` helper。

### 提交工具输入

建议输入结构：

```json
{
  "mode": "single",
  "symbols": ["600519"],
  "market_type": "A股",
  "analysis_date": "2026-06-11",
  "research_depth": "标准",
  "selected_analysts": ["market", "fundamentals", "news", "social"],
  "include_sentiment": true,
  "include_risk": true,
  "language": "zh-CN",
  "quick_analysis_model": "qwen-turbo",
  "deep_analysis_model": "qwen-max",
  "wait_for_completion": false
}
```

批量分析使用：

```json
{
  "mode": "batch",
  "symbols": ["AAPL", "MSFT", "NVDA"],
  "market_type": "美股",
  "research_depth": "标准",
  "wait_for_completion": false
}
```

### 单股提交输出

```json
{
  "tool": "stock_analysis",
  "mode": "single",
  "status": "submitted",
  "symbol": "600519",
  "task_id": "task-id",
  "links": {
    "task": "/tasks?task_id=task-id",
    "report": null
  },
  "message": "单股分析任务已提交，结果生成后可继续让 Agent 总结。"
}
```

### 批量提交输出

```json
{
  "tool": "stock_analysis",
  "mode": "batch",
  "status": "submitted",
  "batch_id": "batch-id",
  "total_tasks": 3,
  "tasks": [
    {"symbol": "AAPL", "task_id": "task-a"},
    {"symbol": "MSFT", "task_id": "task-b"},
    {"symbol": "NVDA", "task_id": "task-c"}
  ],
  "links": {
    "batch": "/tasks?batch_id=batch-id"
  },
  "message": "批量分析任务已提交。"
}
```

### 状态读取工具

增加：

- `stock_analysis_status`

支持输入：

```json
{
  "task_id": "task-id"
}
```

或：

```json
{
  "batch_id": "batch-id"
}
```

要求：

- 只能读取当前用户自己的任务。
- 不能接受 LLM payload 里的 `user_id`。
- pending 返回 pending。
- failed 返回 failed 和错误原因。
- completed 返回报告链接或 `analysis_id`，如果已生成。

### 报告读取工具

增加：

- `stock_analysis_report`

支持输入：

```json
{
  "task_id": "task-id"
}
```

或：

```json
{
  "analysis_id": "analysis-id"
}
```

要求：

- 只能读取当前用户自己的报告。
- pending 任务不能被总结成已完成。
- 报告不存在时返回明确状态。
- 成功时返回摘要、评级、风险等级、关键观点和报告链接。

### 异步执行要求

- 默认 `wait_for_completion=false`。
- 工具提交任务后立即返回任务 ID。
- 可以支持短时间 bounded wait，但必须有硬超时。
- 批量分析不能在 Agent attempt 内同步等待完成。
- Agent 最终回答必须明确说明任务是否只是“已提交”，还是“已完成并已读取报告”。

### 事件和 Artifact

股票分析工具事件必须包含：

- `attempt_id`
- `tool_name`
- `task_id` 或 `batch_id`
- `status`
- `result` 预览

建议写入 Research Agent artifact：

- `stock_analysis_task`
- `stock_analysis_batch`
- `stock_analysis_report_summary`

Evidence Ledger 只保存引用和摘要，不复制完整报告。

## 前端设计

### `/agent` 快捷入口

在研究 Agent 页面增加轻量快捷入口：

- `单股分析`
- `批量分析`

第一版行为：

- 点击后填充 composer。
- 不自动发送。
- 用户可以检查 提示词 再发送。

单股 提示词 示例：

```text
请对 600519 做单股分析，市场为 A股，研究深度为 标准。
```

批量 提示词 示例：

```text
请批量分析 600519, 000001, 300750，市场为 A股，研究深度为 标准。
```

### 旧页面入口

第一版不替换旧页面主按钮。

可以增加辅助链接：

- `用研究 Agent 分析`
- 跳转到 `/agent?prompt=<encoded prompt>`
- 打开后只填充输入框，不自动提交。

### 结果链接

Agent 消息和工具卡片应提供：

- 单股：`/tasks?task_id=<id>`
- 批量：`/tasks?batch_id=<id>`
- 报告：`/reports/view/<analysis_id>`

## 校验和错误处理

- 空股票列表必须拒绝。
- 批量数量沿用最多 10 只限制。
- 股票代码标准化优先复用旧页面/旧服务已有逻辑。
- 模型 API Key 缺失时，返回现有配置指引，不要吞掉错误。
- pending 任务必须明确 pending。
- failed 任务必须显示失败原因。
- completed 但报告缺失时，必须说明报告尚未生成或读取失败。
- 后续总结必须先读取真实 task/report。

## 权限和隔离

- 所有工具使用 `context.principal.user_id`。
- 工具不能接受或信任 payload 里的 `user_id`。
- 任务读取必须带当前用户过滤。
- 报告读取必须带当前用户过滤。
- 普通 Agent 模式下，admin 也不默认跨用户读取私有分析。
- artifact 链接不能暴露其他用户的 task/report。

## 分阶段计划

### 阶段 1：后端工具接入

- 把 `single_stock_analysis` / `batch_stock_analysis` 从占位改成真实调用旧分析服务。
- 增加统一 `stock_analysis` helper。
- 返回真实 `task_id` / `batch_id`。
- 增加提交相关回归测试。

### 阶段 2：状态和报告读取

- 增加 `stock_analysis_status`。
- 增加 `stock_analysis_report`。
- 支持用户后续问“刚才任务完成了吗”和“总结刚才报告”。
- 增加 pending/failed/completed/user isolation 测试。

### 阶段 3：Agent 提示词 和 UX

- 更新工具描述和 Agent 系统提示词约束。
- 让 Agent 知道什么时候提交、什么时候查状态、什么时候读报告。
- `/agent` 增加单股/批量快捷入口。

### 阶段 4：导航收敛

- 给旧分析相关页面增加 Agent 入口。
- 稳定后再决定是否隐藏旧菜单。

## 验收标准

- 在 Agent 里请求单股分析会创建真实 `analysis_tasks` 任务。
- 在 Agent 里请求批量分析会创建真实 batch 和多个 task。
- Agent 工具事件出现在本次 attempt 的右侧执行步骤里。
- Agent 可以读取并总结已完成报告。
- Agent 不会把 pending 任务总结成已完成。
- 用户不能通过 Agent 读取其他用户的 task/report。
- 旧 `/analysis/single`、`/analysis/batch`、`/tasks`、`/reports` 继续可用。
- 后端和前端目标测试通过。

## 待 Review 的关键选择

1. 第一版菜单是否仍保留旧 `单股分析` / `批量分析` 入口？
2. Agent 默认是否只提交任务并返回链接，还是单股分析可以短时间等待完成？
3. `stock_analysis_status` / `stock_analysis_report` 是独立工具，还是合并成 `stock_analysis` 的 action？
