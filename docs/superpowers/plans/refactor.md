# Standards 驱动重构任务规划

> **给执行 agent：** 实施多条独立任务线时必须使用 `superpowers:subagent-driven-development`；单 phase 独立会话实施时使用 `superpowers:executing-plans`。本计划使用 checkbox 任务，执行时直接按项更新状态。

**目标：** 按 `docs/superpowers/specs/2026-06-13-standards-driven-refactor.md` 分阶段完成当前代码重构：先锁定行为，再收敛研究 Agent、配置 Provider、任务状态、Paper、Reports、错误处理和类型边界。

**架构策略：** 这是主任务规划，不是单次实现计划。每个 phase 独立交付、独立 review、独立验证；后一个 phase 只能在前一个 phase 的测试和 review 通过后开始。默认不改变现有 API 成功响应、路由、链接、权限、报告格式和用户可见流程。

**技术栈：** Python、FastAPI、SQLAlchemy、pytest、Ruff、Pyright、Next.js、React、TypeScript、Vitest、pnpm、conda env `trader`。

---

## 1. 执行约束

- 不 commit、不 push，除非用户在当前任务中明确要求。
- 不新增依赖，除非用户明确要求。
- 每个 phase 先补行为锁定测试，再移动代码。
- 每次只改 phase 声明范围内的 owning boundary；不做全仓格式化。
- 不新增 `Any`、`any`、`as any`、`Record<string, any>` 作为逃避类型边界。
- 不把未知错误转成 `None`、`[]`、空成功响应或静默 fallback。
- 所有新增 fallback 必须可观察：触发条件、日志字段、调用方可识别的 degraded 语义。
- 兼容性新增字段只允许在 Phase 3 中出现，且必须保持现有成功响应字段不变。
- 后端命令默认通过 `conda run -n trader` 执行。

## 2. Phase 依赖图

```text
Phase 0 行为锁定
  -> Phase 1 研究 Agent + stock workflow 边界
  -> Phase 2 设置页 + Provider resolver 边界
  -> Phase 3 任务状态 + Paper + Reports 边界
  -> Phase 4 横切错误处理 + loose typing 治理
```

Phase 0 是所有后续阶段的强依赖。Phase 1、Phase 2、Phase 3 在 Phase 0 完成后可以按风险顺序执行，但同一分支内仍建议串行交付，避免 review 和回滚范围过大。Phase 4 必须在对应 owning boundary 完成后按模块族逐项治理。

## 3. 文件范围总览

| Phase | 主要源文件 | 主要测试位置 |
| --- | --- | --- |
| Phase 0 | 不移动业务代码 | `frontend/tests/integration/components/`、`backend/tests/unit/app/services/research/agent/`、`backend/tests/integration/app/routers/reports/`、paper 相关现有测试附近 |
| Phase 1 | `frontend/features/research-agent/research-agent-page.tsx`、`frontend/features/agent/event.ts`、`backend/app/services/research/agent/stock.py` | research-agent frontend integration、agent backend unit/integration |
| Phase 2 | `frontend/features/settings/settings-pages.tsx`、`backend/app/services/config/provider.py`、`backend/app/services/config/testing/provider.py`、`backend/app/services/research/agent/provider/client.py` | settings frontend integration、config/provider backend unit/integration |
| Phase 3 | `backend/app/services/analysis/simple/runner.py`、`backend/app/services/analysis/simple/status.py`、`backend/app/routers/paper.py`、`backend/app/routers/reports.py` | analysis status、paper、reports router/service tests |
| Phase 4 | Phase 1-3 已触达模块中的 broad exception 和 loose typing 热点 | 每个 owning boundary 的新增回归测试 |

## 4. Phase 0：行为锁定

### Task P0.1：建立现有测试和缺口清单

- [ ] 运行以下只读清单命令，记录现有测试覆盖点：

```bash
rg -n "research-agent|stock_analysis|batch_stock_analysis|report|paper|provider|completion|status" frontend/tests backend/tests
rg -n "except Exception|Record<string, unknown>|Any|dict\\[" backend/app frontend/features
```

- [ ] 输出 phase-local notes，列明已有测试是否已经覆盖 spec 要求的六类行为。
- [ ] 不修改业务代码。

验收:

- Phase 0 后续测试任务能明确复用哪些现有 fixture、哪些行为必须新补测试。
- 没有把“大测试文件很长”作为独立重构目标。

### Task P0.2：锁定研究 Agent 前端行为

文件:

- 修改或新增靠近 `frontend/tests/integration/components/research-agent-page.test.tsx` 的聚焦测试。
- 如果新增镜像 feature 测试路径，必须沿用现有前端测试目录约定。

步骤:

- [ ] 添加会话切换行为测试：旧 stream 停止，新 session 的 messages、tools、goal、running state 正确加载。
- [ ] 添加 terminal event 行为测试：running 结束，completion polling 停止，不继续刷新已终止 attempt。
- [ ] 添加 stock/batch config 互斥行为测试：不能同时打开两个 config UI state。

验证:

```bash
cd frontend && pnpm vitest run tests/integration/components/research-agent-page.test.tsx
cd frontend && pnpm type-check
```

验收:

- 如果 Phase 1 破坏 stream cleanup、polling stop 或互斥 UI mode，测试会失败。
- 不新增 E2E 框架，不访问真实网络。

### Task P0.3：锁定 stock workflow 命令和事件行为

文件:

- 在 `backend/tests/unit/app/services/research/agent/` 下新增聚焦后端测试。
- 复用当前 stock workflow fixture，或创建窄范围本地 fixture。

步骤:

- [ ] 添加 legacy payload 到 `AnalysisParameters` 等价输出测试。
- [ ] 添加 symbol、market、analyst、depth、quick/deep model 默认值测试。
- [ ] 添加 stock node event 到 stage/progress/title 映射测试。
- [ ] 添加 workflow result shape 稳定测试，使用 mock workflow result，不触发真实外部服务。

验证:

```bash
cd backend && conda run -n trader pytest tests/unit/app/services/research/agent
cd backend && conda run -n trader pyright
```

验收:

- Phase 1 拆分 `stock.py` 后必须通过这些测试。
- 测试断言现有 contract，不引入新业务能力。

### Task P0.4：锁定 Reports、Paper、Status 公开行为

文件:

- `backend/tests/integration/app/routers/reports/`
- router/service 边界附近的现有 paper 测试。
- `backend/tests/integration/app/routers/analysis/`

步骤:

- [ ] 添加或确认 report list/detail 的用户隔离测试。
- [ ] 添加或确认 `_id`、`analysis_id`、`task_id` 三种 report lookup 测试。
- [ ] 添加或确认 paper buy/sell 的现金、持仓、手续费、均价不变量测试。
- [ ] 添加 task status 读取失败不能伪装成空成功列表的测试。

验证:

```bash
cd backend && conda run -n trader pytest tests/integration/app/routers/reports
cd backend && conda run -n trader pytest tests/integration/app/routers/analysis
```

验收:

- Phase 3 route 变薄时公开行为被测试锁住。
- 写路径失败不伪成功的行为有可失败测试。

### Task P0.5：Phase 0 review gate

- [ ] 检查 Phase 0 diff 只包含测试和必要 test fixture。
- [ ] 检查没有新增业务文件、依赖、contract 字段。
- [ ] 运行：

```bash
cd backend && conda run -n trader ruff check tests
cd frontend && pnpm vitest run tests/integration/components/research-agent-page.test.tsx
```

Review 要求:

- Review 结论为“通过”后才能进入 Phase 1。
- 如果发现测试不稳定或依赖真实外部服务，必须先修 Phase 0。

## 5. Phase 1：研究 Agent 与 stock workflow 边界

### Task P1.1：引入前端 UI mode reducer

文件:

- 修改 `frontend/features/research-agent/research-agent-page.tsx`。
- 在现有 `frontend/features/research-agent/` 边界下新增聚焦本地模块。
- 在现有 research-agent 测试附近新增单元或集成测试。

步骤:

- [ ] 定义 `ResearchUiMode`，覆盖 `chat`、`stock_config`、`batch_config`、`running` 等互斥状态。
- [ ] 把页面中的 config card toggle、submit running state 接入 reducer。
- [ ] 保持按钮、配置面板、提交流程现有可见行为不变。

验证:

```bash
cd frontend && pnpm vitest run tests/integration/components/research-agent-page.test.tsx
cd frontend && pnpm type-check
```

验收:

- 不存在 stock config 和 batch config 同时打开的状态。
- 页面不再散落维护互斥 UI boolean。

### Task P1.2：抽出 `useResearchSession`

文件:

- 修改 `frontend/features/research-agent/research-agent-page.tsx`。
- 在 `frontend/features/research-agent/` 下新增 hook 模块。

步骤:

- [ ] 从页面中移动 session list、active session、load/select/rename/delete 逻辑。
- [ ] hook 对页面暴露 typed state 和 action，不暴露内部 fetch/cache 细节。
- [ ] 保持 session rail 的 loading、empty、error、selection 行为不变。

验证:

```bash
cd frontend && pnpm vitest run tests/integration/components/research-agent-page.test.tsx
cd frontend && pnpm type-check
```

验收:

- `ResearchAgentPage` 不直接维护 session loading 和 session fetch 细节。
- session 切换测试通过。

### Task P1.3：抽出 `useResearchAttempt`

文件:

- 修改 `frontend/features/research-agent/research-agent-page.tsx`。
- 在 `frontend/features/research-agent/` 下新增 hook 模块。

步骤:

- [ ] 移动 active attempt、running、completion polling、terminal refresh 逻辑。
- [ ] polling 的 start/stop 只由 hook 管理。
- [ ] terminal event 后停止 polling，并触发最终状态刷新。

验证:

```bash
cd frontend && pnpm vitest run tests/integration/components/research-agent-page.test.tsx
cd frontend && pnpm type-check
```

验收:

- 页面不直接持有 polling refs。
- terminal event 回归测试通过。

### Task P1.4：抽出 `useResearchStream`

文件:

- 修改 `frontend/features/research-agent/research-agent-page.tsx`。
- 在 `frontend/features/research-agent/` 下新增 hook 模块。

步骤:

- [ ] 移动 subscribe、unsubscribe、last event id、stream event dispatch。
- [ ] unmount 和 active session 切换时关闭旧订阅。
- [ ] hook 只输出 typed event 或 view action，不输出 raw EventSource 细节。

验证:

```bash
cd frontend && pnpm vitest run tests/integration/components/research-agent-page.test.tsx
cd frontend && pnpm type-check
```

验收:

- 页面不直接维护 stream refs。
- 旧 session stream cleanup 测试通过。

### Task P1.5：收敛 `frontend/features/agent/event.ts`

文件:

- 修改 `frontend/features/agent/event.ts`。
- 只在确实承载 UI 或领域语义的位置新增 typed feature adapter。

步骤:

- [ ] 保留 raw event 到 typed event 的 narrowing 边界。
- [ ] 把 tool preview、UI 文案、tool state 生成迁移到对应 feature adapter。
- [ ] `toolsFromEvents` 只消费 typed event。
- [ ] 不引入 `any`、`as any`、`Record<string, any>`。

验证:

```bash
cd frontend && pnpm vitest run tests/integration/components/research-agent-page.test.tsx
cd frontend && pnpm type-check
```

验收:

- raw transport 字段不会穿透到 UI 业务逻辑。
- 现有 tool 展示和消息文案保持。

### Task P1.6：新增 `StockAnalysisCommand`

文件:

- 修改 `backend/app/services/research/agent/stock.py`。
- 在 `backend/app/services/research/agent/` 下新增聚焦模块。
- 在 `backend/tests/unit/app/services/research/agent/` 下新增测试。

步骤:

- [ ] 把 raw payload、symbol、market、analyst、depth、model 字段解析移入 typed command。
- [ ] `StockAnalysisCommand` 输出当前 `AnalysisParameters` 等价数据。
- [ ] command 不执行 workflow、不发 event、不记录 usage。

验证:

```bash
cd backend && conda run -n trader pytest tests/unit/app/services/research/agent
cd backend && conda run -n trader pyright
```

验收:

- `stock.py` 不再直接散落 payload normalization。
- legacy payload 等价测试通过。

### Task P1.7：拆出 workflow runner、event adapter、usage recorder

文件:

- 修改 `backend/app/services/research/agent/stock.py`。
- 在 `backend/app/services/research/agent/` 下新增聚焦模块。
- 在 `backend/tests/unit/app/services/research/agent/` 下新增测试。

步骤:

- [ ] `StockWorkflowRunner` 负责构造 context、执行 workflow、返回 typed result。
- [ ] `StockWorkflowEventAdapter` 负责 node/stage/progress/title 映射和 event bridge。
- [ ] `StockUsageRecorder` 负责 token/pricing/usage 写入，失败只记录可观察日志，不影响主 workflow 成功。
- [ ] 保持 `stock_analysis` 和 `batch_stock_analysis` tool name、`task_id`、`analysis_id`、`links`、`report_url` 不变。

验证:

```bash
cd backend && conda run -n trader pytest tests/unit/app/services/research/agent
cd backend && conda run -n trader pytest tests/integration/app/services/research/agent/test_analysis.py
cd backend && conda run -n trader ruff check app/services/research/agent tests/unit/app/services/research/agent
cd backend && conda run -n trader pyright
```

验收:

- `stock.py` 不再同时包含 command parsing、workflow event bridge 和 usage pricing。
- usage 记录失败不会改变 workflow result contract。

### Task P1.8：Phase 1 review gate

- [ ] 检查 `ResearchAgentPage` 是否只负责组合 hooks 和渲染。
- [ ] 检查新模块是否拥有真实不变量，避免只转发参数的 shallow wrapper。
- [ ] 检查后端 public tool contract 未变化。
- [ ] 检查 frontend/backend 类型没有放宽。
- [ ] 运行 scoped gates：

```bash
cd frontend && pnpm vitest run tests/integration/components/research-agent-page.test.tsx
cd frontend && pnpm type-check
cd backend && conda run -n trader pytest tests/unit/app/services/research/agent
cd backend && conda run -n trader pytest tests/integration/app/services/research/agent/test_analysis.py
cd backend && conda run -n trader pyright
```

Review 要求:

- Review 结论为“通过”后才能进入 Phase 2。

## 6. Phase 2：设置页与 Provider 解析边界

### Task P2.1：拆分设置页模块

文件:

- 修改 `frontend/features/settings/settings-pages.tsx`。
- 在现有 settings feature 边界下新增聚焦页面模块。

步骤:

- [ ] 保留现有 route export 和页面入口。
- [ ] 将 `SettingsIndexPage`、`ConfigManagementPage`、`DatabaseManagementPage`、`OperationLogsPage`、`SystemLogsPage`、`SyncManagementPage`、`CacheManagementPage`、`UsageStatisticsPage`、`SchedulerManagementPage` 拆到各自模块。
- [ ] 入口文件只做 export/组合，不承载页面内部状态。

验证:

```bash
cd frontend && pnpm vitest run tests/integration/components/settings-index-page.test.tsx
cd frontend && pnpm type-check
```

验收:

- 设置页路由、tab、跳转行为不变。
- `settings-pages.tsx` 不再承载所有设置页面逻辑。

### Task P2.2：抽出 config hooks 和表单组件

文件:

- Settings feature modules.
- 如有必要，修改现有 API client 模块。

步骤:

- [ ] 抽出 Provider、LLM、DataSource、Database、Market/Grouping 的 query/mutation hooks。
- [ ] 抽出对应 form/table/dialog 组件。
- [ ] cache invalidation 留在 hook 边界，不散落在页面组件。
- [ ] 保持 loading、empty、error、save success、secret redaction 行为不变。

验证:

```bash
cd frontend && pnpm vitest run tests/integration/components/settings-index-page.test.tsx
cd frontend && pnpm type-check
```

验收:

- `ConfigManagementPage` 主要组合 hooks 和组件。
- Provider 保存、模型导入、DataSource 编辑测试通过。

### Task P2.3：建立 `ProviderCatalog` 和 `ProviderResolver`

文件:

- 修改 `backend/app/services/config/provider.py`。
- 修改 `backend/app/services/research/agent/provider/client.py`。
- 在现有 config/provider 边界下新增聚焦模块。
- 在 `backend/tests/unit/app/services/config/` 和相关 agent provider 测试附近新增测试。

步骤:

- [ ] `ProviderCatalog` 负责 Provider 元数据、alias、默认 base URL、能力、环境变量 key。
- [ ] `ProviderResolver` 输入模型名、用户、系统配置，输出 typed resolved provider。
- [ ] 明确 key 优先级：placeholder key、用户级 key、环境变量 key、DB key 的当前行为必须被测试锁定。
- [ ] Agent runtime 和 Provider test 使用同一 resolver。

验证:

```bash
cd backend && conda run -n trader pytest tests/unit/app/services/config
cd backend && conda run -n trader pytest tests/unit/app/services/research/agent/provider/test_client.py
cd backend && conda run -n trader pyright
```

验收:

- Provider 新增或修改只需更新 catalog/resolver/tester 明确边界。
- Provider 解析错误不改变 secret redaction 和公开响应字段。

### Task P2.4：分离 `ProviderTester` 与 `ModelClient`

文件:

- 修改 `backend/app/services/config/testing/provider.py`。
- 修改 `backend/app/services/research/agent/provider/client.py`。
- 在现有 provider 测试附近新增测试。

步骤:

- [ ] `ProviderTester` 只负责连接测试和测试响应映射。
- [ ] `ModelClient` 只负责 HTTP、streaming、completion，不再选择 Provider。
- [ ] Provider test、settings save、agent runtime 的 resolved provider 一致。

验证:

```bash
cd backend && conda run -n trader pytest tests/unit/app/services/config
cd backend && conda run -n trader pytest tests/integration/app/routers/config
cd backend && conda run -n trader pytest tests/unit/app/services/research/agent/provider/test_client.py
cd backend && conda run -n trader ruff check app/services/config app/services/research/agent/provider tests/unit/app/services/config
cd backend && conda run -n trader pyright
```

验收:

- `client.py` 不再同时拥有 Provider resolution 和 ModelClient 两类职责。
- settings、testing、agent runtime 的 provider 解析矩阵一致。

### Task P2.5：Phase 2 review gate

- [ ] 检查设置页 route export 和 `configApi` 对外方法名未变化。
- [ ] 检查 Provider、LLM、DataSource、Database 响应字段未删除或改名。
- [ ] 检查 secret redaction 测试通过。
- [ ] 检查 no new dependency。

Review 要求:

- Review 结论为“通过”后才能进入 Phase 3。

## 7. Phase 3：任务状态、Paper、Reports 边界

### Task P3.1：建立任务状态 progress/status 边界

文件:

- 修改 `backend/app/services/analysis/simple/runner.py`。
- 修改 `backend/app/services/analysis/simple/status.py`。
- 在 `backend/app/services/analysis/simple/` 下新增聚焦模块。
- 在现有 analysis status 测试附近新增测试。

步骤:

- [ ] `ProgressGateway` 成为 runner 写进度唯一入口。
- [ ] `TaskStatusRepository` 读取 memory、Redis、PostgreSQL raw snapshots。
- [ ] `TaskStatusAggregator` 负责合并优先级和 degraded 标记。
- [ ] `TaskScopePolicy` 负责 user/admin/scope 判断。
- [ ] 读取失败不得返回伪空列表；expected fallback 必须产生可测试 degraded 结果。

Contract handling:

- 可以新增 optional `degraded?: boolean` 和 `warnings?: string[]` 字段。
- 不删除、不重命名现有字段。
- 前端处理方式：API client type 接受 optional 字段；现有 UI 不新增显式展示，避免 Phase 3 引入用户可见行为变化。后续是否展示 warning 需要单独产品决策。

验证:

```bash
cd backend && conda run -n trader pytest tests/integration/app/routers/analysis
cd backend && conda run -n trader ruff check app/services/analysis/simple tests/integration/app/routers/analysis
cd backend && conda run -n trader pyright
```

验收:

- 任务状态读取能表达 degraded 状态。
- dependency failure 不再伪装成空成功列表。

### Task P3.2：拆出 Paper service/repository

文件:

- 修改 `backend/app/routers/paper.py`。
- 在现有 backend app service 边界下新增 service/repository 模块。
- 在 paper router/service 测试附近新增测试。

步骤:

- [ ] `PaperAccountService` 负责账户创建、迁移、读取。
- [ ] `PaperOrderService` 负责下单、手续费、现金和持仓不变量。
- [ ] `PaperRepository` 负责文档库/PostgreSQL 读写和 expected read fallback。
- [ ] Router 只保留 request parsing、dependency、service call、response mapping。
- [ ] 写路径失败必须失败并映射稳定错误，不能伪成功。

验证:

```bash
cd backend && conda run -n trader pytest tests/integration/app/db/test_paper.py
cd backend && conda run -n trader pytest tests/integration/app/routers
cd backend && conda run -n trader ruff check app/routers/paper.py app/services tests/integration/app/db/test_paper.py
cd backend && conda run -n trader pyright
```

验收:

- 买入现金不足、卖出持仓不足、手续费、均价更新测试通过。
- Router 不再直接承载市场识别、迁移、下单和 fallback 细节。

### Task P3.3：拆出 Reports lookup/scope/list/export 边界

文件:

- 修改 `backend/app/routers/reports.py`。
- 在现有 backend app service 边界下新增 service/policy 模块。
- 在 `backend/tests/integration/app/routers/reports/` 下新增测试。

步骤:

- [ ] `ReportLookupService` 统一 `_id`、`analysis_id`、`task_id` 查询。
- [ ] `ReportScopePolicy` 统一 admin/user scope。
- [ ] `ReportListService` 负责 report/task 合并 read model。
- [ ] `ReportExportService` 负责 markdown/json/html 下载。
- [ ] Router 不返回 `detail=str(e)`，公开错误使用稳定错误映射。

验证:

```bash
cd backend && conda run -n trader pytest tests/integration/app/routers/reports
cd backend && conda run -n trader ruff check app/routers/reports.py app/services tests/integration/app/routers/reports
cd backend && conda run -n trader pyright
```

验收:

- 普通用户不能读/删别人报告。
- 三种 lookup 保持。
- 下载 content-type、文件名、unsupported format 错误稳定。

### Task P3.4：Phase 3 review gate

- [ ] 检查 `degraded` / `warnings` 只作为 optional compatible fields 出现。
- [ ] 检查公开 API 不再返回原始异常文本。
- [ ] 检查 route handler 只做 HTTP 边界职责。
- [ ] 检查 DB read/write、fallback、scope、事务归属明确。

Review 要求:

- Review 结论为“通过”后才能进入 Phase 4。

## 8. Phase 4：横切错误处理和类型治理

### Task P4.1：建立 broad exception 分类表

文件:

- Phase 1-3 已触达的模块。
- 如需临时跟踪表，使用现有文档或 phase notes。

步骤:

- [ ] 对每个 `except Exception` 分类为 expected fallback、boundary translation、unexpected error。
- [ ] 每条 expected fallback 写明触发条件、为什么可继续、调用方如何观察、日志字段。
- [ ] 每条 unexpected error 通过现有错误边界失败，不转成 success。
- [ ] 不做全仓一次性替换。

验证:

```bash
rg -n "except Exception" backend/app/services/research/agent backend/app/services/config backend/app/services/analysis/simple backend/app/routers/paper.py backend/app/routers/reports.py
```

验收:

- 新增代码没有无解释 broad exception。
- 每个保留 broad exception 都位于明确边界并有结构化日志或稳定错误映射。

### Task P4.2：逐模块收紧 fallback 语义

文件:

- `backend/app/routers/config/market.py`
- `backend/app/routers/config/settings.py`
- `backend/app/routers/config/providers.py`
- `backend/app/services/config/provider.py`
- `backend/app/services/analysis/simple/status.py`
- `backend/app/routers/paper.py`
- `backend/app/routers/reports.py`

步骤:

- [ ] 按模块族逐项替换伪成功 fallback。
- [ ] expected fallback 保留现有成功响应字段，并补 `degraded` 或等价可观察语义。
- [ ] unexpected error 使用现有异常映射，不泄露 stack trace、secret 或原始异常文本。

验证:

```bash
cd backend && conda run -n trader pytest tests/integration/app/routers/config
cd backend && conda run -n trader pytest tests/integration/app/routers/analysis
cd backend && conda run -n trader pytest tests/integration/app/routers/reports
cd backend && conda run -n trader pyright
```

验收:

- 所有 fallback 都能在测试中触发并断言。
- 没有公开 500 返回原始异常文本。

### Task P4.3：逐模块收敛 loose typing

文件:

- `backend/app/services/research/agent/stock.py`
- `backend/app/services/analysis/simple/status.py`
- `backend/app/routers/paper.py`
- `backend/app/routers/reports.py`
- `backend/app/services/config/provider.py`
- `frontend/features/agent/event.ts`

步骤:

- [ ] Python raw dict 进入业务层前 narrow 到 Pydantic model、dataclass、TypedDict、Protocol、enum 或 literal。
- [ ] TypeScript raw payload 进入 UI 层前 narrow 到 discriminated union 或 type guard。
- [ ] 删除不必要 `cast` 和 loose optionality；保留的 adapter 边界必须最小化。

验证:

```bash
cd backend && conda run -n trader ruff check app tests
cd backend && conda run -n trader pyright
cd frontend && pnpm type-check
```

验收:

- 新增代码没有 `Any` / `any` escape hatch。
- external payload、event、配置解析、报告/任务 read model 有显式 DTO 或 narrowing 边界。

### Task P4.4：最终全量 verification 和 review

步骤:

- [ ] 运行 backend gate：

```bash
cd backend && conda run -n trader ruff format --check .
cd backend && conda run -n trader ruff check .
cd backend && conda run -n trader pyright
cd backend && conda run -n trader pytest
```

- [ ] 运行 frontend gate：

```bash
cd frontend && pnpm lint
cd frontend && pnpm type-check
cd frontend && pnpm test
cd frontend && pnpm build
```

- [ ] 检查 diff 范围：

```bash
git diff --stat
git diff --check
```

验收:

- 所有 phase 的聚焦验证门禁通过。
- 全量验证门禁通过，或明确记录不能运行的环境原因。
- 最终报告包含变更文件、已完成的简化、已执行验证、未执行验证和剩余风险。

## 9. Spec 覆盖矩阵

| Spec 要求 | 计划覆盖 |
| --- | --- |
| Phase 0 行为锁定 | P0.1-P0.5 |
| 研究 Agent session/stream/polling/UI mode | P0.2、P1.1-P1.4 |
| `frontend/features/agent/event.ts` typed event boundary | P1.5、P4.3 |
| `stock.py` command/model/workflow/event/usage 拆分 | P0.3、P1.6-P1.7 |
| 设置页拆分 | P2.1-P2.2 |
| Provider catalog/resolver/tester/model client | P2.3-P2.4 |
| 任务状态 progress/status/repository/aggregator/scope | P0.4、P3.1 |
| Paper account/order/repository | P0.4、P3.2 |
| Reports lookup/scope/list/export | P0.4、P3.3 |
| `degraded` / `warnings` 兼容字段处理 | P3.1、P3.4 |
| broad exception 分类和 fallback 可观察 | P4.1-P4.2 |
| loose typing 收敛 | P1.5、P4.3 |
| 每阶段 review gate | P0.5、P1.8、P2.5、P3.4、P4.4 |
| 后端 verification | P0-P4 verification commands |
| 前端 verification | P0-P4 verification commands |

## 10. 计划 Review

### 发现

严重：未发现。

高：未发现。原 spec 的最大风险是范围过宽，本计划已拆成 Phase 0-4，并设置 phase gate，避免单次大改。

中：Phase 3 的 `degraded` / `warnings` 是兼容字段但仍可能扩散到前端展示语义。

- 缓解措施：本计划明确 Phase 3 只更新 API client type 接受 optional 字段，现有 UI 不新增显式展示；是否展示 warning 作为后续产品决策，不混入本次重构。

低：Phase 4 涉及多个模块族，容易被误执行成全仓 broad exception 清理。

- 缓解措施：本计划要求只治理 Phase 1-3 已触达模块和 spec 明确列出的热点，不做全仓一次性替换。

### Review 结论

通过，作为主任务规划使用。

本计划作为完整主任务规划符合 spec；但不批准作为单次实现批次执行。每个 phase 仍必须独立执行，先补测试，再实施，再通过 review gate 后进入下一阶段。

### 完整性 Checklist

- [x] 覆盖 spec 中所有 Phase 0-4。
- [x] 覆盖所有 spec 明确点名的核心文件和风险边界。
- [x] 每个 phase 都有具体任务、文件范围、验证命令和验收标准。
- [x] Phase 0 测试锁定作为强依赖。
- [x] Phase 3 兼容字段和前端处理方式已明确。
- [x] Provider resolver 的 settings、testing、agent runtime 矩阵已覆盖。
- [x] broad exception 和 loose typing 治理已拆成可 review 的任务。
- [x] 没有要求 commit/push。
- [x] 没有引入新依赖。
