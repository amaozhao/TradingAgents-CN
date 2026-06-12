# 研究 Agent 批量股票分析 Workflow DAG 对齐实施计划

> **给执行代理的要求：** 实施本计划时必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，按任务逐项执行。每个任务使用 checkbox 语法跟踪进度，不允许跳过测试和 review 步骤。

**目标：** 在研究 Agent 内实现批量股票分析 workflow，完整保留旧批量分析的提交、fan-out、子任务映射、状态聚合、事件、SSE、持久化、报告链接、部分成功语义和 `/tasks?batch_id=...` 链路；每个子任务必须复用已经迁移的单股 `StockDagParityWorkflow`。

**架构：** 新增 `backend/app/services/research/agent/batch/` 批量 workflow 包，负责批次验证、状态建模、提交、可选等待完成、持久化、事件和兼容响应。单股分析仍由现有 `StockDagParityWorkflow` 执行，批量层只负责编排和聚合，不重新实现单股 TradingAgents DAG。默认路径必须是“先提交后执行”（submission-first）；只有显式 `wait_for_completion=true` 时才允许同步等待完整批次。

**技术栈：** Python 3.13、FastAPI、Pydantic、PostgreSQL document store helpers、现有 research Agent tool registry、现有 `StockDagParityWorkflow`、pytest 回归测试、Next.js/React/TypeScript、Vitest 与 Testing Library。

---

## 来源规格

实施依据：`docs/superpowers/specs/2026-06-12-agent-batch-stock-workflow-dag-parity.md`

必须保持的规格约束：

- 旧批量分析不是 LangGraph DAG，而是 API + Redis queue + worker + SSE 的 fan-out 编排。
- 新文档中的“批量 DAG”是目标 workflow 的显式建模，不是旧代码里已有的图。
- `/api/analysis/batch` 旧行为是提交任务并返回，不能在 FastAPI 请求内跑完整批次。
- `batch_stock_analysis` 当前 accepted stub 必须移除。
- 每只股票的内部分析必须走与 `stock_analysis` 相同的 `StockDagParityWorkflow` 路径。
- 批量状态必须保留 `batch_id`、`task_ids`、`mapping`、所有者隔离、`partial` 终态、SSE 兼容和任务中心过滤。
- `/tasks?batch_id=...` 当前没有端到端工作，本次迁移必须补齐后端过滤和前端消费。

## 文件范围

### 新增后端批量 workflow 包

- 新增 `backend/app/services/research/agent/batch/__init__.py`
  - 导出批量 workflow 的公共 API。
- 新增 `backend/app/services/research/agent/batch/state.py`
  - 定义批次状态、子任务状态、状态聚合、旧状态映射和工具结果构造。
- 新增 `backend/app/services/research/agent/batch/graph.py`
  - 定义目标批量 workflow 的节点、普通边和条件边。
- 新增 `backend/app/services/research/agent/batch/context.py`
  - 解析 payload，归一化 `symbols` / `stock_codes`，构造 `AnalysisParameters`，解析并发和等待模式。
- 新增 `backend/app/services/research/agent/batch/events.py`
  - 发送 `batch_analysis.*` 事件，并让 child 单股事件携带 `batch_id`。
- 新增 `backend/app/services/research/agent/batch/repository.py`
  - 写入和读取 `analysis_batches`、`analysis_tasks` 文档，并确保按所有者隔离查询。
- 新增 `backend/app/services/research/agent/batch/runner.py`
  - 实现 `BatchStockWorkflow.submit()` 和 `BatchStockWorkflow.run_until_complete()`。

### 修改后端现有文件

- 修改 `backend/app/services/research/agent/tools/analysis.py`
  - 用 `BatchStockWorkflow` 替换 `_batch_stock_analysis` stub。
  - 扩展 `batch_stock_analysis` schema。
- 修改 `backend/app/services/research/agent/stock.py`
  - 允许单股 workflow 的事件和状态携带可选 `batch_id`，但不改变单股工具的返回契约。
- 修改 `backend/app/services/research/agent/direct.py`
  - 识别并持久化 `tool_result.task_ids` 与 `tool_result.batch_id`。
- 修改 `backend/app/routers/analysis/setup.py`
  - 如果 typed request/response model 阻挡 `batch_id` 参数，补齐可选字段。
- 修改 `backend/app/routers/analysis/queue.py`
  - 批次读取优先走新的按所有者隔离 batch status reader，保留 Redis 回退读取。
- 修改 `backend/app/routers/analysis/list.py`
  - 保持 `/api/analysis/batch` 响应 shape；内部切换到 workflow submit adapter。
  - 如果该文件拥有任务列表 query，补齐 `batch_id` 过滤。
- 修改 `backend/app/services/analysis/simple/status.py`
  - history/list rows 保留并输出 `batch_id`。
  - 支持按所有者隔离的 `batch_id` 过滤。
- 修改 `backend/app/routers/sse.py`
  - `/sse/batches/{batch_id}` 能读取新 batch workflow 状态，并保留旧 SSE 事件 shape。

### 修改前端文件

- 修改 `frontend/libs/api/analysis.ts`
  - `getHistory` 和 `getTaskList` 增加可选 `batch_id` 参数。
- 修改 `frontend/features/tasks/task-center-page.tsx`
  - 读取 `batch_id` search param。
  - `TaskRow` 增加 `batch_id?: string`。
  - 请求任务列表/history 时传入 `batch_id`。
  - 批量过滤下展示该批次 child tasks、状态、进度和报告链接。

### 新增测试

- 新增 `backend/tests/unit/app/services/research/agent/batch/test_graph.py`
- 新增 `backend/tests/unit/app/services/research/agent/batch/test_state.py`
- 新增 `backend/tests/unit/app/services/research/agent/batch/test_context.py`
- 新增 `backend/tests/unit/app/services/research/agent/batch/test_runner.py`
- 新增 `backend/tests/unit/app/services/research/agent/batch/test_events.py`
- 新增 `backend/tests/unit/app/services/research/agent/tools/test_analysis.py`
- 新增 `backend/tests/integration/app/services/research/agent/batch/test_repository.py`
- 新增 `backend/tests/unit/app/services/research/agent/test_direct.py`
- 新增 `backend/tests/integration/app/routers/analysis/test_history.py`
- 新增 `backend/tests/integration/app/routers/analysis/test_queue_submission.py`
- 新增或更新 `frontend/tests/integration/features/tasks/task-center-page.test.tsx`

## 非目标

- 不继续让 `batch_stock_analysis` 返回 accepted stub。
- 不把批量工具实现成简单循环调用 `stock_analysis` 后丢弃批次状态。
- 不在批量层重新实现单股 TradingAgents DAG。
- 不让旧 Redis queue/worker 成为 Agent 批量工具的主执行器。
- 不只迁移前端批量提交页面；必须补齐任务中心、状态、事件和持久化链路。
- 不改变单股报告 schema；批量摘要只能附加，不能替代 child report。

## 任务 0：迁移现有前后端测试目录和文件命名

**目的：** 先修正当前 `backend/tests` 和 `frontend/tests` 的既有布局，避免本批量 workflow 继续新增不符合 AGENTS.md 的 `regression/.../test.py`、`app/.../test.py`、`components/...` 或 `foundation/...` 测试文件。

**文件：**

- 移动 `backend/tests/app/**/test.py`
- 移动 `backend/tests/cli/**/test.py`
- 移动 `backend/tests/file/**/test.py`
- 移动 `backend/tests/regression/**/test.py`
- 移动 `backend/tests/test/**/test.py`
- 移动 `backend/tests/tools/**/test.py`
- 移动 `backend/tests/trader/**/test.py`
- 保留 `backend/tests/__init__.py`
- 保留 `backend/tests/conftest.py`
- 保留 `backend/tests/integration/__init__.py`
- 移动 `frontend/tests/api/**`
- 移动 `frontend/tests/components/**`
- 移动 `frontend/tests/foundation/**`
- 移动 `frontend/tests/routes/**`
- 保留 `frontend/tests/e2e/**`
- 保留 `frontend/tests/setup.ts`

**步骤：**

- [x] 建立当前不合规测试清单：

```bash
cd backend && find tests \
  -path 'tests/.pytest_cache' -prune -o \
  -path 'tests/__pycache__' -prune -o \
  -type f -name '*.py' -print | sort
```

当前清单包含大量旧布局测试文件，计划编写时扫描到 197 个 `test.py` 文件；执行时必须以实际命令输出为准，并迁移旧测试顶层目录下的所有测试 Python 文件。

- [x] 建立不合规顶层目录清单：

```bash
cd backend && find tests -maxdepth 1 -mindepth 1 -type d \
  ! -name unit \
  ! -name integration \
  ! -name e2e \
  ! -name __pycache__ \
  ! -name .pytest_cache \
  -print | sort
```

这些目录下的测试必须迁移到 `tests/unit`、`tests/integration` 或 `tests/e2e`，迁移完成后删除空目录。

- [x] 建立前端不合规顶层目录清单：

```bash
cd frontend && find tests -maxdepth 1 -mindepth 1 -type d \
  ! -name unit \
  ! -name integration \
  ! -name e2e \
  -print | sort
```

当前不合规目录包括 `tests/api`、`tests/components`、`tests/foundation`、`tests/routes`；执行时以实际命令输出为准。

- [x] 按以下规则移动文件，必须使用 `git mv`：
  - 纯函数、schema、service helper、状态聚合、tool/direct 结果处理测试 -> `backend/tests/unit/<源码相对路径>/test_<模块名>.py`。
  - FastAPI route、service + repository、document store、队列状态、跨模块查询测试 -> `backend/tests/integration/<源码相对路径>/test_<模块名>.py`。
  - 真实 HTTP 用户流程或完整 worker/队列端到端流程 -> `backend/tests/e2e/<源码相对路径>/test_<模块名>.py`。
  - 如果旧路径是 `backend/tests/app/core/config/test.py` 且对应源码是 `backend/app/core/config.py`，目标是 `backend/tests/unit/app/core/test_config.py`。
  - 如果旧路径对应源码包 `backend/app/services/foo/__init__.py`，目标是 `backend/tests/unit/app/services/foo/test_init.py`。
  - 如果旧 regression 测试实际验证 route 或数据库边界，例如 `backend/tests/regression/analysis/history/test.py`，目标应放入 `backend/tests/integration/app/routers/analysis/test_history.py` 或更精确的 service/repository 镜像路径。
- [x] 按以下规则移动前端文件，必须使用 `git mv`：
  - API client、store、配置、纯函数测试 -> `frontend/tests/unit/<源码相对路径>/<源码文件名>.test.ts(x)`。
  - 组件、页面、hook + provider、router 协作测试 -> `frontend/tests/integration/<源码相对路径>/<源码文件名>.test.tsx`。
  - 浏览器级用户流程测试 -> `frontend/tests/e2e/<场景名>.spec.ts`，现有 `frontend/tests/e2e` 可保留。
  - 如果旧路径是 `frontend/tests/components/task-center-page.test.tsx` 且源码是 `frontend/features/tasks/task-center-page.tsx`，目标是 `frontend/tests/integration/features/tasks/task-center-page.test.tsx`。
  - 如果旧路径是 `frontend/tests/foundation/api-client.test.ts` 且源码在 `frontend/libs/api/client.ts` 或等价 API client 文件，目标是 `frontend/tests/unit/libs/api/client.test.ts`。
- [x] 更新所有 pytest 命令、测试引用和相对 import：
  - `pyproject.toml`
  - `pytest.ini` 或等价 pytest 配置文件
  - `backend/tests/conftest.py`
  - 文档里的测试命令
  - CI 脚本中的测试路径
- [x] 更新所有前端测试命令、Vitest setup 引用和相对 import：
  - `frontend/vitest.config.*`
  - `frontend/package.json`
  - `frontend/tests/setup.ts`
  - 文档里的 `pnpm vitest run ...` 命令
  - CI 脚本中的前端测试路径
- [x] 删除迁移后为空的旧测试目录：
  - `backend/tests/app`
  - `backend/tests/cli`
  - `backend/tests/file`
  - `backend/tests/regression`
  - `backend/tests/test`
  - `backend/tests/tools`
  - `backend/tests/trader`
  - 只删除空目录，不删除还有未迁移文件的目录。
- [x] 删除迁移后为空的前端旧测试目录：
  - `frontend/tests/api`
  - `frontend/tests/components`
  - `frontend/tests/foundation`
  - `frontend/tests/routes`
  - 只删除空目录，不删除还有未迁移文件的目录。
- [x] 验证没有遗留 `test.py` 文件名：

```bash
cd backend && find tests \
  -path 'tests/.pytest_cache' -prune -o \
  -path 'tests/__pycache__' -prune -o \
  -type f -name 'test.py' -print
```

期望输出为空。

- [x] 验证没有遗留不合规位置的 Python 测试文件：

```bash
cd backend && find tests \
  -path 'tests/.pytest_cache' -prune -o \
  -path 'tests/__pycache__' -prune -o \
  -type f -name '*.py' \
  ! -path 'tests/unit/*' \
  ! -path 'tests/integration/*' \
  ! -path 'tests/e2e/*' \
  ! -path 'tests/conftest.py' \
  ! -path 'tests/__init__.py' \
  -print
```

期望输出为空；这意味着 `tests/app`、`tests/cli`、`tests/file`、`tests/regression`、`tests/test`、`tests/tools`、`tests/trader` 已迁移或删除。

- [x] 验证没有遗留不合规前端测试顶层目录：

```bash
cd frontend && find tests -maxdepth 1 -mindepth 1 -type d \
  ! -name unit \
  ! -name integration \
  ! -name e2e \
  -print
```

期望输出为空；`tests/setup.ts` 可作为测试环境配置文件保留在 `frontend/tests` 根目录。

- [x] 验证没有遗留不合规测试顶层目录：

```bash
cd backend && find tests -maxdepth 1 -mindepth 1 -type d \
  ! -name unit \
  ! -name integration \
  ! -name e2e \
  ! -name __pycache__ \
  ! -name .pytest_cache \
  -print
```

期望输出为空。

**验收：**

- 后端测试只新增或保留在 `backend/tests/unit`、`backend/tests/integration`、`backend/tests/e2e` 和必要的测试配置文件中。
- 后端测试文件名使用 `test_<模块名>.py`，不再使用目录内统一 `test.py`。
- `backend/scripts/**/test.py` 不视为 pytest 测试迁移对象：这些文件包含手工诊断、API/DB/网络探测、命令行脚本和带 `__main__` 的一次性验证逻辑，不满足单元/集成测试的隔离要求；本次统一改名为 `script.py`。
- `backend/scripts/test/hk/sync/test.py` 的额外 `test` 层级没有业务含义，已收敛为 `backend/scripts/hk/sync/script.py`。
- `backend/scripts` 下不再存在 `test.py`，脚本内旧的 `scripts/.../test.py` 使用提示也同步改为 `scripts/.../script.py`。
- 前端测试只新增或保留在 `frontend/tests/unit`、`frontend/tests/integration`、`frontend/tests/e2e` 和必要的测试配置文件中。
- 删除空旧目录，不留下只为旧布局服务的空壳。
- 迁移必须保持测试行为不变；如果迁移导致 import 或 fixture 失败，要修正真实路径和 fixture，而不是跳过测试。

## 任务 1：建立批量 workflow 图与状态契约

**文件：**

- `backend/app/services/research/agent/batch/__init__.py`
- `backend/app/services/research/agent/batch/graph.py`
- `backend/app/services/research/agent/batch/state.py`
- `backend/tests/unit/app/services/research/agent/batch/test_graph.py`
- `backend/tests/unit/app/services/research/agent/batch/test_state.py`

**步骤：**

- [x] 先写 `backend/tests/unit/app/services/research/agent/batch/test_graph.py`，验证目标 workflow 节点完整：
  - `START`
  - `validate_batch_request`
  - `resolve_batch_parameters`
  - `check_model_keys`
  - `create_batch_record`
  - `create_child_tasks`
  - `submit_child_workflows`
  - `run_child_workflows`
  - `persist_child_results`
  - `aggregate_batch_status`
  - `persist_batch_result`
  - `emit_finished`
  - `END`
- [x] 测试普通边必须包含：
  - `START -> validate_batch_request`
  - `validate_batch_request -> resolve_batch_parameters`
  - `resolve_batch_parameters -> check_model_keys`
  - `check_model_keys -> create_batch_record`
  - `create_batch_record -> create_child_tasks`
  - `create_child_tasks -> submit_child_workflows`
  - `run_child_workflows -> persist_child_results`
  - `persist_child_results -> aggregate_batch_status`
  - `aggregate_batch_status -> persist_batch_result`
  - `persist_batch_result -> emit_finished`
  - `emit_finished -> END`
- [x] 测试条件边必须包含：
  - 空 symbols -> `END(config_required)`
  - symbols 超过 10 -> `END(config_required)`
  - invalid symbols 且 `strict_symbols=true` -> `END(config_required)`
  - missing model keys -> `END(config_required)`
  - `wait_for_completion=false` -> `END(submitted)`
  - `wait_for_completion=true` -> `run_child_workflows`
  - all completed -> `completed`
  - all failed -> `failed`
  - mixed completed/failed -> `partial`
- [x] 实现 `graph.py`，使用明确的数据结构表达目标 workflow，而不是虚构旧代码已经有 LangGraph。

建议结构：

```python
from dataclasses import dataclass
from typing import Literal

BatchWorkflowNode = Literal[
    "START",
    "validate_batch_request",
    "resolve_batch_parameters",
    "check_model_keys",
    "create_batch_record",
    "create_child_tasks",
    "submit_child_workflows",
    "run_child_workflows",
    "persist_child_results",
    "aggregate_batch_status",
    "persist_batch_result",
    "emit_finished",
    "END",
]

@dataclass(frozen=True)
class ConditionalEdge:
    source: BatchWorkflowNode
    condition: str
    target: BatchWorkflowNode | str

@dataclass(frozen=True)
class BatchStockWorkflowPlan:
    nodes: tuple[BatchWorkflowNode, ...]
    edges: tuple[tuple[BatchWorkflowNode, BatchWorkflowNode], ...]
    conditional_edges: tuple[ConditionalEdge, ...]
```

- [x] 先写 `backend/tests/unit/app/services/research/agent/batch/test_state.py`，验证状态聚合：
  - 全部 child completed -> batch `completed`，progress 100。
  - 全部 child failed -> batch `failed`，progress 100。
  - completed + failed 混合 -> batch `partial`，progress 100。
  - 有 processing 未完成 -> batch `processing`，progress 只统计 completed/failed/cancelled。
  - cancelled 且无成功结果 -> batch `cancelled`。
  - `partial` 写旧 Pydantic `BatchStatus` 时映射为 `partial_success`，但 SSE/tool 保持 `partial`。
- [x] 实现 `state.py`。

建议结构：

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

BatchStatus = Literal[
    "pending",
    "processing",
    "completed",
    "partial",
    "failed",
    "cancelled",
    "config_required",
]

ChildStatus = Literal[
    "pending",
    "queued",
    "processing",
    "completed",
    "failed",
    "cancelled",
]

@dataclass
class BatchChildState:
    symbol: str
    stock_code: str
    task_id: str
    status: ChildStatus = "pending"
    progress: int = 0
    analysis_id: str | None = None
    report_url: str | None = None
    error: str | None = None

@dataclass
class BatchWorkflowState:
    batch_id: str
    user_id: str
    title: str
    description: str | None
    status: BatchStatus
    parameters: dict[str, Any]
    children: list[BatchChildState] = field(default_factory=list)
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
```

- [x] 实现 `aggregate_batch_status(state)`，返回 status/counts/progress。
- [x] 实现 `normalize_batch_status_for_document(status)`，只在写旧 batch model 时把 `partial` 映射为 `partial_success`。
- [x] 实现 `build_batch_tool_result(state)`，输出：
  - `tool`
  - `mode=batch`
  - `accepted`
  - `status`
  - `batch_id`
  - `total_tasks`
  - `completed_tasks`
  - `failed_tasks`
  - `cancelled_tasks`
  - `progress`
  - `task_ids`
  - `mapping`
  - `children`
  - `summary`
  - `links.batch`
  - `message`

**验收：**

- 图测试和状态测试先失败、实现后通过。
- 状态聚合不依赖 Redis。
- `partial` 语义在 tool/SSE 层不被误改成 `partial_success`。

## 任务 2：实现 payload 验证和批次上下文

**文件：**

- `backend/app/services/research/agent/batch/context.py`
- `backend/tests/unit/app/services/research/agent/batch/test_context.py`

**步骤：**

- [x] 写验证测试，覆盖：
  - 缺少 `symbols` 和 `stock_codes` -> `config_required`。
  - 空数组 -> `config_required`。
  - 超过 10 只 -> `config_required`。
  - 同时有 `symbols` 和 `stock_codes` 时优先 `symbols`。
  - `stock_codes` 兼容字段能正常生成 child states。
  - 重复 symbol 去重，并保留响应顺序。
  - invalid symbol 且 `strict_symbols=true` -> `config_required`。
  - invalid symbol 且 `strict_symbols=false` -> 记录 `skipped_symbols`，剩余 symbols 继续。
  - `max_concurrency` 不能超过系统上限。
  - 默认 `wait_for_completion=false`。
- [x] 实现 `BatchConfigError`，提供 `missing`、`reason`、`instruction`。
- [x] 复用/对齐单股参数归一化逻辑：
  - `_analysis_parameters`：保留同名惰性包装，避免导入阶段触发单股执行模块的配置/数据库初始化。
  - `_normalize_stock_symbol_for_analysis`：在 batch context 内实现与单股一致的纯函数规则。
  - `_stock_symbol_format_error`：在 batch context 内实现与单股一致的纯函数规则。
- [x] 构造 `BatchRequestContext`，包含：
  - `user_id`
  - `title`
  - `description`
  - `symbols`
  - `skipped_symbols`
  - `parameters`
  - `strict_symbols`
  - `max_concurrency`
  - `wait_for_completion`
  - `raw_payload`

建议结构：

```python
@dataclass(frozen=True)
class BatchRequestContext:
    user_id: str
    title: str
    description: str | None
    symbols: tuple[str, ...]
    skipped_symbols: tuple[str, ...]
    parameters: AnalysisParameters
    strict_symbols: bool
    max_concurrency: int
    wait_for_completion: bool
    raw_payload: Mapping[str, object]
```

**验收：**

- Agent tool schema 与旧 `BatchAnalysisRequest` 字段兼容。
- workflow 层自己强校验 1-10 只股票，不能只依赖前端或 API。
- 每个 child workflow 使用同一个完整 `AnalysisParameters`，不能丢字段。

## 任务 3：实现 batch repository 和按所有者隔离的状态读取

**文件：**

- `backend/app/services/research/agent/batch/repository.py`
- `backend/tests/integration/app/services/research/agent/batch/test_repository.py`

**步骤：**

- [x] 写 persistence fake DB 测试，验证提交后写入：
  - `analysis_batches.batch_id`
  - `analysis_batches.user_id`
  - `analysis_batches.title`
  - `analysis_batches.description`
  - `analysis_batches.status`
  - `analysis_batches.total_tasks`
  - `analysis_batches.completed_tasks`
  - `analysis_batches.failed_tasks`
  - `analysis_batches.cancelled_tasks`
  - `analysis_batches.progress`
  - `analysis_batches.parameters`
  - `analysis_batches.results_summary`
  - `analysis_batches.mapping`
  - 每条 `analysis_tasks.task_id`
  - 每条 `analysis_tasks.batch_id`
  - 每条 `analysis_tasks.user_id`
  - 每条 `analysis_tasks.symbol` / `stock_code` / `stock_symbol`
  - 每条 `analysis_tasks.status`
  - 每条 `analysis_tasks.progress`
  - 每条 `analysis_tasks.parameters`
- [x] 测试 `get_batch(batch_id, user_id)` 不能读取其他用户的批次。
- [x] 实现 `BatchRepository.save_submitted_batch(state)`。
- [x] 实现 `BatchRepository.update_child(batch_id, user_id, child)`。
- [x] 实现 `BatchRepository.update_batch_aggregate(state)`。
- [x] 实现 `BatchRepository.get_batch(batch_id, user_id)`。
- [x] 复用项目已有 document store 和 dual-write helpers：
  - `get_postgres_db`
  - `dual_write_hot_document`
  - `dual_write_hot_documents`

**验收：**

- 批次和子任务都能按 `batch_id + user_id` 查询。
- 新 workflow 的状态能转换成旧 `/sse/batches/{batch_id}` 需要的哈希结构。
- 不改变单股 `analysis_reports` 写入契约。

## 任务 4：实现批量事件和 child event 归属

**文件：**

- `backend/app/services/research/agent/batch/events.py`
- `backend/app/services/research/agent/stock.py`
- `backend/tests/unit/app/services/research/agent/batch/test_events.py`

**步骤：**

- [x] 写事件测试，验证以下事件 payload 都包含 `attempt_id` 和 `batch_id`：
  - `batch_analysis.stage`
  - `batch_analysis.child_started`
  - `batch_analysis.child_completed`
  - `batch_analysis.child_failed`
  - `batch_analysis.progress`
  - `batch_analysis.completed`
  - `batch_analysis.partial`
  - `batch_analysis.failed`
- [x] 测试 `batch_analysis.progress` 至少包含：
  - `status`
  - `progress`
  - `total_tasks`
  - `completed`
  - `failed`
  - `processing`
  - `children`
- [x] 修改 `run_agent_stock_workflow`，增加可选 `batch_id` 参数。
- [x] 修改 `_emit_stock_workflow_stage`，在存在 `batch_id` 时把它放进事件 payload。
- [x] 修改 `_stock_workflow_node_emitter`，在存在 `batch_id` 时把它放进 node event payload。
- [x] 确保单股直接调用时不输出多余字段或改变返回 shape。

验证记录：

- `backend/tests/unit/app/services/research/agent/batch/test_events.py` 覆盖 batch 事件 shape。
- `stock.py` 当前存在导入阶段触发 ConfigManager/PostgreSQL token store 初始化的既有副作用，`timeout 10 python -c "import app.services.research.agent.stock"` 会超时；stock helper 的运行时验证需要在后续 Pyright/导入副作用清理任务中继续处理。

**验收：**

- child 单股事件可以被归到批次。
- 任务页和 Agent session timeline 不会丢失批次上下文。

## 任务 5：实现 BatchStockWorkflow.submit 与工具集成

**文件：**

- `backend/app/services/research/agent/batch/runner.py`
- `backend/app/services/research/agent/tools/analysis.py`
- `backend/tests/unit/app/services/research/agent/tools/test_analysis.py`
- `backend/tests/unit/app/services/research/agent/batch/test_runner.py`

**步骤：**

- [x] 写工具测试，锁定当前缺口：
  - `_batch_stock_analysis` 不能只返回 `{"accepted": True, "payload": ...}`。
  - 必须返回 `tool=batch_stock_analysis`。
  - 必须返回 `mode=batch`。
  - 必须返回 `batch_id`。
  - 必须返回全部 `task_ids`。
  - 必须返回 `mapping`。
  - 默认 `status=submitted` 或 `pending/processing`，但必须表示非阻塞提交。
  - 必须返回 `links.batch=/tasks?batch_id=...`。
- [x] 扩展 `batch_stock_analysis` schema，支持：
  - `title`
  - `description`
  - `symbols`
  - `stock_codes`
  - `market_type`
  - `analysis_date`
  - `research_depth`
  - `selected_analysts`
  - `include_sentiment`
  - `include_risk`
  - `language`
  - `quick_analysis_model`
  - `deep_analysis_model`
  - `strict_symbols`
  - `max_concurrency`
  - `wait_for_completion`
- [x] 实现 `BatchStockWorkflow.submit(context, payload)`：
  - [x] 调 `build_batch_request_context`。
  - [x] 校验 model keys。
  - [x] 生成 `batch_id`。
  - [x] 为每个 symbol 生成独立 `task_id`。
  - [x] 构造 `BatchWorkflowState`。
  - [x] 写入 batch 和 child task 初始状态。
  - [x] 提交 child workflow job 或记录为待执行状态。
  - [x] 默认通过可注入后台 scheduler 调度 child workflow，测试可传 `background_scheduler=None` 禁用后台执行。
  - [x] 发 `batch_analysis.stage` 和 `batch_analysis.progress`。
  - [x] 返回非阻塞提交结果。
- [x] 修改 `_batch_stock_analysis`：
  - [x] 默认调用 `BatchStockWorkflow.submit`，不再返回 stub payload。
  - [x] `wait_for_completion=True` 时调用 `run_until_complete`。

说明：批量提交阶段通过 `build_batch_request_context -> stock._analysis_parameters` 复用单股模型参数解析；默认非阻塞提交不会同步等待 child，但会在提交响应返回后调度后台 child workflow。`wait_for_completion=True` 或后台 child 执行时会进入单股 workflow 的 `_missing_model_keys` 校验并返回 `config_required`，因此不在批量层重复实现一套独立模型 key 校验。

```python
async def _batch_stock_analysis(payload: Mapping[str, object], ctx: ToolExecutionContext) -> dict[str, object]:
    workflow = BatchStockWorkflow(tool_name="batch_stock_analysis")
    if payload.get("wait_for_completion") is True:
        return await workflow.run_until_complete(ctx, payload)
    return await workflow.submit(ctx, payload)
```

**验收：**

- Agent 工具不再是 stub。
- 默认不会等待完整批次。
- 提交结果包含旧 API 依赖的 `batch_id`、`task_ids`、`mapping`。

## 任务 6：修复 DirectToolMixin 批量元数据

**文件：**

- `backend/app/services/research/agent/direct.py`
- `backend/tests/unit/app/services/research/agent/test_direct.py`

**步骤：**

- [x] 写 direct tool 测试：
  - 当 tool result 包含 `task_ids` 时，元数据记录所有 task id。
  - 当 tool result 包含 `batch_id` 时，元数据记录 batch id。
  - 保留单股 `task_id` / `job_id` 现有行为。
- [x] 修改 direct tool 结果提取逻辑：
  - 读取单个 `task_id`。
  - 读取 `job_id`。
  - 读取列表型 `task_ids`。
  - 读取 `batch_id`。
  - 去重后写入事件/消息元数据。

**验收：**

- Agent 对话中的批量工具调用能被任务中心和后续状态查询关联。
- 不破坏单股工具的元数据。

## 任务 7：实现可选等待完成模式和真实 child workflow adapter

**文件：**

- `backend/app/services/research/agent/batch/runner.py`
- `backend/app/services/research/agent/stock.py`
- `backend/tests/unit/app/services/research/agent/batch/test_runner.py`

**步骤：**

- [x] 在 runner 测试中使用 fake child workflow，验证：
  - `max_concurrency` 被遵守。
  - 一个 child 失败不会中断整个批次。
  - mixed completed/failed -> batch `partial`。
  - 每个 child 的 error 被记录。
  - progress 使用 `(completed + failed + cancelled) / total * 100`。
- [x] 实现 `run_batch_child_workflow(ctx, batch_state, child, parameters)`。
- [x] child runner 必须调用同一条单股 workflow 路径：
  - `build_agent_stock_workflow_context(...)`
  - `StockDagParityWorkflow(...).run()`
  - `build_stock_workflow_report(...)`
  - `persist_stock_workflow_report(...)`
  - `_record_stock_workflow_usage(...)`
- [x] 不允许调用：
  - `run_native_stock_workflow()`
  - `TradingAgentsGraph.propagate()`
  - 旧 queue/worker 作为 Agent 主路径
  - 简化 mock 报告替代真实 child report
- [x] 实现 `BatchStockWorkflow.run_until_complete()`：
  - 先完成 submit 初始化。
  - 用 bounded semaphore 执行 child。
  - 每个 child 完成或失败都更新 repository。
  - 每个 child 完成或失败都发 batch progress event。
  - 最终聚合 batch 状态。
  - 返回 completed/partial/failed/cancelled 工具结果。

**验收：**

- 等待完成模式是显式附加能力。
- 默认 API/Agent 调用仍是“先提交后执行”（submission-first）。
- child report 仍按单股 report schema 读取。

## 任务 8：补齐后端任务列表和历史记录的 `batch_id` 过滤

**文件：**

- `backend/app/services/analysis/simple/status.py`
- `backend/app/routers/analysis/list.py`
- `backend/app/routers/analysis/queue.py`
- `backend/app/routers/analysis/setup.py`
- `backend/tests/integration/app/routers/analysis/test_history.py`
- `backend/tests/integration/app/routers/analysis/test_queue_submission.py`

**步骤：**

- [x] 写 backend filter 测试：
  - `GET /api/analysis/user/history?batch_id=batch-1` 只返回当前用户 batch-1 的 child tasks。
  - 其他用户同名 `batch_id` 不会泄漏。
  - 返回 item 包含 `batch_id`。
  - 不传 `batch_id` 时保持旧列表行为。
- [x] 修改 `_analysis_task_document_to_history_item()` 输出 `batch_id`。
- [x] 修改 `get_user_analysis_history` / `list_user_tasks` 的查询参数和 service 层过滤。
- [x] 修改结构化 PostgreSQL 表路径：
  - `build_user_analysis_tasks_select(..., batch_id=...)` 在 SQL select 阶段按 `payload["batch_id"]` 过滤。
  - `list_user_analysis_tasks(..., batch_id=...)` 把过滤条件传入 DB 查询，不能在分页后再做 Python 过滤。
  - `_task_to_dict()` 输出 `batch_id`，保证 history/list rows 与 document store 路径一致。
- [x] 修改 `/api/analysis/queue/batch/{batch_id}` 或等价读取路径：
  - 先查新 batch repository。
  - 查不到时再读旧 Redis。
  - 所有路径都必须按 user 过滤。

**验收：**

- `/tasks?batch_id=...` 的后端数据源可用。
- owner scope 不被绕过。

## 任务 9：实现 SSE 批次进度兼容读取

**文件：**

- `backend/app/routers/sse.py`
- `backend/tests/unit/app/services/research/agent/batch/test_events.py`

**步骤：**

- [x] 为 `/sse/batches/{batch_id}` 增加新 batch status reader。
- [x] 修复 `/sse/batches/{batch_id}` route 入口：
  - 入口先按当前用户读取 `BatchRepository.get_batch(batch_id, user_id)`。
  - 新 workflow 批次存在时直接返回 `StreamingResponse`。
  - repository 查不到时才回退旧队列状态，避免新批次在 generator 前被旧队列检查误判为 404。
- [x] 保留旧事件序列：
  - connected
  - progress
  - finished
  - error
- [x] 终态仍输出：
  - `completed`
  - `failed`
  - `partial`
- [x] progress 仍按完成/失败/取消 child 数除以 total 计算。
- [x] 如果新 repository 查不到批次，再回退读取 Redis 旧状态。

**验收：**

- 旧 SSE 客户端无需改协议即可消费新 workflow 状态。
- `partial` 不被 SSE 层改名。

## 任务 10：迁移 `/api/analysis/batch` 到 workflow submit adapter

**文件：**

- `backend/app/routers/analysis/list.py`
- `backend/app/routers/analysis/queue.py`
- `backend/tests/integration/app/routers/analysis/test_queue_submission.py`

**步骤：**

- [x] 保留旧 `/api/analysis/batch` 响应 shape：
  - `success`
  - `data.batch_id`
  - `data.task_ids`
  - `data.mapping`
  - `data.status`
  - `message`
- [x] 实现 route adapter：

```python
async def _submit_batch_via_workflow(
    request: BatchAnalysisRequest,
    user: dict[str, object],
) -> dict[str, object]:
    payload = request.model_dump(exclude_none=True)
    payload["wait_for_completion"] = False
    context = build_api_tool_execution_context(user)
    return await BatchStockWorkflow(tool_name="batch_stock_analysis").submit(context, payload)
```

- [x] 如果本阶段不能安全切换产品 API，必须明确保留旧 queue route 作为阶段性兼容，同时 Agent 工具先迁到 workflow。
- [x] 如果切换产品 API，必须保证：
  - FastAPI 请求只提交 workflow job，不同步执行长分析。
  - `backend/tests/integration/app/routers/analysis/test_queue_submission.py` 中“批量提交只入队/提交，不在请求内跑完整分析”的语义仍有替代测试覆盖。

**验收：**

- 不出现两套长期漂移的批量逻辑。
- 文档和测试明确当前 API 是否已共用 workflow。

## 任务 11：实现前端任务中心 batch filter

**文件：**

- `frontend/libs/api/analysis.ts`
- `frontend/features/tasks/task-center-page.tsx`
- `frontend/tests/integration/features/tasks/task-center-page.test.tsx`

**步骤：**

- [x] 写前端测试：
  - 渲染 `/tasks?batch_id=batch-1`。
  - `analysisApi.getHistory` 或 `getTaskList` 被调用时包含 `{ batch_id: "batch-1" }`。
  - 页面展示 batch-1 的 child tasks。
  - child row 展示 status/progress。
  - child row 保留报告链接。
- [x] 修改 `analysisApi.getHistory` 和 `analysisApi.getTaskList`：
  - 增加 `batch_id?: string` 参数。
  - 构造 query string 时包含 `batch_id`。
- [x] 修改 `TaskCenterPage`：
  - 读取 `searchParams.get("batch_id")`。
  - 把 `batch_id` 传入 API。
  - `TaskRow` 类型增加 `batch_id?: string`。
  - batch filter 下统计当前 child rows。
  - 不影响原有 `task_id` filter。
  - 切换 tab 时通过统一 URL builder 保留 `batch_id` 和 `task_id`，避免 `/tasks?batch_id=...` 在状态页签切换后断链。

**验收：**

- `BatchAnalysisPage` 跳转到 `/tasks?batch_id=...` 后能看到该批次 child tasks。
- 任务中心当前断链被修复。

## 任务 12：真实消除 Ruff 与 Pyright 告警

**文件：**

- `backend/app/**`
- `backend/trader/**`
- `backend/support/**`
- `backend/web/**`
- `backend/tests/unit/**`
- `backend/tests/integration/**`
- `backend/tests/e2e/**`
- `backend/pyproject.toml`
- `backend/pyrightconfig.json` 或等价 Pyright 配置文件

**步骤：**

- [x] 删除所有 `# ruff: noqa...` 和普通 `# noqa...` 跳过注释：

```bash
cd /home/amaozhao/workspace/TradingAgents-CN
rg -n "#\\s*(ruff:\\s*)?noqa" backend frontend tools docs -g '*.py'
```

期望输出为空；不允许通过保留 Ruff 跳过注释隐藏问题。

- [x] 运行 Ruff 并真实修复所有诊断：

```bash
cd backend && ruff check .
```

当前实测结果：`All checks passed!`

- [x] 运行 Pyright 并保存当前诊断清单：

```bash
cd backend && pyright
```

- [x] 对每条 Ruff/Pyright 诊断做真实代码修复，不允许使用以下方式“消除”告警：
  - 新增 `# ruff: noqa` 或 `# noqa`。
  - 新增或扩大 `exclude`。
  - 降低 `typeCheckingMode`。
  - 把 `report*` 规则改成 `none`。
  - 增加 `# type: ignore`、`# pyright: ignore` 或无解释的 `cast`。
  - 把明确类型退化成 `Any`、`dict[str, Any]`、`object` 后不做窄化。
- [x] 优先使用以下修复方式：
  - 将 `support.loader.execute(...)` 拆分文件中运行期必需的 `TYPE_CHECKING` 导入改成显式模块级导入。
  - 用真实 helper 替代原先被 `F821` 掩盖的缺失函数。
  - 删除未使用变量，而不是添加忽略。
  - 将因子文件中的局部变量 `l` 改名为 `low`。
  - 给函数、fixture、repository 返回值补真实类型。
  - 用 Pydantic model、dataclass、TypedDict、Protocol、Literal 或 Enum 表达结构化数据。
  - 对外部输入用类型守卫或显式校验后再使用。
  - 把可选值在使用前窄化，而不是使用非空断言或弱 cast。
  - 修正错误 import、循环 import、async 返回类型、mock/fake 对象签名。
- [x] 检查没有新增 Pyright 过滤或忽略：

```bash
cd backend && rg -n "# type: ignore|# pyright: ignore|typeCheckingMode\\s*=\\s*['\\\"]?basic|report[A-Za-z]+\\s*=\\s*['\\\"]?none|exclude\\s*=" pyproject.toml pyrightconfig.json app tests
```

如果命中的是迁移前已存在配置，必须说明没有扩大范围；如果是本次新增，必须移除并改真实代码。

- [x] 重新运行 Pyright，直到零告警：

当前 Pyright 记录：

- 已把 `backend/pyrightconfig.json` 绑定到真实 conda 环境 `trader`，修复 `fastapi`、`pydantic`、`sqlalchemy` 等依赖解析类 warning；这不是过滤或 ignore。
- 已真实修复 `support.loader.execute(...)` 分片模块缺少显式 imports、缺失 helper 和未使用变量导致的 Ruff/Pyright 问题。
- 完整 `cd backend && pyright`：`0 errors, 0 warnings, 0 informations`。
- 完整 `cd backend && ruff check .`：`All checks passed!`

```bash
cd backend && pyright
```

期望输出不包含 error 或 warning。

**验收：**

- Pyright 零 error、零 warning。
- Ruff 零 error。
- 代码中没有 `# ruff: noqa` 或 `# noqa`。
- 没有通过过滤配置、忽略注释或弱化类型规则隐藏问题。
- 所有测试迁移后的 fixture、fake、mock 也通过类型检查。

## 任务 13：最终验证和自审

**步骤：**

- [x] 跑后端定向测试：

```bash
cd backend && pytest -q -o addopts='' \
  tests/unit/app/services/research/agent/batch \
  tests/unit/app/services/research/agent/tools/test_analysis.py \
  tests/unit/app/services/research/agent/test_direct.py \
  tests/integration/app/services/research/agent/batch/test_repository.py \
  tests/integration/app/routers/test_sse_batch.py \
  tests/integration/app/db/test_analysis.py \
  tests/integration/app/routers/analysis/test_history.py \
  tests/integration/app/routers/analysis/test_queue_submission.py
```

当前实测结果：使用 `-o addopts='--import-mode=importlib'` 定向执行，`51 passed in 16.54s`。

- [x] 跑前端定向测试：

```bash
cd frontend && pnpm vitest run tests/integration/features/tasks/task-center-page.test.tsx --reporter=dot
```

当前实测结果：`1 passed`，文件内 `4 passed`。

- [x] 跑后端质量门：

```bash
cd backend && ruff check .
cd backend && pyright
```

当前实测结果：

- `ruff check .`：`All checks passed!`
- `pyright`：`0 errors, 0 warnings, 0 informations`

`ruff` 和 `pyright` 必须是零告警，不能通过新增过滤条件、忽略注释、Ruff 跳过注释或弱化规则通过。

- [x] 尝试后端全量测试：

```bash
cd backend && timeout 180s pytest -q -o addopts=''
```

当前实测结果：旧的无条件全量 pytest 命令曾在 180 秒硬超时后退出，exit code `124`，期间没有输出；不计为通过。随后按用户要求改为带边界的诊断方式，`timeout 60s pytest --collect-only -q` 仍在收集/导入阶段 60 秒无输出超时，说明后端全量套件存在既有收集期阻塞风险；后续应继续按目录分段 collect/run 并看日志定位，不能再直接无条件全量跑。已确认没有残留独立 pytest 进程。后端完成验证以批量 workflow 定向 51 个测试、Ruff 和 Pyright 为准。

- [x] 跑前端质量门：

```bash
cd frontend && pnpm lint
cd frontend && pnpm type-check
cd frontend && pnpm test
```

当前实测结果：

- `pnpm lint`：通过。
- `pnpm type-check`：通过，输出 `$ tsc --noEmit`。
- `pnpm test`：`31 passed (31)`，`146 passed (146)`。

- [x] 检查 diff：

```bash
git diff --stat
git diff -- backend/app/services/research/agent/batch backend/app/services/research/agent/tools/analysis.py backend/app/services/research/agent/direct.py backend/app/services/research/agent/stock.py backend/app/services/analysis/simple/status.py backend/app/routers/analysis backend/tests/unit backend/tests/integration backend/tests/e2e frontend/libs/api/analysis.ts frontend/features/tasks/task-center-page.tsx frontend/tests/integration/features/tasks
```

当前实测结果：已检查 `git diff --stat`；本轮 diff 覆盖既有测试目录迁移、批量 workflow、批量 route/status 兼容、direct tool 元数据、child event 批次上下文、前端 batch filter，以及为删除所有 `# ruff: noqa` / `# noqa` 后真实通过 Ruff/Pyright 而进行的全后端 lint/type 修复。

**验收：**

- 变更集中在测试目录命名迁移、批量 workflow、批量 route/status 兼容、direct tool 元数据、child event 批次上下文、前端 batch filter、Ruff/noqa 清理和 Pyright 真实类型修复。
- 不通过新增跳过检查、过滤配置、忽略注释或弱化规则来隐藏 Ruff/Pyright 问题。
- 如果全量测试因为耗时或环境失败，必须记录定向测试结果、失败命令、失败原因和剩余风险。

## 迁移映射审查

### API 映射

- `analysis/list.py::submit_batch_analysis` -> `BatchStockWorkflow.submit()` 或 route adapter。
- `analysis/queue.py::analyze_batch` -> 同一 batch submit adapter。
- `analysis/queue.py::get_batch` -> `BatchRepository.get_batch(batch_id, user_id)`，回退读取 Redis。
- `sse.py::stream_batch_progress` -> 新 batch status reader，保留旧 SSE event shape。
- `analysis/result.py::get_task_result` -> 不改变 child report 契约。

### Redis queue 语义映射

- `qa:batch:{batch_id}` -> `BatchWorkflowState`，可转旧哈希结构。
- `qa:batch_tasks:{batch_id}` -> `BatchWorkflowState.task_ids`。
- `qa:task:{task_id}` -> `BatchChildState`。
- `qa:ready` -> workflow job queue 或 background runner，必须保持“先提交后执行”（submission-first）。
- `qa:processing` / user processing set -> bounded concurrency。
- visibility timeout / lease 若本阶段不实现，必须显式记录为不支持或后续工作，不能伪装等价。

### DB/document 映射

- `analysis_batches.batch_id` -> 必填。
- `analysis_batches.user_id` -> 必填，所有查询按 user 过滤。
- `analysis_batches.status` -> tool/SSE 保留 `partial`，旧 Pydantic model 写入时映射 `partial_success`。
- `analysis_batches.total_tasks/completed_tasks/failed_tasks/cancelled_tasks/progress` -> 必填。
- `analysis_batches.parameters/results_summary/mapping` -> 必填。
- `analysis_tasks.task_id/batch_id/user_id/symbol/stock_code/stock_symbol` -> 必填。
- `analysis_tasks.status/progress/message/last_error` -> 必填。
- `analysis_reports` -> 单股 workflow 原样写。

### Agent tool 映射

- `batch_stock_analysis` -> 从 stub 改为 `BatchStockWorkflow.submit()`。
- `stock_analysis` -> child 复用同一底层 `StockDagParityWorkflow`，不通过 tool registry 递归调用。
- `stock_analysis_status` -> 可扩展 batch status 或新增 batch status 工具；本计划先保证 batch result 与 `/tasks?batch_id` 可查。
- `stock_analysis_report` -> batch result 返回 child report links，不伪装成单股 report。
- `DirectToolMixin.run_direct_tool` -> 识别 `task_ids` 和 `batch_id`。

### 前端映射

- `BatchAnalysisPage` -> payload 结构保持，提交后继续跳 `/tasks?batch_id=...`。
- `TaskCenterPage` -> 新增读取 `batch_id` search param。
- `TaskRow` -> 新增 `batch_id?: string`。
- `analysisApi.getHistory/getTaskList` -> 新增 `batch_id` 查询参数。
- 任务统计 -> batch filter 下统计 child tasks。

## 审查结论

### 覆盖性

- 已覆盖旧批量外层编排：验证、参数解析、批次 ID、子任务 ID、fan-out、非阻塞提交、状态聚合、事件、持久化、SSE 和前端跳转。
- 已覆盖 Agent 当前缺口：`batch_stock_analysis` stub、direct tool 元数据丢批次信息、child event 缺 `batch_id`。
- 已覆盖任务中心当前缺口：后端按 `batch_id` 过滤、history/list 输出 `batch_id`、前端读取并传递 `batch_id`。
- 已覆盖 `partial` 状态双命名风险：tool/SSE 保留 `partial`，旧 batch model 写入时才映射为 `partial_success`。
- 已覆盖单股 workflow 边界：批量层不得复制单股 DAG，不得调用旧 `run_native_stock_workflow()` 或 `TradingAgentsGraph.propagate()`。
- 已覆盖 AGENTS.md 测试命名要求：新后端测试路径使用 `backend/tests/unit|integration|e2e/.../test_<模块名>.py`，新前端测试路径使用 `frontend/tests/unit|integration|e2e/.../*.test.ts(x)` 或 e2e `*.spec.ts`，并增加现有前后端 `tests` 全量迁移任务。
- 已覆盖 Pyright 要求：新增真实消除 Pyright error/warning 的任务，并禁止通过过滤配置、忽略注释或弱化类型规则清除告警。

### 容易出错点

- 不能把 `wait_for_completion=true` 做成默认，否则会违背旧 API “先提交后执行”（submission-first）语义。
- 不能只修 Agent 工具而不修 `/tasks?batch_id=...`，否则用户提交后仍看不到批次任务。
- 不能只记录一个总错误；每个失败 child 都要有独立状态和错误。
- 不能只用 `batch_id` 查询批次；所有 batch/status/history/report 查询都必须带所有者隔离条件。
- 不能把 `partial` 全局替换成 `partial_success`；SSE 兼容层需要旧终态 `partial`。
- 不能继续新增 `backend/tests/regression/.../test.py` 或 `backend/tests/app/.../test.py`。
- 不能为了通过 Pyright 修改配置过滤、添加 ignore 注释或把类型退化成 `Any`。

### 阻断性验收

实施完成前必须有以下测试通过：

- `batch_stock_analysis` 不再返回 accepted stub。
- 默认批量提交不会同步执行完整批次。
- 单个 child 失败时 batch 返回 `partial` 并保留失败明细。
- child event 和 child report 都能通过 `batch_id` 关联回批次。
- `/tasks?batch_id=...` 能展示该批次 child tasks。
- 按所有者隔离的 `batch_id` 过滤不会泄漏其他用户数据。
- `backend/tests` 只保留 `unit`、`integration`、`e2e` 三类测试目录和必要配置文件。
- `frontend/tests` 只保留 `unit`、`integration`、`e2e` 三类测试目录和必要配置文件。
- `cd backend && pyright` 零 error、零 warning。
