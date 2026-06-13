# Standards 驱动的当前代码重构规格说明

日期：2026-06-13

## 结论先行

本规格的目标是：**按照 `standards/` 的模块、类型、错误、契约、前端、数据库、测试和 review 规范，对当前代码中已经出现的职责混杂、状态流不清、fallback 语义不明、边界类型松散和胖 Router 问题进行分阶段重构。**

这不是以下方案：

- 不是新增业务能力。
- 不是重写研究 Agent、设置页、纸上交易或报告系统。
- 不是为了行数达标做机械拆文件。
- 不是一次性清理全仓 broad exception。
- 不是调整 UI 视觉设计。
- 不是改变现有 API contract、报告格式、任务链接或用户可见流程，除非某一阶段明确列为 contract 变更并补齐前后端测试。

正确方向是：**先用测试锁定当前行为，再按稳定业务边界拆分深模块，让入口变薄、状态源明确、错误语义稳定、类型边界可验证。**

## Review 修正结论

对本规格按 `standards/review.md` 自审后，有三条约束必须写入规格正文：

1. **范围必须分阶段交付。** 当前问题横跨研究 Agent、配置、任务状态、纸上交易、报告和错误处理。如果放进一个实现计划，会违反 `standards/review.md` 的 scope 控制，也会让测试和回滚成本过高。
2. **任何重构先补行为锁定测试。** `standards/testing.md` 要求先用最窄测试锁住行为。每一阶段都必须先补或运行对应回归测试，再移动代码。
3. **错误/fallback 收紧不能改变现有成功响应。** `standards/contracts.md` 和 `standards/errors.md` 要求公开 contract 稳定。fallback 语义可以显式化，但不得在未声明 contract 变更时改变现有成功字段、状态码或前端跳转。

## 适用 Standards

| 标准 | 本规格中的约束 |
| --- | --- |
| `standards/modules.md` | 以不变量和变更原因拆边界；避免 shallow wrapper；FastAPI route 和 React page 保持薄。 |
| `standards/typing.md` | 外部 payload、event、配置解析、报告/任务 read model 必须有显式 DTO 或 narrowing 边界。 |
| `standards/errors.md` | broad exception 只允许在明确边界；fallback 必须可观察；不能把未知错误转成空结果。 |
| `standards/contracts.md` | API、前端 client、事件 payload、报告链接和任务状态字段必须同步更新和测试。 |
| `standards/frontend.md` | 复杂 UI 状态机下沉到 hooks/reducer；组件主要渲染 UI state。 |
| `standards/database.md` | 持久化读取、fallback、用户 scope 和写入事务归属必须明确。 |
| `standards/testing.md` | 先补最小回归测试；测试路径靠近 owning boundary；先跑 scoped verification。 |
| `standards/review.md` | 每阶段完成后检查 diff scope、架构、类型、错误、契约、测试和验证记录。 |

## 全局重构原则

1. **行为优先不变。** 重构阶段默认不改变现有功能行为、响应 shape、路由、链接、权限和持久化字段。
2. **先深后拆。** 只有当新边界拥有真实不变量、类型或策略时才抽模块；不创建只转发参数的浅包装。
3. **入口变薄。** FastAPI route、React page 和 tool entrypoint 只做参数接收、依赖注入、调用 owning boundary、响应映射。
4. **边界类型化。** loose dict 只允许在 raw transport 或 legacy adapter 边界出现，进入业务层前必须 narrow。
5. **fallback 可观察。** 业务 fallback 要有明确触发条件、日志和调用方可识别的 degraded 语义；未知错误不能伪装成空数据。
6. **测试伴随边界。** 每移动一个不变量，就把对应测试移到 owning boundary 附近。

## 阶段划分

| 阶段 | 范围 | 目标 | 是否允许 contract 变更 |
| --- | --- | --- | --- |
| Phase 0 | 测试锁定与安全网 | 补关键行为回归测试，不移动业务代码 | 不允许 |
| Phase 1 | 研究 Agent 前端状态和 `stock.py` command/event 边界 | 降低主分析链路复杂度 | 不允许 |
| Phase 2 | 设置页与 Provider 解析 | 拆分设置页，统一 Provider 解析边界 | 不允许；内部 DTO 可新增 |
| Phase 3 | 分析任务状态、paper router、reports router | 明确状态源、route 变薄、错误语义稳定 | 仅允许兼容性新增字段 |
| Phase 4 | broad exception 与 loose typing 横切治理 | 按模块族收紧 fallback 和类型 | 逐项声明 |

## Phase 0：行为锁定

### 当前风险

当前高风险路径缺少足够聚焦的小测试。大集成测试存在，但不适合作为每次重构的唯一定位手段：

- `frontend/tests/integration/components/research-agent-page.test.tsx` 约 975 行。
- `backend/tests/integration/app/services/research/agent/test_analysis.py` 约 896 行。
- `backend/tests/integration/app/services/research/agent/sessions/test_events.py` 约 1117 行。
- `frontend/tests/integration/components/stock.test.tsx` 约 895 行。

### 规格要求

Phase 0 必须补齐或确认以下测试后，才能进入对应实现阶段：

| 行为 | 测试层级 | 建议位置 |
| --- | --- | --- |
| 研究 Agent 切换会话时旧 stream 停止，新会话消息和工具状态加载正确 | frontend integration | `frontend/tests/integration/features/research-agent/` |
| terminal event 后 running 结束，completion polling 停止 | frontend integration | `frontend/tests/integration/features/research-agent/` |
| stock tool payload 转 `AnalysisParameters` 的结果稳定 | backend unit | `backend/tests/unit/app/services/research/agent/` |
| stock node event 到 stage/progress 的映射稳定 | backend unit | `backend/tests/unit/app/services/research/agent/` |
| report detail/list 用户隔离不变 | backend integration | 现有 reports router tests 附近 |
| paper buy/sell 余额和持仓不变量不变 | backend unit/integration | `backend/tests/unit/app/services/paper/` 或现有 router tests 附近 |

### 验收标准

- 每个后续 phase 至少有一个会在重构破坏行为时失败的测试。
- 不新增 E2E 框架。
- 不引入真实外部网络、真实 DB、真实第三方密钥。

## Phase 1：研究 Agent 与单股 workflow 边界

### 现状证据

前端：

- `frontend/features/research-agent/research-agent-page.tsx` 约 898 行。
- `ResearchAgentPage` 同时维护 session、messages、tools、goal、input、running、sessionLoading、config card、stream refs、polling refs、live status。
- `research-agent-page.tsx:82-151` 加载 session 数据。
- `research-agent-page.tsx:226-313` 刷新 attempt 和 polling。
- `research-agent-page.tsx:374-480` 处理 stream event。
- `research-agent-page.tsx:501-554` 执行 prompt。
- `research-agent-page.tsx:599-615` 执行 stock/batch tool。

后端：

- `backend/app/services/research/agent/stock.py` 约 939 行。
- `stock.py:101-303` 模型和 Provider 解析。
- `stock.py:181-376` symbol、market、analyst、depth、`AnalysisParameters` 构造。
- `stock.py:516-676` workflow context 构造和执行。
- `stock.py:679-766` workflow event bridge。
- `stock.py:768-845` usage 记录。

事件：

- `frontend/features/agent/event.ts` 约 664 行。
- 多数函数从 `Record<string, unknown>` 读取字段并直接生成展示文案或 tool state。

### 目标边界

#### Frontend

`ResearchAgentPage` 的目标职责：

- 读取 hook 暴露的 view state。
- 渲染 session rail、message list、tool rail、composer、config card。
- 把用户操作转发给 hook action。

必须从页面中分离的边界：

| 边界 | 职责 |
| --- | --- |
| `useResearchSession` | session list、active session、load/select/rename/delete。 |
| `useResearchAttempt` | active attempt、running、completion polling、terminal refresh。 |
| `useResearchStream` | subscribe/unsubscribe、last event id、stream event dispatch。 |
| `useResearchComposer` | input、prompt build、submit、keyboard behavior。 |
| `ResearchUiMode` reducer | `chat`、`stock_config`、`batch_config`、`running` 等互斥 UI 模式。 |

#### Backend

`stock.py` 必须被拆成拥有明确职责的边界：

| 边界 | 当前来源 | 目标职责 |
| --- | --- | --- |
| `StockAnalysisCommand` | `_normalize_*`、`_analysis_parameters` | 从 raw payload 构造 typed command，处理 market/symbol/depth/analyst/model 字段。 |
| `StockModelResolver` | `_configured_model_for_role`、`_resolve_analysis_models` | 选择 quick/deep model 并返回可诊断结果。 |
| `StockWorkflowRunner` | `build_agent_stock_workflow_context`、`run_agent_stock_workflow` | 执行 workflow，返回 typed result。 |
| `StockWorkflowEventAdapter` | `_emit_stock_workflow_stage`、`_stock_workflow_node_emitter` | node/stage/progress 映射和 event bridge。 |
| `StockUsageRecorder` | `_record_stock_workflow_usage`、token/pricing helpers | 记录用量，不影响主 workflow 成败。 |

#### Event parsing

`frontend/features/agent/event.ts` 的目标职责：

- 只保留 raw event 到 typed event 的 narrowing。
- tool preview 和 UI 文案移动到对应 feature adapter。
- `toolsFromEvents` 只消费 typed event。

### Contract 要求

Phase 1 不允许改变：

- `stock_analysis` tool 名称。
- `batch_stock_analysis` 现有入口行为。
- `task_id`、`analysis_id`、`links`、`report_url` 字段。
- Agent session event 的现有成功/失败语义。
- 前端用户可见的提交、取消、报告跳转流程。

### 测试要求

Backend：

- `StockAnalysisCommand` 单元测试：输入 legacy payload，输出与当前 `AnalysisParameters` 等价。
- `StockWorkflowEventAdapter` 单元测试：node 到 stage/progress/title 映射等价。
- `StockWorkflowRunner` 集成测试：mock workflow result 后返回 shape 保持不变。

Frontend：

- UI mode reducer 单元测试：互斥状态不能同时打开 stock 和 batch config。
- `useResearchStream` 集成测试：unmount/select session 时停止订阅。
- `useResearchAttempt` 集成测试：terminal event 后停止 polling。

### 验收标准

- `research-agent-page.tsx` 不再直接拥有 stream/polling 的底层 refs。
- `stock.py` 不再同时包含 command parsing、event bridge 和 usage pricing。
- 没有新增 `any` / `Any` 作为逃避类型边界。
- 现有 Agent stock workflow 集成测试通过。

## Phase 2：设置页与 Provider 解析边界

### 现状证据

前端：

- `frontend/features/settings/settings-pages.tsx` 约 4197 行。
- 同一文件内包含 `SettingsIndexPage`、`ConfigManagementPage`、`DatabaseManagementPage`、`OperationLogsPage`、`SystemLogsPage`、`SyncManagementPage`、`CacheManagementPage`、`UsageStatisticsPage`、`SchedulerManagementPage`。
- `ConfigManagementPage` 维护多组 dialog/form/editing state 和 9 个 config query。

后端：

- `backend/app/services/config/provider.py` 约 844 行，负责 Provider catalog、CRUD、env migration。
- `backend/app/services/config/testing/provider.py` 约 739 行，负责多 Provider API 测试。
- `backend/app/services/research/agent/provider/client.py` 约 805 行，既解析 Agent 模型配置，又发送模型请求。

### 目标边界

Frontend：

| 边界 | 目标职责 |
| --- | --- |
| settings page modules | 每个设置页面单独文件，保留现有 route export。 |
| config hooks | 持有 query key、mutation、cache invalidation。 |
| config form components | Provider、LLM、DataSource、Database、Market/Grouping 表单拆分。 |
| shared settings UI | `GenericTable`、`LoadingButton`、`StatusBadge` 等局部共享组件。 |

Backend：

| 边界 | 目标职责 |
| --- | --- |
| `ProviderCatalog` | Provider 元数据、alias、默认 base URL、支持能力、环境变量 key。 |
| `ProviderResolver` | 输入模型名、用户、系统配置，输出 typed resolved provider。 |
| `ProviderTester` | 消费 provider config/resolution，执行连接测试。 |
| `ModelClient` | 只负责 HTTP/streaming/completion，不负责选择 Provider。 |

### Contract 要求

Phase 2 不允许改变：

- 设置页路由。
- `configApi` 对外方法名。
- Provider、LLM、DataSource、Database 现有响应字段。
- secret redaction 行为。

### 测试要求

Frontend：

- `ConfigManagementPage` smoke test：Provider 保存、模型导入、DataSource 编辑。
- 页面拆分后 route/tab 行为保持。

Backend：

- Provider alias/base URL/env key resolution 单元测试。
- placeholder key、用户级 key、环境变量 key、DB key 优先级测试。
- Provider test 和 Agent runtime 使用同一 resolver 的一致性测试。

### 验收标准

- `settings-pages.tsx` 不再承载所有设置页面。
- `client.py` 不再同时拥有 Provider resolution 和 ModelClient 两类职责。
- Provider 新增或修改只需要更新 catalog/resolver/tester 明确边界。

## Phase 3：任务状态、Paper Router、Reports Router

### 现状证据

任务状态：

- `runner.py:51-98` 同时更新 tracker、memory manager、PostgreSQL。
- `status.py:33-159` 读 memory 并合并 Redis progress。
- `status.py:161-556` 合并 memory、PostgreSQL table/document 任务列表。
- 多处 `except Exception` 返回 `[]` 或 `None`。

Paper：

- `backend/app/routers/paper.py` 约 786 行。
- Router 内处理市场识别、账户创建/迁移、下单、手续费、持仓、读取 fallback。

Reports：

- `backend/app/routers/reports.py` 约 752 行。
- Router 内处理 stock name cache、query 构造、scope、list/detail/delete/download。
- 多处 `HTTPException(status_code=500, detail=str(e))`。

### 目标边界

任务状态：

| 边界 | 目标职责 |
| --- | --- |
| `ProgressGateway` | runner 写进度的唯一入口。 |
| `TaskStatusRepository` | 读取 memory/Redis/PostgreSQL raw snapshots。 |
| `TaskStatusAggregator` | 合并优先级、degraded 标记、输出统一状态。 |
| `TaskScopePolicy` | user/admin/scope 判断。 |

Paper：

| 边界 | 目标职责 |
| --- | --- |
| `PaperAccountService` | 账户创建、迁移、读取。 |
| `PaperOrderService` | 下单、手续费、现金和持仓不变量。 |
| `PaperRepository` | 文档库/PostgreSQL 读写与 fallback。 |

Reports：

| 边界 | 目标职责 |
| --- | --- |
| `ReportLookupService` | 按 `_id` / `analysis_id` / `task_id` 统一查询。 |
| `ReportScopePolicy` | admin/user scope。 |
| `ReportListService` | report/task 合并 read model。 |
| `ReportExportService` | markdown/json/html 下载。 |

### Contract 要求

允许兼容性新增字段：

- 状态/列表接口可新增 `degraded` 或 `warnings` 字段，但不得删除现有字段。
- 错误响应可新增稳定 code，但不得改变现有成功响应 shape。

不允许：

- 写路径失败后静默 fallback 成成功。
- 报告、交易、任务状态公开 500 返回原始异常文本。

### 测试要求

任务状态：

- memory/Redis/PostgreSQL 状态合并优先级测试。
- 读取失败不返回伪空列表测试。
- 非 owner 查询行为一致性测试。

Paper：

- 买入现金不足、卖出持仓不足、手续费、均价更新测试。
- PostgreSQL 读失败 fallback 行为测试。
- 写失败不伪成功测试。

Reports：

- 普通用户不能读/删别人报告。
- `_id` / `analysis_id` / `task_id` 三种 lookup 保持。
- 下载 content-type、文件名、unsupported format 错误稳定。

### 验收标准

- `paper.py` 和 `reports.py` route handler 只保留 HTTP 边界职责。
- 任务状态读取能表达 degraded 状态，不能把依赖故障伪装成空数据。
- 公开 API 不再返回原始异常文本。

## Phase 4：横切错误处理和类型治理

### 现状证据

命中较多的 broad exception 区域：

- `backend/app/routers/config/market.py`
- `backend/app/routers/config/settings.py`
- `backend/app/routers/config/providers.py`
- `backend/app/services/config/provider.py`
- `backend/app/services/analysis/simple/status.py`
- `backend/app/routers/paper.py`
- `backend/app/routers/reports.py`

loose typing 热点：

- `backend/app/services/research/agent/stock.py`
- `backend/app/services/analysis/simple/status.py`
- `backend/app/routers/paper.py`
- `backend/app/routers/reports.py`
- `backend/app/services/config/provider.py`
- `frontend/features/agent/event.ts`

### 规格要求

- 每个 broad exception 必须被归类为 expected fallback、boundary translation 或 unexpected error。
- expected fallback 必须说明：触发条件、为什么可继续、调用方如何观察、日志字段。
- unexpected error 必须通过现有错误边界失败，不得转成 `None` / `[]` / success。
- loose dict 必须逐步收敛到 DTO、Pydantic model、TypedDict、dataclass 或 TypeScript union。

### 验收标准

- 新增代码不得引入新的 broad `except Exception`，除非是边界层并带有结构化日志和稳定错误映射。
- 新增前端代码不得引入 `any` / `as any` / `Record<string, any>`。
- 所有 fallback 都能在测试中被触发和断言。

## Review Checklist

执行任何 phase 前，必须逐项检查：

- Scope：本 phase 是否只改声明范围内文件。
- Architecture：是否新增了拥有真实不变量的深模块，而不是浅 wrapper。
- Types：是否减少 loose dict/unknown 传播，是否没有新增 `Any`/`any`。
- Errors：是否区分 expected failure 和 unexpected failure。
- Contracts：是否保持现有成功响应 shape，contract 变更是否同步前后端。
- Database：读写、fallback、scope、事务归属是否明确。
- Frontend：组件是否更薄，复杂状态是否下沉，loading/error/empty 是否保留。
- Tests：是否先有行为锁定测试，且 verification 命令已实际运行。

## Verification Strategy

每个 phase 默认先跑 scoped verification：

Backend examples：

```bash
cd backend && ruff check path/to/touched.py
cd backend && pyright
cd backend && pytest path/to/relevant_test.py
```

Frontend examples：

```bash
cd frontend && pnpm exec eslint path/to/touched.tsx
cd frontend && pnpm vitest run path/to/relevant.test.tsx
cd frontend && pnpm type-check
```

当 phase 触及 shared contracts、API client、router、workflow event、任务状态或设置页公共组件时，必须扩大到相关 full gate。

## Spec Review

### Findings

HIGH：本规格覆盖范围较广，不能作为单次 implementation plan 执行。

- Impact：一次性执行会导致 diff 过大、测试定位困难、回滚成本高。
- Required action：后续必须按 Phase 0/1/2/3/4 拆成独立 plan，每个 plan 只覆盖一个 owning boundary。

MEDIUM：Phase 3 中 `degraded` / `warnings` 属于兼容性新增字段，仍需要单独确认前端展示和 API 文档。

- Impact：如果直接透传到前端但不展示，会形成无效 contract；如果展示，又是用户可见行为变化。
- Required action：Phase 3 plan 必须列出具体接口和前端处理方式。

MEDIUM：Provider resolver 统一会影响 settings、testing、agent runtime 三条路径，测试矩阵必须先写。

- Impact：Provider 解析错误会直接影响 Agent 可用性。
- Required action：Phase 2 plan 必须先列 provider/key/base_url 优先级测试表。

LOW：测试文件尺寸本身不是独立重构目标。

- Impact：为了拆测试而拆测试会制造无价值 churn。
- Required action：仅在对应行为重构时拆出局部 helper 或新增聚焦测试。

### Recommendation

COMMENT：规格方向符合 `standards/`，但不能直接进入实现。下一步应先生成 Phase 0/Phase 1 的独立 plan，并在 plan 中明确具体文件、测试、验收和回滚边界。
