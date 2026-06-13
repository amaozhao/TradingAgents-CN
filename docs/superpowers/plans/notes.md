# Refactor Phase Notes

## Phase 0 Scan

Date: 2026-06-13

### Commands Run

```bash
rg -n "research-agent|stock_analysis|batch_stock_analysis|report|paper|provider|completion|status" frontend/tests backend/tests
rg -n "except Exception|Record<string, unknown>|Any|dict\\[" backend/app frontend/features
rg --files frontend/tests backend/tests | rg '(research-agent|stock|report|paper|provider|completion|status|config)'
find frontend/tests backend/tests -maxdepth 6 -type d | rg '(research-agent|research/agent|routers/reports|routers/analysis|paper|config|provider)'
```

### Existing Coverage Confirmed

- Research Agent page has integration coverage for persisted session switching, stale response protection, running attempt restoration, SSE completion recovery, and completed assistant message recovery in `frontend/tests/integration/components/research-agent-page.test.tsx`.
- Stock frontend payload and event behavior have integration coverage in `frontend/tests/integration/components/stock.test.tsx`, including payload construction, model defaults, queued stock tool running state, and initial stock workflow tool state.
- Reports user isolation has backend integration coverage in `backend/tests/integration/app/routers/reports/test_user_isolation.py`.
- Analysis status user isolation and completion status have backend integration coverage under `backend/tests/integration/app/routers/analysis/`.
- Paper database query shape has coverage in `backend/tests/integration/app/db/test_paper.py`.

### Phase 0 Gaps

- Research Agent still needs a focused test that asserts an active stream unsubscribe function is called when switching to another session.
- Research Agent still needs a focused test that a terminal event stops completion polling for the finished attempt.
- Research Agent stock and batch config mutual exclusion is covered indirectly by workflow tests, but needs an explicit assertion.
- Backend stock workflow needs unit coverage for raw legacy payload normalization into `AnalysisParameters`-equivalent values.
- Backend stock workflow needs unit coverage for workflow node event to stage/progress/title mapping.
- Paper trading needs service/router-level buy/sell invariants for insufficient cash, insufficient holdings, fee handling, and average price update. Existing DB query tests do not lock these behaviors.
- Analysis status needs a dependency-failure regression that proves read failures are not silently converted into an empty success list before Phase 3 changes that behavior.

### Risk Hotspots Confirmed

- `backend/app/services/research/agent/stock.py` currently contains command parsing, model resolution, workflow execution, event mapping, and usage recording.
- `frontend/features/agent/event.ts` and report frontend APIs still use broad `Record<string, unknown>` payloads that must be narrowed before Phase 1 and Phase 4 are considered complete.
- Broad `except Exception` is present across analysis status, paper, reports, config, provider, and several database adapter boundaries; Phase 4 must handle only the modules touched by Phase 1-3 plus spec-listed hotspots.

### Phase 0 Tests Added

- `frontend/tests/integration/components/research-agent-page.test.tsx`: verifies active stream unsubscribe when switching persisted sessions and verifies terminal completion clears polling.
- `frontend/tests/integration/components/stock.test.tsx`: verifies single-stock and batch config cards are mutually exclusive.
- `backend/tests/unit/app/services/research/agent/test_stock.py`: locks legacy payload normalization and stock workflow node-to-stage event mapping.
- `backend/tests/integration/app/routers/test_paper.py`: locks paper buy cash/fee checks, weighted average cost update, and sell insufficient holdings behavior.
- `backend/tests/integration/app/routers/analysis/test_history.py`: adds a strict xfail redline for dependency failure being silently converted into an empty task list; Phase 3 must remove the xfail by fixing the behavior.
- `backend/tests/unit/app/services/research/agent/tool/test_calls.py` and `backend/tests/unit/app/services/research/agent/tool/test_registry.py`: isolate stock model resolution so unit tests do not connect to real PostgreSQL.

### Phase 0 Verification

```bash
cd frontend && pnpm install --frozen-lockfile
cd frontend && pnpm vitest run tests/integration/components/research-agent-page.test.tsx
cd frontend && pnpm vitest run tests/integration/components/stock.test.tsx
cd frontend && pnpm vitest run tests/integration/components/research-agent-page.test.tsx tests/integration/components/stock.test.tsx
cd frontend && pnpm type-check
cd backend && conda run -n trader pytest tests/unit/app/services/research/agent/test_stock.py
cd backend && conda run -n trader pytest tests/unit/app/services/research/agent
cd backend && conda run -n trader pytest tests/integration/app/routers/reports tests/integration/app/routers/analysis tests/integration/app/routers/test_paper.py
cd backend && conda run -n trader ruff check tests/unit/app/services/research/agent tests/integration/app/routers/test_paper.py tests/integration/app/routers/analysis/test_history.py
cd backend && conda run -n trader pyright
git diff --check
```

Results:

- Frontend target tests: 49 passed.
- Frontend type-check: passed.
- Backend research-agent unit directory: 108 passed, 1 deselected.
- Backend reports/analysis/paper integration tests: 32 passed, 1 xfailed, 3 warnings.
- Backend scoped ruff: passed.
- Backend pyright: 0 errors, 0 warnings, 0 informations.
- Diff whitespace check: passed.

## Phase 1 Progress

### Completed Slices

- Added `backend/app/services/research/agent/command.py` for stock command parsing, symbol/market normalization, analyst/depth normalization, and `AnalysisParameters` construction.
- Added `backend/app/services/research/agent/emitter.py` for stock workflow stage emission, node-to-stage mapping, and progress/title mapping.
- Added `backend/app/services/research/agent/usage.py` for token counting, pricing lookup, and usage record writes.
- Updated `backend/app/services/research/agent/stock.py` to delegate command parsing, event emission, and usage recording to the new boundaries while preserving existing tool contract.
- Added `frontend/features/research-agent/mode.ts` for the Research Agent UI mode reducer.
- Updated `frontend/features/research-agent/query.ts` and `frontend/features/research-agent/research-agent-page.tsx` to use reducer actions for stock/batch config mutual exclusion and composer mode.
- Added `frontend/tests/unit/features/research-agent/mode.test.ts` for reducer behavior.

### Phase 1 Verification So Far

```bash
cd backend && conda run -n trader ruff check app/services/research/agent tests/unit/app/services/research/agent
cd backend && conda run -n trader pytest tests/unit/app/services/research/agent
cd backend && conda run -n trader pyright
cd frontend && pnpm exec eslint features/research-agent/research-agent-page.tsx features/research-agent/query.ts features/research-agent/mode.ts
cd frontend && pnpm vitest run tests/unit/features/research-agent/mode.test.ts tests/integration/components/research-agent-page.test.tsx tests/integration/components/stock.test.tsx
cd frontend && pnpm type-check
```

Results:

- Backend research-agent unit directory: 108 passed, 1 deselected.
- Backend scoped ruff for research-agent source/tests: passed.
- Backend pyright after backend extraction: 0 errors, 0 warnings, 0 informations.
- Frontend reducer + target integration tests: 51 passed.
- Frontend type-check: passed.

### Remaining Phase 1 Work

- No remaining required Phase 1 work.

### Phase 1 Completion Update

- Added `frontend/features/research-agent/session.ts` for session list refresh, active session identity, rename/delete/create, and stale load invalidation.
- Added `frontend/features/research-agent/stream.ts` for SSE subscription ownership, last event ID tracking, and streaming answer placeholder tracking.
- Added `frontend/features/research-agent/attempt.ts` for completion polling, run-finished state, and local running session tracking.
- Updated `frontend/features/research-agent/research-agent-page.tsx` so the page no longer owns session list state, SSE refs, completion polling refs, run-finished refs, or local running session refs directly.
- Narrowed `frontend/features/agent/event.ts` with `AgentEventData`, record guards, and stock/batch payload guards so event parsing has one explicit boundary instead of repeated ad hoc casts.
- Deferred a separate `StockWorkflowRunner` extraction because `stock.py` is already split under 800 lines and an additional runner layer would be a shallow wrapper at this point.

### Phase 1 Completion Verification

```bash
cd frontend && pnpm exec eslint features/research-agent/research-agent-page.tsx features/research-agent/query.ts features/research-agent/mode.ts features/research-agent/session.ts features/research-agent/stream.ts features/research-agent/attempt.ts
cd frontend && pnpm exec eslint features/agent/event.ts features/research-agent/research-agent-page.tsx features/research-agent/session.ts features/research-agent/stream.ts features/research-agent/attempt.ts
cd frontend && pnpm type-check
cd frontend && pnpm vitest run tests/unit/features/research-agent/mode.test.ts tests/integration/components/research-agent-page.test.tsx tests/integration/components/stock.test.tsx
cd backend && conda run -n trader ruff check app/services/research/agent tests/unit/app/services/research/agent
cd backend && conda run -n trader pytest tests/unit/app/services/research/agent
```

Results:

- Frontend scoped ESLint: passed.
- Frontend type-check: passed.
- Frontend reducer + target integration tests: 51 passed.
- Backend scoped ruff for research-agent source/tests: passed.
- Backend research-agent unit directory: 108 passed, 1 deselected.

## Phase 2 Progress

### Completed Slices

- Added `frontend/features/settings/personal.tsx` and moved `SettingsIndexPage` plus personal settings tab helpers out of `settings-pages.tsx`.
- Added `frontend/features/settings/config.ts` for config-page query setup, config invalidation, and shared config action mutation.
- Updated `frontend/features/settings/settings-pages.tsx` to re-export `SettingsIndexPage` and consume config query/action hooks while preserving route imports.
- Added `backend/app/services/research/agent/provider/resolver.py` with `ProviderCatalog`, `ProviderResolver`, typed `AgentModelConfig`, and resolver diagnostics.
- Updated `backend/app/services/research/agent/provider/client.py` so `OpenAICompatibleModelClient` owns HTTP/streaming/completion only and delegates provider/model resolution.
- Updated `backend/app/services/config/testing/provider.py` so provider API testing uses the same catalog rules for env key and base URL resolution.
- Added `backend/app/services/config/providers.py` and moved the built-in LLM provider catalog out of `backend/app/services/config/provider.py`; `provider.py` is now below the backend 800-line limit.
- Added resolver/provider testing coverage for alias base URLs, MiniMax Token Plan URL validation, missing-key resolution, config provider env-key precedence, and config provider base URL reuse.

### Phase 2 Verification

```bash
cd frontend && pnpm exec eslint features/settings/settings-pages.tsx features/settings/personal.tsx features/settings/config.ts
cd frontend && pnpm type-check
cd frontend && pnpm vitest run tests/integration/components/settings-index-page.test.tsx tests/integration/components/config-management-page.test.tsx
cd backend && conda run -n trader pytest tests/unit/app/services/config tests/unit/app/services/research/agent/provider
cd backend && conda run -n trader ruff check app/services/config app/services/research/agent/provider tests/unit/app/services/config tests/unit/app/services/research/agent/provider
cd backend && conda run -n trader pyright
```

Results:

- Frontend settings scoped ESLint: passed.
- Frontend type-check: passed.
- Frontend settings/config integration tests: 12 passed.
- Backend config + provider unit tests: 13 passed.
- Backend scoped ruff for config/provider source/tests: passed.
- Backend pyright: 0 errors, 0 warnings, 0 informations.

## Phase 3 Progress

### Completed Slices

- Added `backend/app/services/analysis/simple/tasks.py` for compatible degraded task-list responses.
- Updated `backend/app/services/analysis/simple/status.py` so memory/PostgreSQL task-list dependency failures no longer become silent empty successes; callers now receive optional `degraded` and `warnings` fields.
- Removed the strict xfail from `backend/tests/integration/app/routers/analysis/test_history.py` and asserted the degraded response contract.
- Added `backend/app/services/paper.py` with `PaperOrderService` for currency selection, cash normalization, buying-power checks, weighted average cost, T+1 availability, and sell proceeds/PnL totals.
- Updated `backend/app/routers/paper.py` to delegate order invariants to `PaperOrderService` and use timezone-aware timestamps.
- Added `backend/app/services/reports.py` with `ReportLookupService`, `ReportScopePolicy`, and `ReportExportService`.
- Updated `backend/app/routers/reports.py` to delegate report lookup/scope/export rules and replace raw public 500 exception details with stable error messages.

### Phase 3 Verification

```bash
cd backend && conda run -n trader pytest tests/integration/app/routers/analysis tests/integration/app/routers/test_paper.py tests/integration/app/routers/reports
cd backend && conda run -n trader ruff check app/services/analysis/simple app/routers/paper.py app/services/paper.py app/routers/reports.py app/services/reports.py tests/integration/app/routers/analysis tests/integration/app/routers/test_paper.py tests/integration/app/routers/reports
cd backend && conda run -n trader pyright
```

Results:

- Backend analysis/paper/reports integration tests: 33 passed.
- Backend scoped ruff for Phase 3 source/tests: passed.
- Backend pyright: 0 errors, 0 warnings, 0 informations.

## Phase 4 Progress

### Broad Exception Classification

- Research agent provider/client:
  - `client.py` transport cleanup and provider resolver fallbacks are boundary translation. HTTP/stream calls still raise typed runtime errors to the tool boundary; close failures and optional metadata probes are logged or ignored only after the main result is already decided.
  - `resolver.py` provider metadata and user preference reads are expected fallback boundaries. Trigger: missing/invalid user config, provider catalog lookup miss, or persisted provider record read failure. Observation: resolver diagnostics and `AgentModelConfigurationError` remain the caller-visible contract.
- Config provider/testing:
  - `provider.py` and `testing/provider.py` retain broad exceptions at legacy config repository and external provider API boundaries. Trigger: missing provider row, malformed stored provider data, unavailable HTTP provider test, or optional env-derived defaults. Observation: returned provider test result includes `success`/`message`; internal service failures are logged and no secret values are returned.
  - `routers/config/{market,settings,providers}.py` now keeps expected audit-log failures as ignored side effects, but public 500 responses use stable messages instead of raw exception text. `HTTPException` validation and authorization errors pass through unchanged.
- Analysis task status:
  - `list_user_tasks` and `list_all_tasks` dependency failures return degraded task rows with `degraded=True` and warning codes instead of silent empty success.
  - zombie task query/cleanup failures now propagate to the admin route error boundary instead of returning empty or nested false-success payloads. Admin routes return stable 500 details.
- Paper trading:
  - Postgres read fallback remains expected fallback to hot document reads. Trigger: optional read replica path unavailable. Observation: warning logs include collection/action context; write path still raises on order invariant failure.
  - `PaperOrderError` remains a user-facing validation error for insufficient buying power and sell availability; this is not an unexpected server exception.
- Reports:
  - report lookup/export exceptions are boundary translation. Lookup/read failures become stable HTTP errors; markdown/json export is pure formatting and does not hide persistence failures. Optional report date conversion uses best-effort fallback to preserve historical report payload compatibility.

### Tightened Fallbacks And Typing

- Replaced config route raw public exception details with stable messages while preserving status codes and success payloads.
- Removed direct `print`/`traceback.print_exc()` from provider model fetch failure; it now uses structured logger context.
- Replaced `datetime.utcnow()` in analysis task status with a local UTC helper that preserves the existing naive-UTC persistence shape.
- Kept `frontend/features/agent/event.ts` as the TypeScript event narrowing boundary and avoided adding `as any` or `Record<string, any>`.

### Phase 4 Review Notes

- Scope stayed inside Phase 1-3 touched boundaries plus the config routes explicitly named by P4.2.
- Remaining broad exceptions are either side-effect audit logging, optional fallback reads, or HTTP boundary translation; none of the newly touched public 500 paths returns raw `str(exc)` for unexpected server failures.
- The only remaining `detail=str(...)` in touched routes is `PaperOrderError`, a domain validation error intentionally returned as a 400 response.

### Final Verification

```bash
cd backend && conda run -n trader ruff format --check .
cd backend && git diff --name-only -- backend | xargs conda run -n trader ruff format --check
cd backend && conda run -n trader ruff check .
cd backend && conda run -n trader pyright
cd backend && conda run -n trader pytest
cd frontend && pnpm lint
cd frontend && pnpm type-check
cd frontend && pnpm test
cd frontend && pnpm build
git diff --check
```

Results:

- Backend full `ruff format --check .`: failed on pre-existing repository baseline formatting drift (621 files would be reformatted). Touched backend files were formatted separately and passed scoped format check.
- Backend full `ruff check .`: passed.
- Backend pyright: 0 errors, 0 warnings, 0 informations.
- Backend full pytest: 593 passed, 7 deselected.
- Frontend lint: passed.
- Frontend type-check: passed.
- Frontend full Vitest: 149 passed across 31 files.
- Frontend build: passed.
- `git diff --check`: passed.
