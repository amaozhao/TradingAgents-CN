# 研究 Agent 批量分析 Workflow 迁移规格说明

日期：2026-06-12

## 结论先行

本规格的目标是：**在研究 Agent 内实现批量股票分析 workflow，完整迁移旧批量分析的批次创建、子任务 fan-out、非阻塞提交、并发限制、状态聚合、SSE/事件语义、结果链接和部分成功判定，并让每只股票复用已经迁移的单股 `StockDagParityWorkflow`。**

这不是以下方案：

- 不是继续让 `batch_stock_analysis` 返回 accepted stub。
- 不是把批量工具简单循环调用 `stock_analysis`，然后丢掉批次状态。
- 不是在 Agent workflow 中重新实现单股 TradingAgents DAG 节点。
- 不是把旧 Redis queue/worker 当作 Agent 批量工具的主执行器。
- 不是只迁移前端 `/analysis/batch` 提交表单。

正确方向是：**新增 batch workflow runner，把旧批量分析的外层编排语义完整迁入 Agent workflow；每个 symbol 的内部分析仍调用单股 workflow，批量层只负责验证、调度、聚合、持久化、事件和兼容响应。**

## Review 修正结论

第一次规格稿有三处需要严格修正：

1. **“旧批量 DAG”不是代码里的真实 LangGraph DAG。** 旧批量分析没有 `StateGraph`，真实实现是 API/Redis queue/worker/SSE 组成的 fan-out 编排。本规格后续所说“目标批量 DAG”，是为了迁移到 workflow 后显式建模的外层编排图，不代表旧代码已经有一个 LangGraph 批量 DAG。
2. **旧批量默认是 submission-first，不是同步跑完整批次。** `/api/analysis/batch` 只创建任务并入队，不能在 FastAPI 请求内执行分析。Agent 批量 workflow 也必须支持非阻塞提交；如果支持等待完成，必须是显式 `wait_for_completion=true` 的附加模式。
3. **当前任务中心没有真正消费 `batch_id`。** `BatchAnalysisPage` 跳转到 `/tasks?batch_id=...`，但 `TaskCenterPage` 当前只读取 `task_id`，任务列表转换也没有输出 `batch_id`。迁移必须补齐 backend list filter 和 frontend batch filter，否则页面链路不完整。

## 背景与现状

当前代码中有三类批量入口：

1. 主产品 API：`backend/app/routers/analysis/list.py::submit_batch_analysis`。
   - 接收 `BatchAnalysisRequest`。
   - 校验股票列表非空、最多 10 只。
   - 为每只股票调用 `SimpleAnalysisService.create_analysis_task()`。
   - 用同一个 `batch_id` 调 `QueueService.enqueue_task()` 入队。
   - 返回 `batch_id`、`task_ids`、`mapping`、`status=submitted`。

2. 旧服务层：`backend/app/services/analysis/service/submit.py::AnalysisSubmitMixin.submit_batch_analysis`。
   - 创建 `AnalysisBatch` 文档。
   - 创建多条 `AnalysisTask` 文档。
   - 写入 `analysis_batches`、`analysis_tasks`，并 dual-write hot documents。
   - 把每个任务加入队列。
   - 返回 `batch_id`、`total_tasks`、`status=pending`。

3. 研究 Agent 工具：`backend/app/services/research/agent/tools/analysis.py::_batch_stock_analysis`。
   - 当前只是 `{"tool": "batch_stock_analysis", "accepted": True, "payload": payload}`。
   - 没有创建批次、没有运行子任务、没有聚合状态、没有报告链接、没有事件。

因此，批量分析不是“已经迁到 workflow 但不完整”；它在 Agent 工具侧尚未迁移。

## 旧批量编排逻辑

旧批量分析不是 TradingAgents 单股内部 DAG，也不是 LangGraph DAG。它的真实外层编排语义可以表达为：

```text
START
  -> validate_batch_request
  -> resolve_batch_parameters
  -> create_batch_identity
  -> create_child_tasks
  -> enqueue_child_tasks
  -> return_submission_response
  -> END
```

然后由 worker/SSE 异步完成后半段：

```text
worker_dequeue_child_task
  -> run_single_analysis
  -> ack_child_task
  -> update_child_status
  -> aggregate_batch_status_by_polling
  -> expose_batch_progress
```

每个 child task 的实际股票分析再进入单股分析链路：

```text
child_task(symbol)
  -> StockDagParityWorkflow / old TradingAgentsGraph equivalent
```

新 batch workflow 必须迁移外层编排的全部功能，并把 child task 的执行引擎换成当前 Agent 单股 workflow。

## 旧功能清单

| 功能 | 旧实现位置 | 旧行为 | 目标 workflow 要求 |
| --- | --- | --- | --- |
| 请求模型 | `schemas/analysis.py::BatchAnalysisRequest` | `title` 必填；`description` 可选；`symbols` 和 `stock_codes` 兼容；最多 10 个 | Agent tool schema 必须支持同等字段和兼容别名 |
| 参数模型 | `AnalysisParameters` | `market_type`、`analysis_date`、`research_depth`、`selected_analysts`、`include_sentiment`、`include_risk`、`language`、quick/deep model | 每个 child workflow 使用同一参数对象，不得丢字段 |
| 非空校验 | `analysis/list.py` | 空列表返回 400 | Agent tool 返回 `config_required`，API adapter 返回 400 |
| 批量上限 | `analysis/list.py`、Pydantic | 最多 10 只 | workflow 层再次强校验，防止绕过前端和 API |
| 兼容字段 | `get_symbols()` | `symbols` 优先，否则 `stock_codes` | Agent tool 保持 `symbols` / `stock_codes` 兼容 |
| 批次 ID | `uuid.uuid4()` | 所有子任务共享一个 `batch_id` | 新 workflow 生成并返回同一 `batch_id` |
| 子任务 ID | `create_analysis_task()` 或 `uuid.uuid4()` | 每只股票独立 `task_id` | 新 workflow 每只股票生成独立 `task_id`，并映射 symbol |
| 任务映射 | `mapping` | `symbol`、`stock_code`、`task_id` | 响应和事件必须保留 |
| 持久化 | `analysis_batches`、`analysis_tasks` | 批次和子任务可被任务页/历史页读取 | 新 workflow 必须写同等查询字段，或提供兼容 adapter |
| 队列状态 | Redis task hash / batch set | `queued`、`processing`、`completed`、`failed` | Agent batch workflow 不必用 Redis 主执行，但必须产出等价状态 |
| 并发限制 | `QueueService` | user/global concurrent limit；visibility timeout | 新 workflow 必须 bounded concurrency，不得无限并发 |
| worker ack | `AnalysisWorker` | 子任务完成后 ack success/fail | 新 workflow 必须为每个 child 记录 success/fail，不静默吞错 |
| 批次状态聚合 | `sse.py::batch_progress_generator` | 全成功 `completed`；全失败 `failed`；混合 `partial` | 新 workflow 必须保留这三个终态及计数 |
| 进度 | `finished / total * 100` | 只按完成/失败子任务计整体进度 | 新 workflow 批次 progress 按同一公式，child progress 作为明细 |
| SSE / 事件 | `/sse/batches/{batch_id}` | connected/progress/finished/error | Agent session events 必须提供 batch stage events；旧 SSE adapter 可读取同一状态 |
| 所有权 | `batch_data.user == user["id"]` | 只能访问自己的批次 | Agent status/report 工具和 API adapter 必须 owner-scoped |
| 前端跳转 | `frontend/features/analysis/batch-analysis-page.tsx` | 提交后跳 `/tasks?batch_id=...` | 新 API response 仍含 `batch_id`，任务页可按 batch 查询 |

## 逐点映射方式

### API route 映射

| 旧位置 | 旧职责 | 新位置 | 迁移方式 |
| --- | --- | --- | --- |
| `analysis/list.py::submit_batch_analysis` | 产品批量页面提交入口 | `BatchStockWorkflow.submit()` 或 batch service adapter | 保留 route；内部改为调用 workflow submit 服务，返回旧 `ApiResponse` shape |
| `analysis/queue.py::analyze_batch` | 兼容队列入口 `/analyze/batch` | 同一 batch submit adapter | 继续返回 `{batch_id, submitted}`，但底层状态源改为 workflow batch state |
| `analysis/queue.py::get_batch` | 按 `batch_id` 读取 Redis batch | `read_batch_status(batch_id, user_id)` | 先查新 batch store，再兼容读 Redis；必须 owner-scoped |
| `sse.py::stream_batch_progress` | 批次 SSE | `batch_progress_reader` | 读取新 batch state 的 child statuses，保留 connected/progress/finished/error event |
| `analysis/result.py::get_task_result` | 读取 child task report | 不改报告契约 | child report 仍按 `task_id` 读取；batch summary 只能附加，不能替代 child report |

### Redis queue 映射

| 旧 Redis 结构 | 旧字段 / 含义 | 新 workflow state | 迁移要求 |
| --- | --- | --- | --- |
| `qa:batch:{batch_id}` | `id`、`user`、`status`、`submitted`、`created_at` | `BatchWorkflowState.batch_id/user_id/status/total_tasks/created_at` | 新状态必须可转成旧 hash shape，供兼容 SSE/API 读取 |
| `qa:batch_tasks:{batch_id}` | child task id set | `BatchWorkflowState.task_ids` | 顺序响应使用 `mapping`，兼容 set 读取可无序 |
| `qa:task:{task_id}` | `id`、`user`、`symbol`、`status`、`params`、`batch_id` | `BatchChildState` | 必须保留 `batch_id`、`symbol`、`user_id`、`parameters` |
| `qa:ready` | FIFO ready list | workflow job queue / background runner | Agent workflow 不必继续使用 Redis ready list，但必须保留非阻塞提交语义 |
| `qa:processing` / user processing set | 并发控制 | semaphore + persisted running count | user/global concurrency 语义必须有等价实现 |
| visibility timeout keys | worker 崩溃重入队 | workflow lease / heartbeat | 若本阶段不做 lease，必须显式标为不支持，不能假装有旧等价能力 |

### DB/document 映射

| 旧文档 | 旧字段 | 新写入要求 | 说明 |
| --- | --- | --- | --- |
| `analysis_batches` | `batch_id` | 必填 | structured table 只索引最小字段，完整字段放 JSON payload/document store |
| `analysis_batches` | `user_id` | 必填 | 所有查询必须按 user 过滤 |
| `analysis_batches` | `status` | 必填 | `partial` 写 document；写 Pydantic `BatchStatus` 时映射为 `partial_success` |
| `analysis_batches` | `total_tasks` | 必填 | 兼容 mapper 已索引该字段 |
| `analysis_batches` | `completed_tasks`、`failed_tasks`、`cancelled_tasks`、`progress` | 必填 | 当前 table mapper 不索引，但 document payload 必须保留 |
| `analysis_batches` | `parameters`、`results_summary`、`mapping` | 必填 | 前端和 Agent summary 依赖 |
| `analysis_tasks` | `task_id`、`batch_id`、`user_id`、`symbol`/`stock_code` | 必填 | 当前 `list_user_tasks` 转换未输出 `batch_id`，迁移必须补 |
| `analysis_tasks` | `status`、`progress`、`message`、`last_error` | 必填 | 任务中心和 SSE 依赖 |
| `analysis_reports` | `task_id`、`analysis_id`、`user_id`、`stock_symbol` | 单股 workflow 原样写 | batch layer 不得改变 report schema |

### Agent tool 映射

| 旧/当前工具 | 当前状态 | 新工具行为 |
| --- | --- | --- |
| `batch_stock_analysis` | accepted stub，只回显 payload | 调 `BatchStockWorkflow.submit()`；默认返回 `batch_id`、`task_ids`、`mapping`、`status=processing/pending` |
| `stock_analysis` | 单股 workflow | batch child 调用同一底层 child runner，不通过 tool registry 递归调用 |
| `stock_analysis_status` | 查单股 task | 新增 `batch_stock_analysis_status` 或扩展 `batch_stock_analysis` 支持 `action=status` |
| `stock_analysis_report` | 查单股 report | batch result 返回 child report links；不需要把 batch report 伪装成 single report |
| `DirectToolMixin.run_direct_tool` | 只从 `tool_result.task_id/job_id` 收集一个 task id | 必须识别 `tool_result.task_ids` 和 `batch_id`，否则 Agent 消息 metadata 会丢批次关联 |

### 前端映射

| 旧/当前前端 | 当前状态 | 迁移要求 |
| --- | --- | --- |
| `BatchAnalysisPage` | 已提交完整 payload，跳 `/tasks?batch_id=...` | 保持 payload shape；若 API 改为 workflow submit，测试仍应通过 |
| `TaskCenterPage` | 读取 `task_id`，没有读取 `batch_id` | 必须读取 `batch_id` search param，并传给 history/list API |
| `TaskRow` | 没有 `batch_id` 字段 | 增加 `batch_id?: string`，搜索和表格可按批次过滤 |
| `analysisApi.getHistory/getTaskList` | 无 `batch_id` 参数 | 增加可选 `batch_id`，backend route 过滤 `analysis_tasks.batch_id` |
| 任务统计 | 按当前 rows 统计 | batch filter 下统计 child tasks；可另加 batch summary band |

## 目标架构

新增批量 workflow 模块，复用现有单股 workflow：

```text
backend/app/services/research/agent/batch/
  context.py      # 构建批次上下文和参数
  graph.py        # 批量外层 DAG plan
  runner.py       # BatchStockWorkflow 主执行器
  state.py        # 批次状态、子任务状态、聚合规则
  events.py       # batch_analysis.stage / child events
  reports.py      # 批次摘要和子报告链接
```

命名说明：`batch` 是单词目录，符合仓库新增目录命名规则；代码符号使用 `BatchStockWorkflow`、`BatchStockWorkflowResult` 表达业务语义。

### 主入口

`backend/app/services/research/agent/tools/analysis.py::_batch_stock_analysis` 必须改为：

```text
BatchStockWorkflow(tool_name="batch_stock_analysis").submit(context, payload)
```

当 payload 显式传入 `wait_for_completion=true` 时，入口可转入 `BatchStockWorkflow(...).run_until_complete(context, payload)`；默认不得等待完整批次完成。

`StockAnalysisWorkflow.run_single()` 保持单股职责，不新增 `mode=batch` 分支作为主要设计。批量是外层 workflow，不应该污染单股 workflow 类。

## 目标批量 DAG

### 节点清单

| 节点 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `START` | 初始化 workflow attempt | `ToolExecutionContext`、payload | attempt metadata |
| `validate_batch_request` | 解析 `symbols` / `stock_codes`，去重，校验 1-10 只 | raw payload | normalized symbols、invalid symbols、market hints |
| `resolve_batch_parameters` | 复用单股参数归一化和模型选择逻辑 | payload、normalized symbols | `AnalysisParameters`、skipped stage plan |
| `check_model_keys` | 校验 quick/deep model API key | parameters | ok 或 `config_required` |
| `create_batch_record` | 生成 `batch_id`，创建批次初始状态 | title、description、user、parameters | `BatchWorkflowState` |
| `create_child_tasks` | 为每只股票生成 `task_id` 和 child state | symbols、batch_id | child task list、mapping |
| `submit_child_workflows` | 非阻塞提交 child workflow job | child tasks、parameters | child job handles |
| `run_child_workflows` | 显式等待模式下有界并发执行每个 `StockDagParityWorkflow` | child tasks、parameters、`wait_for_completion=true` | child result / child error |
| `persist_child_results` | 保存每个单股报告和任务状态 | child result | `analysis_reports`、`analysis_tasks` |
| `aggregate_batch_status` | 汇总 completed/failed/cancelled/progress | child states | batch status、counts、summary |
| `persist_batch_result` | 写 batch 文档和 batch summary artifact | aggregate | `analysis_batches`、batch report |
| `emit_finished` | 发 final batch event | final state | finished event |
| `END` | 返回兼容响应 | final state | tool result |

### 边

```text
START -> validate_batch_request
validate_batch_request -> resolve_batch_parameters
resolve_batch_parameters -> check_model_keys
check_model_keys -> create_batch_record
create_batch_record -> create_child_tasks
create_child_tasks -> submit_child_workflows
submit_child_workflows -> END(submitted)
submit_child_workflows -> run_child_workflows [only when wait_for_completion=true]
run_child_workflows -> persist_child_results
persist_child_results -> aggregate_batch_status
aggregate_batch_status -> persist_batch_result
persist_batch_result -> emit_finished
emit_finished -> END
```

### 条件边

| source | condition | target |
| --- | --- | --- |
| `validate_batch_request` | no symbols | `END(config_required)` |
| `validate_batch_request` | symbols > 10 | `END(config_required)` |
| `validate_batch_request` | invalid symbols and `strict_symbols=true` | `END(config_required)` |
| `validate_batch_request` | invalid symbols and strict false | `resolve_batch_parameters` with `skipped_symbols` |
| `check_model_keys` | missing API keys | `END(config_required)` |
| `submit_child_workflows` | `wait_for_completion=false` or omitted | `END(submitted)` |
| `submit_child_workflows` | `wait_for_completion=true` | `run_child_workflows` |
| `run_child_workflows` | any child completed or failed | `persist_child_results` |
| `aggregate_batch_status` | all completed | `completed` |
| `aggregate_batch_status` | all failed | `failed` |
| `aggregate_batch_status` | mixed completed/failed | `partial` |
| `aggregate_batch_status` | cancelled children exist and unfinished remain | `cancelled` or `partial` per child outcomes |

## 数据契约

### Tool payload

`batch_stock_analysis` schema 必须支持：

```json
{
  "title": "银行股批量复盘",
  "description": "对低估值银行做批量分析",
  "symbols": ["600036", "000001"],
  "stock_codes": ["600036", "000001"],
  "market_type": "A股",
  "analysis_date": "2026-06-12",
  "research_depth": "标准",
  "selected_analysts": ["market", "fundamentals", "news"],
  "include_sentiment": true,
  "include_risk": true,
  "language": "zh-CN",
  "quick_analysis_model": "qwen-turbo",
  "deep_analysis_model": "qwen-max",
  "strict_symbols": true,
  "max_concurrency": 3,
  "wait_for_completion": false
}
```

`stock_codes` 是兼容字段；若两者同时存在，`symbols` 优先。

### Tool result

成功或部分成功时必须返回：

```json
{
  "tool": "batch_stock_analysis",
  "mode": "batch",
  "accepted": true,
  "status": "completed",
  "batch_id": "uuid",
  "total_tasks": 2,
  "completed_tasks": 2,
  "failed_tasks": 0,
  "cancelled_tasks": 0,
  "progress": 100,
  "task_ids": ["task-a", "task-b"],
  "mapping": [
    {"symbol": "600036", "stock_code": "600036", "task_id": "task-a"},
    {"symbol": "000001", "stock_code": "000001", "task_id": "task-b"}
  ],
  "children": [
    {
      "symbol": "600036",
      "task_id": "task-a",
      "status": "completed",
      "analysis_id": "analysis-a",
      "report_url": "/reports/view/task-a"
    }
  ],
  "summary": "批量分析完成：2/2 成功。",
  "links": {
    "batch": "/tasks?batch_id=uuid"
  },
  "message": "Agent 批量分析 workflow 已完成。"
}
```

默认非阻塞提交时必须返回：

```json
{
  "tool": "batch_stock_analysis",
  "mode": "batch",
  "accepted": true,
  "status": "submitted",
  "batch_id": "uuid",
  "total_tasks": 2,
  "task_ids": ["task-a", "task-b"],
  "mapping": [
    {"symbol": "600036", "stock_code": "600036", "task_id": "task-a"},
    {"symbol": "000001", "stock_code": "000001", "task_id": "task-b"}
  ],
  "links": {
    "batch": "/tasks?batch_id=uuid"
  },
  "message": "批量分析任务已提交。"
}
```

失败校验时必须返回：

```json
{
  "tool": "batch_stock_analysis",
  "mode": "batch",
  "accepted": false,
  "status": "config_required",
  "missing": ["symbols"],
  "reason": "Missing required argument: symbols or stock_codes.",
  "instruction": "请提供 1-10 个股票代码。"
}
```

### 状态枚举

批次状态必须兼容旧状态，并在 Agent 内统一为：

- `pending`
- `processing`
- `completed`
- `partial`
- `failed`
- `cancelled`
- `config_required`

API adapter 写入旧 `AnalysisBatch` 时可把 `partial` 映射为 `partial_success`，但工具结果和 SSE 兼容层必须保留 `partial`，因为旧 `batch_progress_generator` 使用该终态。

## 持久化契约

新 batch workflow 必须至少写入或可查询以下信息：

### `analysis_batches`

- `batch_id`
- `user_id`
- `title`
- `description`
- `status`
- `total_tasks`
- `completed_tasks`
- `failed_tasks`
- `cancelled_tasks`
- `progress`
- `created_at`
- `started_at`
- `completed_at`
- `parameters`
- `results_summary`
- `mapping`

### `analysis_tasks`

每个 child task 必须写：

- `task_id`
- `batch_id`
- `user_id`
- `symbol`
- `stock_code`
- `stock_symbol`
- `status`
- `progress`
- `parameters`
- `created_at`
- `started_at`
- `completed_at`
- `last_error`

### `analysis_reports`

每个 child task 的报告仍由单股 `persist_stock_workflow_report()` 写入，批量层不得改写单股报告字段。

批量层可以新增 batch summary artifact，但不得把多个单股报告揉成一个替代报告后丢失 child report 链接。

## 事件契约

Agent session event 必须新增或复用以下事件类型：

- `batch_analysis.stage`
- `batch_analysis.child_started`
- `batch_analysis.child_completed`
- `batch_analysis.child_failed`
- `batch_analysis.progress`
- `batch_analysis.completed`
- `batch_analysis.partial`
- `batch_analysis.failed`

`batch_analysis.progress` payload 至少包含：

- `attempt_id`
- `batch_id`
- `status`
- `progress`
- `total_tasks`
- `completed`
- `failed`
- `processing`
- `children`

子任务内部的 `stock_analysis.stage` / `stock_analysis.node` event 必须继续发出，并带上 `batch_id`，否则任务页无法把 child event 归到批次。

## 并发与执行规则

1. 默认 `max_concurrency` 从系统设置读取，建议使用 `max_concurrent_tasks`，没有配置时默认 3。
2. payload 允许传 `max_concurrency`，但不能超过系统上限。
3. 默认 `wait_for_completion=false`，只提交 batch 和 child jobs；不得阻塞 Agent/API 请求跑完整批次。
4. `wait_for_completion=true` 时，才允许在当前调用中有界并发等待 child workflow 完成。
5. 单个 child workflow 失败不能中断整个批次，除非失败发生在批次级校验或模型配置阶段。
6. 批次级状态由 child 终态聚合：
   - 全部 completed -> `completed`
   - 全部 failed -> `failed`
   - completed 和 failed 混合 -> `partial`
   - 用户取消后无成功结果 -> `cancelled`
7. 每个 child 都要独立记录错误，不允许只返回一个总错误。
8. 长任务必须通过事件和持久化状态暴露进度，不能只等最终返回。

## API 与前端兼容要求

### `/api/analysis/batch`

迁移后可以有两种实现方式：

1. API adapter 调用 `BatchStockWorkflow` 的提交/运行服务。
2. API 暂时保留旧 queue 路径，但 Agent `batch_stock_analysis` 使用 workflow。

如果选择第 2 种，必须在计划中明确这是阶段性兼容，不得声称页面批量已迁移到 workflow。

最终目标是 `/api/analysis/batch` 与 `batch_stock_analysis` 共用同一批量 workflow 服务层，避免两套批量逻辑继续漂移。

### `/tasks?batch_id=...`

当前页面还没有真正处理 `batch_id`。迁移后必须能显示：

- 批次总状态
- 子任务列表
- 每个子任务 status/progress
- 每个子任务报告链接
- 部分成功时的失败原因

必改点：

- `TaskCenterPage` 读取 `searchParams.get("batch_id")`。
- `analysisApi.getHistory()` 和 `analysisApi.getTaskList()` 增加 `batch_id` 查询参数。
- 后端 `get_user_analysis_history`、`list_user_tasks` 增加 owner-scoped `batch_id` 过滤。
- `_analysis_task_document_to_history_item()` 输出 `batch_id`。
- 批量页面测试要断言跳转后任务中心能按 batch 展示 child tasks。

### `/sse/batches/{batch_id}`

旧 SSE 端点可以继续存在，但数据源应能读取新 batch workflow 状态。其终态仍是：

- `completed`
- `failed`
- `partial`

## 与单股 workflow 的关系

批量层只编排，不复制单股 DAG。

每个 child 必须调用与 `stock_analysis` 同一条单股路径：

```text
build_agent_stock_workflow_context(...)
-> StockDagParityWorkflow(...).run()
-> build_stock_workflow_report(...)
-> persist_stock_workflow_report(...)
-> _record_stock_workflow_usage(...)
```

批量层不得：

- 调用旧 `TradingAgentsGraph.propagate()`。
- 调用 `run_native_stock_workflow()`。
- 调用旧 queue/worker 作为 Agent 主路径。
- 跳过 `StockDagParityWorkflow` 直接构造简化报告。

## 测试要求

### 后端测试

新增测试建议：

- `backend/tests/unit/app/services/research/agent/batch/test_graph.py`
  - 验证 batch DAG 节点、普通边、条件边。
- `backend/tests/unit/app/services/research/agent/batch/test_state.py`
  - 验证状态聚合：completed、failed、partial、cancelled。
- `backend/tests/unit/app/services/research/agent/batch/test_context.py`
  - 验证空 symbols、超过 10 只、`stock_codes` 兼容、去重、格式错误。
- `backend/tests/unit/app/services/research/agent/batch/test_runner.py`
  - 用 fake child workflow 验证有界并发、单 child 失败不阻断全批次。
- `backend/tests/unit/app/services/research/agent/batch/test_events.py`
  - 验证 batch events 和 child events 都带 `batch_id`。
- `backend/tests/unit/app/services/research/agent/tools/test_analysis.py`
  - 验证 `batch_stock_analysis` 不再返回 stub，且返回 `batch_id`、`task_ids`、`mapping`。
- `backend/tests/integration/app/services/research/agent/batch/test_repository.py`
  - 验证 batch/task/report 查询字段兼容。
- `backend/tests/unit/app/services/research/agent/test_direct.py`
  - 验证 direct tool metadata 同时记录 `batch_id` 和所有 `task_ids`。
- `backend/tests/integration/app/routers/analysis/test_batch.py`
  - 验证 `/api/analysis/user/history?batch_id=...` 只返回当前用户该批次 child tasks。
- `frontend/tests/integration/features/tasks/task-center-page.test.tsx`
  - 验证 `/tasks?batch_id=batch-1` 会把 `batch_id` 传给 API 并展示 child tasks。

### 需要保留的旧测试语义

- `backend/tests/integration/app/routers/analysis/test_queue_submission.py` 中“批量提交只入队，不在 FastAPI 进程内执行”的旧 API 语义，在 API adapter 完成迁移前必须继续通过。
- 如果最终让 `/api/analysis/batch` 也改走 workflow，必须先新增替代测试，明确 FastAPI 进程不阻塞长分析，或明确该接口只是提交 workflow job 而非同步执行全批次。

## 实施任务建议

1. 写 batch graph/state 失败测试。
2. 实现 `batch/graph.py` 和 `batch/state.py`。
3. 写 tool schema 和 stub 回归失败测试，锁定 `batch_stock_analysis` 当前缺口。
4. 实现 `BatchStockWorkflow.submit()`，先通过验证、batch/child state、提交响应测试。
5. 实现可选 `wait_for_completion=true` 的 `BatchStockWorkflow.run_until_complete()`，用 fake child workflow 验证聚合和部分成功。
6. 接入真实 `StockDagParityWorkflow` child runner，保留 fake 注入点。
7. 接入持久化和报告链接。
8. 接入 Agent event append 和 direct tool result 文案，修复 `task_ids` / `batch_id` metadata。
9. 补 `/tasks?batch_id=...` 后端过滤和前端展示链路。
10. 决定 `/api/analysis/batch` 是否本阶段共用 workflow；若共用，补 API adapter 测试和前端任务页验证。
11. 跑 targeted backend/frontend tests，再跑 backend ruff/pyright/pytest。

## Review

### 覆盖性结论

规格已经覆盖旧批量编排语义的主要行为面：

- 请求字段和兼容字段。
- 批量大小限制。
- 批次 ID 和子任务 ID。
- 子任务映射。
- 批次/任务/报告持久化。
- 队列时代的并发和终态聚合语义。
- SSE 和 Agent event 兼容。
- 前端 `/tasks?batch_id=...` 当前缺口和迁移要求。
- Agent `batch_stock_analysis` 当前 stub 缺口。
- 与单股 `StockDagParityWorkflow` 的边界。

### 主要风险

1. **同步执行风险。** 当前单股 Agent workflow 会在工具调用内等待完成；批量如果直接并发跑 10 个 child，可能让 Agent 请求长期占用。实施时默认必须是 submission-first，等待完成只能作为显式模式。
2. **API 双轨风险。** `/api/analysis/batch` 仍可能保留旧 queue，Agent 工具走新 workflow。短期可接受，但必须在文档和测试中标明，不要误报“页面批量已迁移”。
3. **状态字段漂移。** 旧 Redis/SSE 使用 `partial`，Pydantic `BatchStatus` 使用 `partial_success`。实现时必须有显式映射测试。
4. **所有权风险。** batch/status/report 查询必须按 `user_id` 过滤；不能只用 `batch_id`。
5. **事件归属风险。** child 单股事件若不带 `batch_id`，任务页和 Agent 时间线会难以聚合批次进度。
6. **任务中心断链风险。** 当前任务中心不读 `batch_id`，如果不补过滤链路，批量页面提交成功后仍无法看到该批次。

### 阻断项

实现前必须先锁定这三个测试，否则容易做成“循环调用单股工具”的不完整迁移：

- `batch_stock_analysis` 不再返回 accepted stub。
- 单个 child 失败时 batch 返回 `partial` 并保留失败明细。
- child event 和 child report 都能通过 `batch_id` 关联回批次。
