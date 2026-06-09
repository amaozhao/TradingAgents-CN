# Vibe Research Agent Integration Plan

## Executive Summary

This document plans how to integrate the global research capabilities from
`/home/amaozhao/workspace/Vibe-Trading` into
`/home/amaozhao/workspace/TradingAgents-CN`.

The target system is **TradingAgents-CN as the primary product**, with Vibe used
as the capability source for:

- global research Agent conversations;
- Alpha Zoo factor registry, factor analysis, benchmark, and comparison;
- correlation and matrix-style research views;
- session event streaming and Markdown research rendering patterns.

The migration must not replace TradingAgents-CN's existing single-stock
TradingAgents workflow. Instead, it adds a global orchestration layer above the
existing system:

```text
Global Research Agent
  -> sector/universe discovery
  -> screening
  -> Alpha Zoo factor tests
  -> correlation matrix
  -> single/batch TradingAgents analysis
  -> report synthesis
```

This creates one system that can analyze sectors, groups of stocks, individual
stocks, factors, correlations, and final recommendations while preserving
TradingAgents-CN's existing data, user, task, report, and configuration model.

## Non-Negotiable Constraints

### Product Ownership

- TradingAgents-CN is the destination and product shell.
- Vibe-Trading remains a source repository. It should not run as a parallel
  production dependency.
- The final user entry points should be in TradingAgents-CN:
  - `/agent`
  - `/alpha-zoo`
  - `/correlation`
  - existing `/screening`
  - existing `/analysis/single`
  - existing `/analysis/batch`
  - existing `/tasks`
  - existing `/reports`

### Runtime And Branch Safety

- Start from a clean TradingAgents-CN integration branch or worktree.
- The current `dev` checkout has unrelated local state. Do not mix migration
  changes with existing local deletions, config edits, generated data folders,
  or frontend-vue lockfile changes.
- Backend verification must use the real TradingAgents-CN environment:
  `conda run -n trader ...`.
- Do not use port `8000`; it is reserved for another backend service.

### User Isolation And Permissions

This migration must be designed as multi-user from the first commit.

- Every research session, task, artifact, Alpha bench result, correlation result,
  uploaded file, and report must carry `user_id`.
- Every read, stream, cancel, retry, download, and delete endpoint must enforce
  ownership server-side.
- SSE and WebSocket streams must verify that the requested `session_id`,
  `task_id`, or `batch_id` belongs to the authenticated user.
- Agent tools must receive an execution context containing `user_id`, role,
  session id, and permission set.
- The Agent must never receive tools that can read or modify global system
  configuration unless the user has the required admin permission.
- User API keys must stay private and redacted. Agent tools must not expose
  plaintext provider keys.

### Security And Tool Policy

Vibe includes powerful local tools. Only research-safe tools should migrate to
the web product.

Allowed for normal users:

- market data read tools;
- screening tools;
- sector/universe tools;
- single-stock analysis tools;
- batch analysis tools;
- Alpha list/detail/bench/compare tools;
- factor analysis tools;
- correlation matrix tools;
- report read/write tools scoped to the current user;
- session memory scoped to the current user.

Blocked by default:

- shell/bash execution;
- arbitrary file read/write/edit;
- system configuration mutation;
- raw database query tools;
- local path traversal tools;
- unrestricted URL fetchers that can reach internal services;
- live trading or real-order tools;
- tools that read global logs or other users' data.

Admin-only:

- model/provider catalog management;
- data-source initialization and sync control;
- system logs and operations;
- queue/system-wide diagnostics;
- user management;
- admin audit views.

## Current Capability Map

### TradingAgents-CN Capabilities

TradingAgents-CN already has strong product and data infrastructure:

- FastAPI backend under `backend/app`.
- Next.js frontend under `frontend`.
- Authentication and current-user dependency through `get_current_user`.
- Redis-backed task queue in `backend/app/services/queue/service.py`.
- Single-stock analysis submission at `/api/analysis/single`.
- Batch analysis and queue endpoints under `/api/analysis`.
- Task progress streaming under `/api/stream/tasks/{task_id}`.
- Screening APIs and UI under `/api/screening` and `/screening`.
- Reports APIs and pages under `/api/reports` and `/reports`.
- A-share, HK, US, Tushare, AkShare, BaoStock, historical, news, social, and
  financial data modules.
- TradingAgentsGraph under `backend/trader/graph/trading`.
- Multi-agent single-stock workflow:
  - market analyst;
  - social/sentiment analyst;
  - news analyst;
  - fundamentals analyst;
  - bull researcher;
  - bear researcher;
  - research manager;
  - trader;
  - risk analysts;
  - portfolio/risk manager.
- LLM configuration through `/api/config/llm`, provider catalog, provider
  aliases, and model config services.

TradingAgents-CN does **not** currently have a global free-form research Agent
that can combine sector analysis, screening, Alpha factors, correlation,
TradingAgents reports, and final synthesis in one conversation.

Important current-code constraints found during review:

- The Redis queue service is stock-symbol centric. It records `symbol`,
  `params`, `user`, and status fields, and its concurrency checks are built for
  existing analysis tasks. It should not be reused unchanged for Alpha,
  correlation, or free-form research jobs.
- Existing queue stream routes perform useful ownership checks before
  subscribing, but research streams still need persistent event replay because
  browser refresh must not lose generated content.
- Existing report APIs and some task-status fallback paths read by report id or
  task id without a required user filter in the inspected document-store paths.
  These are Phase 0 blockers before adding a broader Agent surface.
- Existing LLM/provider config endpoints are authenticated, but mutating global
  provider/model settings need explicit admin gating before they are exposed as
  Agent-operable or settings-driven controls.
- Existing screening APIs return global market scans and do not currently expose
  a persisted, user-owned screening result id suitable for later Alpha/matrix
  jobs. Persist that artifact first or pass explicit symbol lists.

### Vibe-Trading Capabilities

Vibe-Trading provides the missing global research layer:

- ReAct-style `AgentLoop` with:
  - streaming model output;
  - tool calls;
  - parallel read-only tool execution;
  - context compaction;
  - length-continuation handling;
  - session event emission;
  - trace and progress events.
- `ToolRegistry` with auto-discovered tools.
- Finance research tools such as:
  - Alpha Zoo;
  - Alpha bench;
  - Alpha compare;
  - factor analysis;
  - backtest;
  - options pricing;
  - document reader;
  - session search;
  - memory;
  - web/search tools;
  - shadow account;
  - trade journal;
  - swarm.
- Alpha factor library:
  - Alpha101;
  - GTJA191;
  - Qlib158;
  - metadata registry;
  - static metadata validation;
  - factor compute;
  - IC/IR analysis;
  - layered NAV;
  - benchmark classification;
  - factor comparison.
- Alpha Zoo HTTP routes:
  - list;
  - detail;
  - bench;
  - bench stream;
  - compare;
  - compare stream.
- Correlation matrix page and ECharts heatmap.
- Agent conversation UI with:
  - Markdown rendering;
  - thinking timeline;
  - tool progress;
  - streaming status;
  - session persistence;
  - sidebar session list.

### Overlap And Migration Decision

| Domain | TradingAgents-CN | Vibe-Trading | Decision |
| --- | --- | --- | --- |
| Product shell | Strong | Smaller Vite app | Use TradingAgents-CN |
| Authentication | Present | Local/API auth | Use TradingAgents-CN |
| User isolation | Partial, task queue has user field | Mostly local/session scoped | Strengthen in TradingAgents-CN |
| LLM config | Strong config services | Provider registry and adapters | Use TradingAgents-CN; port adapters only if needed |
| Single-stock analysis | Strong TradingAgentsGraph | Generic tool-based analysis | Keep TradingAgentsGraph |
| Global research Agent | Missing | Strong ReAct loop | Port concept and selected code |
| Agent tools | LangChain tools tied to graph | Generic registry | Build new TradingAgents-CN research tool registry |
| Alpha factors | Missing | Strong Alpha Zoo | Port factor library and math |
| Data loading | Strong A-share DB/services | Lightweight loaders | Replace Vibe loaders with TradingAgents-CN data panel loader |
| Task queue | Redis/Postgres task model | In-memory Alpha jobs | Use TradingAgents-CN task model |
| Reports | Strong report system | Run/session artifacts | Use TradingAgents-CN reports |
| SSE | Task progress SSE | Session event bus with replay ideas | Merge patterns into TradingAgents-CN |
| Frontend | Next.js | Vite React | Rebuild pages in Next.js |
| Live trading | Paper trading only | Live mandate/order guard | Exclude from first migration |

## Target Architecture

### High-Level Modules

Add these modules to TradingAgents-CN:

```text
backend/app/routers/research_agent.py
backend/app/routers/alpha_zoo.py
backend/app/routers/research_matrix.py

backend/app/services/research_agent/
  __init__.py
  context.py
  loop.py
  models.py
  permissions.py
  registry.py
  sessions.py
  events.py
  artifacts.py
  tools/
    __init__.py
    alpha.py
    analysis.py
    correlation.py
    market_data.py
    reports.py
    screening.py
    sector.py

backend/app/services/alpha_zoo/
  __init__.py
  jobs.py
  service.py
  schemas.py

backend/trader/factors/
  __init__.py
  base.py
  registry.py
  factor_analysis_core.py
  bench_runner.py
  compare_runner.py
  panel_loader.py
  zoo/
    alpha101/
    gtja191/
    qlib158/

frontend/app/agent/page.tsx
frontend/app/alpha-zoo/page.tsx
frontend/app/correlation/page.tsx

frontend/features/research-agent/
frontend/features/alpha-zoo/
frontend/features/research-matrix/
frontend/libs/api/research-agent.ts
frontend/libs/api/alpha-zoo.ts
frontend/libs/api/research-matrix.ts
```

### Global Research Flow

For a request such as "分析 A 股储能板块，给出推荐个股":

```text
1. User opens /agent and creates a research session.
2. Frontend POSTs a message to /api/research-agent/sessions/{id}/messages.
3. Backend starts a user-scoped research task.
4. GlobalResearchAgent receives:
   - user_id;
   - session_id;
   - role and permissions;
   - selected LLM config;
   - user-visible tool registry.
5. Agent calls tools:
   - sector_universe -> get storage-sector universe;
   - screening -> filter fundamentals/liquidity/valuation;
   - correlation -> compute matrix for candidate universe;
   - alpha_bench -> test factors on the selected universe;
   - single_stock_analysis -> enqueue TradingAgentsGraph tasks;
   - report_write -> persist final research report.
6. Events stream to /api/research-agent/sessions/{id}/events.
7. Final report is saved under the current user's reports/artifacts.
8. User can inspect linked factor bench, correlation matrix, and individual
   stock reports.
```

### Relationship To TradingAgentsGraph

TradingAgentsGraph remains the canonical single-stock analysis engine.

The global Agent must call TradingAgentsGraph through a narrow service/tool:

```text
Research Agent Tool: single_stock_analysis
  input:
    symbol
    market
    analysis_depth
    quick_model
    deep_model
  behavior:
    create analysis task for current user
    enqueue task through QueueService
    return task_id and report/result links
```

The global Agent should not import analyst nodes directly or reimplement the
TradingAgentsGraph.

## User Isolation And Permission Model

### Principal Model

Introduce a research execution context:

```python
class ResearchPrincipal:
    user_id: str
    role: str
    permissions: set[str]
    session_id: str | None
```

The context is created from `get_current_user` and passed into every service,
tool, stream, and job.

### Resource Ownership

Every private research resource must include ownership:

```text
research_sessions.user_id
research_messages.user_id
research_tasks.user_id
research_artifacts.user_id
alpha_bench_jobs.user_id
alpha_compare_jobs.user_id
correlation_jobs.user_id
uploaded_files.user_id
analysis_tasks.user_id or user
analysis_reports.user_id
```

Existing TradingAgents-CN Redis queue records use the field name `user`; new
research tables should use `user_id`. Service adapters must normalize both
names and never compare a task/report without resolving the owner field first.
The current document-style `analysis_reports` writer should also be corrected to
persist `user_id`; relying on the related `analysis_tasks` document for ownership
as a fallback makes report list/detail/download filtering fragile.

Public resources:

- factor definitions;
- factor metadata;
- provider model catalog without private keys;
- public market metadata;
- public stock basics when no user-specific artifact is attached.

Private resources:

- research prompts;
- model outputs;
- tool traces;
- Alpha bench results;
- correlation matrices;
- selected universes saved by users;
- generated reports;
- user uploaded files;
- user model keys;
- personal favorites and tags.

### Required API Checks

Every endpoint must follow this pattern:

```text
resource = service.get(resource_id)
if not resource or resource.user_id != current_user.id:
    raise 404
```

Return `404`, not `403`, for user-private resources to avoid leaking existence.

Admin endpoints may use `403` when the resource is system-level but the action
requires an admin permission.

### Current Gap To Address

Some existing TradingAgents-CN paths already check ownership, for example queue
batch reads, queue cancel, and queue task SSE preflight checks. The migration
cannot treat this as complete coverage. The current code review found concrete
gaps that must be fixed before the global Agent is enabled:

- `backend/app/routers/reports.py` list, detail, content, download, and delete
  paths must filter by `user_id` or require an admin permission for system-level
  report access.
- `backend/app/services/analysis/simple/reports.py` must persist `user_id` when
  saving document-style `analysis_reports`, not only `task_id`.
- `backend/app/routers/analysis/single.py` task-status recovery must not return
  memory, task, or report data found by `task_id` until ownership is verified.
- `backend/app/routers/analysis/setup.py` read helpers should accept `user_id`
  or return only enough data for a caller to perform a mandatory owner check.
- `backend/app/services/analysis/simple/status.py` should either accept
  `user_id` for `get_task_status` or expose a companion owner lookup that
  routers must call before returning a result.
- `backend/app/routers/config/llm.py` and
  `backend/app/routers/config/providers.py` mutating routes should require an
  admin permission when changing global providers, defaults, aliases, or model
  entries.
- Screening result ids are not currently persisted as user-owned artifacts; any
  Alpha or matrix API that accepts `screening_result_id` must first add that
  storage layer.

The migration should include regression tests where user A cannot:

- get user B's research session;
- subscribe to user B's research SSE stream;
- cancel user B's research task;
- read user B's Alpha bench result;
- read user B's correlation result;
- fetch user B's report by task id;
- download user B's generated artifact.
- change global LLM/provider configuration without admin permission.

### Tool-Level Permissions

Define tool permissions in code, not only in UI:

```text
research.market_data.read
research.screening.run
research.alpha.read
research.alpha.run
research.correlation.run
research.analysis.single
research.analysis.batch
research.report.read
research.report.write
admin.config.llm.write
admin.queue.inspect
admin.system.logs
```

Tool registry filtering must happen server-side:

```text
available_tools = registry.for_principal(principal)
```

The Agent prompt should only see tools already filtered for that principal.

## Data Model

### Research Sessions

Use persistent sessions instead of Vibe's local-only session store.

```text
research_sessions
  session_id: string primary key
  user_id: string indexed
  title: string
  status: active | archived | deleted
  created_at
  updated_at
  last_message_at
```

### Research Messages

```text
research_messages
  message_id: string primary key
  session_id: string indexed
  user_id: string indexed
  role: user | assistant | tool | system
  content: text
  tool_name: string nullable
  tool_call_id: string nullable
  metadata: json
  created_at
```

### Research Tasks

```text
research_tasks
  task_id: string primary key
  session_id: string indexed
  user_id: string indexed
  status: queued | running | completed | failed | cancelled
  current_step: string
  progress: number
  error_message: string nullable
  created_at
  started_at
  completed_at
```

### Research Events

For replayable streams, persist lightweight event envelopes:

```text
research_events
  event_id: monotonically increasing string or integer
  session_id: string indexed
  task_id: string indexed nullable
  user_id: string indexed
  event_type: string
  payload: json
  created_at
```

This allows Last-Event-ID resume and avoids losing output when the browser
refreshes.

### Research Artifacts

```text
research_artifacts
  artifact_id: string primary key
  user_id: string indexed
  session_id: string indexed nullable
  task_id: string indexed nullable
  type: report | alpha_bench | alpha_compare | correlation_matrix | universe | file
  title: string
  payload: json
  storage_path: string nullable
  visibility: private | workspace | admin_audit | system
  created_at
  updated_at
```

Alpha bench and correlation results should be artifacts linked to the session
and task that produced them.

## Backend Migration Plan

### Phase 0: Safety, Isolation, And Baseline Audit

Goal: create the migration foundation without changing product behavior.

Tasks:

1. Create an integration branch or clean worktree in TradingAgents-CN.
2. Fix report ownership before adding new research report surfaces:
   - make document-style report writes include `user_id`;
   - filter report list/detail/content/download/delete by current user;
   - allow cross-user report access only through explicit admin permissions.
3. Fix task-status recovery before exposing more long-running jobs:
   - require user ownership when reading task state from memory;
   - require user ownership when recovering task/report state by `task_id`;
   - normalize `user` and `user_id` in shared status helpers.
4. Add or strengthen regression tests for existing task/report ownership.
5. Add admin checks for global LLM/provider mutation routes.
6. Define the research job model before moving Alpha/correlation jobs:
   - either add a dedicated `research_jobs` queue;
   - or extend the current queue with `task_type`, `resource_id`, optional
     `symbol`, and typed payload validation.
7. Persist user-owned screening run artifacts if downstream APIs will accept
   `screening_result_id`; otherwise downstream APIs must accept explicit
   symbols only.
8. Define `ResearchPrincipal` and permission constants.
9. Define a server-side tool permission model.
10. Confirm LLM config uses `/api/config/llm` for runnable model config and
   keeps model catalog metadata separate.
11. Confirm MiniMax token-plan works through current TradingAgents-CN provider
   path; if it fails, port Vibe's dedicated adapter.

Exit criteria:

- Existing single/batch analysis still works.
- User A cannot read, download, delete, or stream user B's existing
  tasks/reports through normal or fallback paths.
- Non-admin users cannot mutate global provider/model/default LLM config.
- The selected job queue design supports non-symbol research jobs without
  overloading the existing single-stock task schema.
- No Vibe code has been imported yet.

### Phase 1: Global Research Session And Event Bus

Goal: add the shell needed for a global Agent conversation.

Backend:

- Add `research_agent` service package.
- Add session CRUD.
- Add message append/list APIs.
- Add user-scoped event persistence.
- Add SSE stream with:
  - ownership check;
  - heartbeat;
  - replay from Last-Event-ID;
  - cancel detection.

Frontend:

- Add `/agent`.
- Add session sidebar.
- Add message timeline.
- Add Markdown rendering.
- Add initial tool call timeline states for queued, running, completed, failed,
  and cancelled tool executions.
- Add SSE reconnect handling.

Exit criteria:

- User can create a session, send a message, receive a streamed echo or simple
  model response, refresh the browser, and see the complete message history.
- User A cannot list or stream user B's sessions.

### Phase 2: Research Tool Registry

Goal: introduce a TradingAgents-CN-native tool registry instead of copying all
Vibe tools.

Build:

- `ResearchTool` base interface.
- JSON-schema tool definitions for LLM function calling.
- Permission metadata per tool.
- `ResearchToolRegistry.for_principal(principal)`.
- `ToolExecutionContext` passed to every tool, containing:
  - principal;
  - session id;
  - request id;
  - artifact writer;
  - event emitter;
  - budget and timeout;
  - cancellation token.
- Tool execution audit events.
- Tool result size limits and redaction.
- Server-side input validation before a tool touches data services.

Initial tools:

- `market_data_lookup`;
- `screening_run`;
- `single_stock_analysis`;
- `batch_stock_analysis`;
- `report_lookup`;
- `report_write`.

Exit criteria:

- Global Agent can call existing TradingAgents-CN services through tools.
- Tool events appear in `/agent`.
- Tool execution is denied if the principal lacks permission.

### Phase 3: Port AgentLoop

Goal: port the useful behavior of Vibe's AgentLoop without importing unsafe
runtime assumptions.

Port or rewrite:

- message formatting;
- model streaming wrapper;
- tool call execution;
- read-only tool batching;
- context compaction;
- tool-result truncation;
- finish_reason `length` continuation;
- event emission.

Do not port:

- Vibe's system prompt wholesale;
- shell tools;
- file edit tools;
- local workspace memory;
- live trading tools;
- process-local session store;
- process-local event bus as the only replay source;
- `~/.vibe-trading` shared cache paths;
- Vibe-specific run directory assumptions;
- Vibe API auth assumptions.

Prompt migration rule:

- Rewrite the system prompt for TradingAgents-CN. Vibe's prompt describes Vibe
  tools, local files, swarm teams, and runtime claims that are not true in
  TradingAgents-CN. Reusing it would cause the Agent to promise unavailable
  tools and unsafe actions.
- Prompt-visible tool names must be generated from
  `ResearchToolRegistry.for_principal(principal)`, not from a static copied
  tool list.

Runtime migration rule:

- Long-running tool execution should happen in a worker/job context, not inside
  a FastAPI request handler.
- Vibe's read-only parallel tool batching can be reused as a design pattern, but
  thread-pool execution must be adapted to TradingAgents-CN's async/worker
  boundaries and database/session lifecycle.

Exit criteria:

- The Agent can answer a research question using at least one tool.
- Tool calls are persisted and replayable.
- Long model output is not truncated after refresh.
- Cancellation stops the task and emits a terminal event.

### Phase 4: Port Alpha Zoo Core

Goal: add factor registry and factor analytics to TradingAgents-CN.

Create `backend/trader/factors` with:

- factor base operators;
- strict Alpha metadata schema;
- registry scanner;
- Alpha101 zoo;
- GTJA191 zoo;
- Qlib158 zoo;
- IC/IR computation;
- grouped NAV computation;
- bench runner;
- compare runner.

Important namespace changes:

- Vibe imports like `src.factors...` must become `trader.factors...`.
- Alpha ids and metadata should remain stable.
- Do not reuse `trader/flows/alpha` for this; that name already means a data
  provider area, not factor research.

Exit criteria:

- Factor registry lists all ported factors.
- A single factor can compute over a test panel.
- IC/IR and grouped NAV tests pass against deterministic fixtures.

### Phase 5: A-Share Panel Loader

Goal: adapt Alpha Zoo to TradingAgents-CN data, not Vibe's lightweight loaders.

Create `backend/trader/factors/panel_loader.py`.

Required output:

```text
{
  "open": DataFrame[date x symbol],
  "high": DataFrame[date x symbol],
  "low": DataFrame[date x symbol],
  "close": DataFrame[date x symbol],
  "volume": DataFrame[date x symbol],
  "amount": DataFrame[date x symbol],
  "vwap": DataFrame[date x symbol],
  "_meta": dict
}
```

Inputs:

- explicit symbols;
- screening result id only after screening runs are persisted as user-owned
  artifacts;
- sector/industry id;
- favorites list;
- uploaded universe;
- market index universe when supported.

Rules:

- Data is read through TradingAgents-CN market/historical services or DB, not
  direct ad-hoc CSV paths.
- Do not use Vibe's local `~/.vibe-trading/cache` model in the web backend.
  Server caches must be controlled by TradingAgents-CN and safe for multi-user
  operation.
- Universe membership must be captured in metadata.
- Missing data must be reported in `_meta.missing_symbols`.
- Generated panel artifacts are user-scoped when derived from a private
  universe or private screening result.
- Panel metadata must include:
  - data source;
  - adjusted-price mode;
  - trading calendar;
  - universe source;
  - missing symbols;
  - suspended/no-trade dates if known.
- Unit contracts must be explicit. For A-share Tushare-style data, `volume` is
  commonly reported in lots and `amount` in thousand CNY; normalize or record
  the source units before computing `vwap`.
- `vwap` must be computed from the normalized `amount` and `volume` contract,
  not copied from a formula that assumes US share/dollar units.

Exit criteria:

- A storage-sector universe can produce a valid panel.
- Insufficient data returns a typed error, not a partial silent result.
- Panel loader tests cover missing symbols and sparse history.

### Phase 6: Alpha Zoo APIs And Jobs

Goal: expose Alpha Zoo through TradingAgents-CN APIs and task model.

Routes:

```text
GET  /api/alpha-zoo/list
GET  /api/alpha-zoo/{alpha_id}
POST /api/alpha-zoo/bench
GET  /api/alpha-zoo/jobs/{job_id}
GET  /api/alpha-zoo/jobs/{job_id}/events
POST /api/alpha-zoo/compare
```

Design:

- Factor definitions are public.
- Bench and compare jobs are private to the submitting user.
- Do not put Alpha jobs directly into the current symbol-only queue shape.
  Choose one:
  - create a dedicated `research_jobs` queue/table;
  - or extend the current queue with typed `task_type`, `resource_id`, optional
    `symbol`, typed params, and research-specific ownership checks.
- Concurrency limits should align with both system defaults and user-level
  quota/concurrency settings such as `daily_quota` and `concurrent_limit`.
- Results persist as `research_artifacts`.
- SSE stream checks ownership before subscribing.
- Job events are persisted so refresh can render the final result and the
  intermediate tool timeline.

Exit criteria:

- User can list public factors.
- User can run a private bench job.
- Refreshing the UI does not lose the final bench result.
- User A cannot read or stream user B's bench job.

### Phase 7: Correlation Matrix

Goal: add matrix-style research for sectors, selected stocks, or custom
universes.

Backend:

```text
POST /api/research-matrix/correlation
GET  /api/research-matrix/jobs/{job_id}
```

Inputs:

- symbols;
- sector;
- screening result id only after screening runs are persisted as user-owned
  artifacts;
- favorites;
- date range;
- window;
- method: pearson or spearman;
- return type: close return, log return, or excess return when supported.

Output:

```text
{
  "labels": ["300750.SZ", "002594.SZ"],
  "matrix": [[1.0, 0.42], [0.42, 1.0]],
  "method": "pearson",
  "window": 90,
  "universe_meta": {...}
}
```

Frontend:

- Rebuild Vibe's heatmap in TradingAgents-CN's Next.js UI.
- Link matrix cells to stock detail and single-stock analysis.
- Allow "send this universe to Agent".

Exit criteria:

- User can compute a matrix for a selected A-share universe.
- Matrix result is private if the input universe is private.
- Matrix can be attached to a research session.

### Phase 8: Frontend Integration

Goal: make the features usable as one product flow.

Pages:

- `/agent`: global research conversation.
- `/alpha-zoo`: factor browse, detail, bench, compare.
- `/correlation`: matrix analysis.

Navigation:

- Add top-level or research group nav entry.
- Link from screening results to:
  - batch analysis;
  - correlation matrix;
  - Alpha bench;
  - Agent session.
- Link from Agent tool cards to:
  - report detail;
  - task detail;
  - Alpha bench result;
  - correlation matrix;
  - stock detail.

Rendering:

- Use existing Next.js frontend stack.
- Do not copy Vibe's Vite router.
- Use TradingAgents-CN components and `libs/` API convention.
- Markdown renderer must support streamed Markdown without losing final content.

Exit criteria:

- User can complete the storage-sector workflow from `/agent`.
- Generated intermediate artifacts are inspectable from links.
- Browser refresh preserves final output and task state.

### Phase 9: Report Synthesis

Goal: turn Agent output into persistent research reports.

Report structure:

```text
1. Sector summary
2. Universe construction method
3. Screening filters and top candidates
4. Correlation matrix findings
5. Alpha/factor findings
6. Single-stock TradingAgents conclusions
7. Recommended stocks
8. Risk factors
9. Data limitations
10. Linked artifacts and task ids
```

The Agent may draft the report, but the backend should store structured
sections where possible so the report UI can display and filter them.

Exit criteria:

- Final Agent answer includes recommended stocks when the workflow produced
  sufficient evidence.
- Report detail page shows linked artifacts.
- Missing evidence is shown as a limitation, not hallucinated as a conclusion.

## Frontend UX Target

### Agent Page

The `/agent` page should be a research workspace, not a marketing page.

Expected elements:

- session list;
- current conversation;
- model/status indicator;
- tool execution timeline;
- artifact drawer;
- cancel button;
- retry button for failed tool calls;
- Markdown assistant messages;
- final report card;
- links to tasks, reports, Alpha results, correlation matrices, and stock pages.

### Alpha Zoo Page

Expected elements:

- factor list with filters:
  - zoo;
  - theme;
  - universe;
  - required columns;
  - search;
- factor detail with formula and metadata;
- bench runner;
- compare runner;
- result table sorted by IC/IR;
- category breakdown:
  - alive;
  - reversed;
  - dead;
- "use in Agent" action.

### Correlation Page

Expected elements:

- universe selector:
  - symbols;
  - sector;
  - screening result;
  - favorites;
- date/window selector;
- method selector;
- heatmap;
- high-correlation pairs;
- low-correlation/diversification candidates;
- "send universe to Agent" action.

## LLM And MiniMax Token-Plan

TradingAgents-CN should keep its config model as the source of truth.

Rules:

- Runnable model configs come from `/api/config/llm`.
- Model catalog metadata remains separate.
- Provider management remains in TradingAgents-CN settings.
- Global provider/model/default mutations require an admin permission.
- If users can bring their own model keys, store them as user-owned secrets in a
  separate path from system provider credentials.
- User keys and system keys must be redacted in API responses.
- The Agent chooses models from the same configured models used by existing
  analysis pages.

MiniMax token-plan:

- TradingAgents-CN already has `minimax-token-plan` provider wiring in the LLM
  client/config area.
- First verify live behavior through the current Anthropic-compatible client.
- If tool calls, headers, max token handling, or finish reasons fail, port the
  dedicated Vibe adapter into TradingAgents-CN's LLM client layer.
- Do not force users into OpenAI-compatible MiniMax configuration for the
  token-plan path.

## Testing Strategy

### Backend Unit Tests

Add tests for:

- `ResearchPrincipal` permission checks;
- tool registry filtering;
- user-scoped session CRUD;
- user-scoped event replay;
- tool execution denial;
- Alpha metadata loading;
- factor compute fixtures;
- IC/IR math;
- panel loader sparse data behavior;
- correlation matrix math.

### Backend Integration Tests

Add tests for:

- user A cannot access user B sessions;
- user A cannot stream user B session events;
- user A cannot read user B Alpha bench jobs;
- user A cannot read user B correlation jobs;
- user A cannot cancel user B research tasks;
- user A cannot list, detail, content-read, download, or delete user B reports;
- user A cannot recover user B task status through task-status fallback paths;
- document-style report writes persist `user_id`;
- non-admin users cannot add, update, delete, toggle, or set defaults for global
  LLM/provider configs;
- Alpha/correlation jobs reject invalid or unowned `screening_result_id`;
- Agent can call screening and single-stock analysis tools through service
  wrappers;
- Alpha bench jobs persist results after worker completion;
- SSE streams replay events after reconnect.

### Frontend Tests

Add tests for:

- `/agent` session creation and message rendering;
- Markdown streamed content rendering;
- tool timeline rendering;
- Alpha list/detail/bench UI states;
- correlation heatmap request and result rendering;
- permission errors shown as not-found/private-resource messages;
- links from Agent artifacts to task/report/factor/matrix pages.

### Verification Commands

Backend:

```bash
cd backend
conda run -n trader pytest
conda run -n trader ruff check .
conda run -n trader pyright .
```

Frontend:

```bash
cd frontend
pnpm test
pnpm type-check
pnpm build
```

Run scoped tests during each phase, then run the broader suite before merging.

## Rollout Strategy

### Recommended Order

1. Security and ownership audit.
2. Research session/event shell.
3. Research tool registry with existing TradingAgents-CN tools.
4. AgentLoop migration.
5. Alpha Zoo core migration.
6. A-share panel loader.
7. Alpha Zoo jobs and UI.
8. Correlation matrix jobs and UI.
9. Full sector-to-stock research workflow.
10. Report synthesis and artifact linking.

### Release Gates

Do not release the global Agent until:

- all private resources are user-scoped;
- unsafe Vibe tools are excluded;
- SSE ownership tests pass;
- report list/detail/content/download/delete endpoints are user-scoped;
- report/task fallback reads are ownership-checked;
- task-status recovery cannot return another user's memory/document-store
  result;
- global LLM/provider mutating routes are admin-gated;
- research jobs are typed and not forced into the existing symbol-only queue
  schema;
- screening result ids, if accepted by research APIs, are persisted user-owned
  artifacts;
- Alpha bench results persist across refresh;
- model keys are redacted;
- generated output survives page refresh;
- every tool has a permission label.

### Feature Flags

Use feature flags during rollout:

```text
RESEARCH_AGENT_ENABLED
ALPHA_ZOO_ENABLED
RESEARCH_MATRIX_ENABLED
RESEARCH_AGENT_TOOL_ALPHA_ENABLED
RESEARCH_AGENT_TOOL_ANALYSIS_ENABLED
```

Flags should be system settings, not client-only toggles.

## Risks And Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Cross-user data leakage | Critical | Phase 0 ownership tests before feature migration |
| Unsafe Vibe tools exposed | Critical | Server-side tool whitelist and permissions |
| Alpha bench overloads server | High | Queue, concurrency caps, cancellation, job TTL |
| Data panel mismatch | High | Dedicated A-share panel loader with fixtures |
| MiniMax token-plan mismatch | Medium | Verify current client; port Vibe adapter only if needed |
| Frontend route duplication | Medium | Add new Next.js features; do not copy Vite router |
| Report hallucination | High | Require linked evidence/artifacts and limitation section |
| Refresh loses output | High | Persist messages/events/artifacts |
| Existing dirty worktree conflict | Medium | Use clean branch or worktree |

## Explicit Non-Goals For First Version

- Do not merge the entire Vibe FastAPI app.
- Do not run Vibe as a sidecar service for production.
- Do not copy the Vibe Vite frontend into TradingAgents-CN.
- Do not expose shell/file-edit tools.
- Do not add real trading execution.
- Do not replace TradingAgentsGraph.
- Do not rewrite the existing single-stock analysis workflow.
- Do not introduce a new database outside TradingAgents-CN's current storage
  strategy.
- Do not change the whole authentication model.

## Implementation Checklist

- [ ] Create clean TradingAgents-CN integration branch/worktree.
- [ ] Audit existing ownership checks for tasks, reports, streams, and config.
- [ ] Persist `user_id` in document-style analysis reports.
- [ ] Scope report list/detail/content/download/delete by current user.
- [ ] Scope task-status memory and fallback recovery by current user.
- [ ] Require admin permission for global LLM/provider mutations.
- [ ] Decide and implement dedicated or generalized research-job queue shape.
- [ ] Persist screening run artifacts before using `screening_result_id`.
- [ ] Add regression tests for cross-user denial.
- [ ] Add `ResearchPrincipal` and permissions.
- [ ] Add research sessions and messages.
- [ ] Add replayable research event stream.
- [ ] Add server-side research tool registry.
- [ ] Wrap existing screening API as a research tool.
- [ ] Wrap existing single-stock analysis as a research tool.
- [ ] Wrap existing batch analysis as a research tool.
- [ ] Wrap report read/write as research tools.
- [ ] Port safe parts of Vibe AgentLoop.
- [ ] Add Agent frontend page.
- [ ] Port factor core to `backend/trader/factors`.
- [ ] Add A-share panel loader.
- [ ] Add Alpha Zoo APIs.
- [ ] Add Alpha Zoo frontend page.
- [ ] Add Alpha bench/compare workers and artifacts.
- [ ] Add correlation matrix backend.
- [ ] Add correlation frontend page.
- [ ] Add report synthesis and artifact linking.
- [ ] Run backend lint, typecheck, and tests.
- [ ] Run frontend tests, typecheck, and build.

## Architecture Review Notes

This plan intentionally keeps TradingAgents-CN's product shell, auth, data,
queue, and report systems as the destination architecture. Vibe contributes the
global Agent pattern and quant research modules, not a second application.

The most important dependency is the A-share panel loader. Alpha Zoo cannot be
considered migrated until it runs on TradingAgents-CN's real historical data
services and stores user-scoped results.

The most important security dependency is tool filtering. The global Agent must
never see tools that the current user is not authorized to call.

## Document Review Result

Reviewed on 2026-06-08.

Checked:

- No unresolved markers remain.
- The migration direction is consistent: TradingAgents-CN is the destination,
  Vibe-Trading is the source of selected capabilities.
- User isolation is treated as Phase 0 and as an API/tool/data requirement, not
  as a later UI-only concern.
- Existing TradingAgents-CN task ownership naming differences are called out:
  Redis queue records use `user`, while new research resources should use
  `user_id`.
- Vibe's unsafe tools are explicitly excluded from the normal-user web Agent.
- Alpha Zoo migration includes both formula code and the required A-share panel
  loader, so factor math is not planned in isolation from real TradingAgents-CN
  data.
- Alpha bench and correlation jobs are planned as user-scoped persisted
  artifacts, not process-local memory.
- Frontend work is planned as native Next.js features, not a copy of Vibe's
  Vite app.
- Verification commands use the `trader` conda environment and the existing
  frontend pnpm scripts.

Residual implementation risks:

- MiniMax token-plan compatibility must be verified against the active
  TradingAgents-CN client before deciding whether to port the Vibe adapter.
- A-share panel loader correctness depends on real historical data shape and
  sparse-data behavior; deterministic fixtures should be created before moving
  the full factor zoo.

Second review on 2026-06-08:

Additional code-level findings incorporated into the plan:

- Report routes are not only a generic audit concern. The inspected
  `backend/app/routers/reports.py` paths need user filtering or admin checks for
  list, detail, module content, download, and delete.
- Document-style report persistence needs to write `user_id`; otherwise report
  ownership is inferred indirectly and inconsistently.
- Single-analysis task-status recovery can read memory/document-store state by
  task id; the plan now requires ownership verification before returning any
  recovered result.
- Current Redis queue semantics are symbol-centric, so Alpha Zoo, correlation,
  and free-form Agent tasks need a dedicated or generalized research-job model.
- Screening output is not currently a persisted user-owned artifact, so
  `screening_result_id` is conditional rather than immediately available.
- Vibe's local session store, process-local event bus, prompt, and
  `~/.vibe-trading` cache are not reusable as-is in a multi-user web backend.
- Global provider/model/default LLM config mutation needs admin enforcement,
  while user-owned model keys need a separate private credential path.

After this review, the remaining design risk is implementation accuracy: the
first code phase should land ownership tests and config-admin tests before any
Agent/Alpha UI is exposed.
