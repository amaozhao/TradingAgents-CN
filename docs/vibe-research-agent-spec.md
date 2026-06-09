# Vibe Research Agent Integration Spec

Date: 2026-06-08

Source repositories:

- Destination: `/home/amaozhao/workspace/TradingAgents-CN`
- Capability source: `/home/amaozhao/workspace/Vibe-Trading`
- Architecture plan: `docs/vibe-research-agent-integration-plan.md`

## Summary

TradingAgents-CN should become the single product surface for sector, universe,
factor, matrix, single-stock, and final recommendation analysis. Vibe-Trading
contributes selected global Agent, Alpha Zoo, and correlation capabilities, but
it must not become a production sidecar or replace TradingAgents-CN's existing
TradingAgentsGraph single-stock workflow.

The first releasable result is a user-scoped research workspace where a user can
ask a question such as "分析 A 股储能板块，给出推荐个股", watch tool progress stream
in the browser, refresh safely, inspect linked Alpha/correlation/single-stock
artifacts, and receive a final report with recommended stocks when evidence is
sufficient.

## Goals

- Add a global research Agent in TradingAgents-CN under `/agent`.
- Add Alpha Zoo factor browsing, benchmark, and comparison under `/alpha-zoo`.
- Add correlation/matrix research under `/correlation`.
- Reuse TradingAgents-CN authentication, data services, queue conventions,
  reports, model configuration, and frontend shell.
- Port only safe Vibe capabilities:
  - ReAct-style loop behavior;
  - streaming and event patterns;
  - Alpha factor formulas and analytics;
  - matrix visualization ideas.
- Preserve complete generated content across browser refresh.
- Enforce user isolation and permissions from the first code phase.

## Non-Goals

- Do not run Vibe-Trading as a production sidecar.
- Do not copy Vibe's Vite frontend into TradingAgents-CN.
- Do not expose shell, local file read/write, raw database, global log, or live
  trading tools to normal users.
- Do not rewrite TradingAgentsGraph.
- Do not change the whole authentication model.
- Do not force MiniMax token-plan users into OpenAI-compatible configuration.
- Do not use port `8000` for local verification.

## Users And Permissions

Primary users:

- Normal authenticated user: can run private research, Alpha bench, matrix, and
  own report workflows.
- Admin user: can additionally mutate global provider/model configuration and
  inspect system-level diagnostics.

Every private resource must include `user_id`:

- research sessions;
- messages;
- tasks;
- events;
- artifacts;
- Alpha bench and compare jobs;
- correlation jobs;
- uploaded universes/files;
- generated reports;
- user-owned model keys.

Endpoints that read, stream, cancel, retry, download, or delete private
resources must return `404` when the resource does not belong to the current
user. Admin-only system resources may return `403` when the user lacks admin
permission.

## Current-Code Findings That Shape The Spec

- `backend/app/routers/reports.py` currently accepts `get_current_user`, but
  report list/detail/content/download/delete paths need mandatory user filters
  or explicit admin checks.
- `backend/app/services/analysis/simple/reports.py` currently saves
  document-style `analysis_reports` without a direct `user_id`; report ownership
  must not rely only on task fallback inference.
- `backend/app/routers/analysis/single.py` and
  `backend/app/routers/analysis/setup.py` can recover task/report state by
  `task_id`; recovery must verify ownership before returning any data.
- `backend/app/services/queue/service.py` is symbol-centric. It requires a
  `symbol` when enqueuing and stores `user`, `symbol`, and `params`, so it is
  not a complete fit for Alpha, correlation, or free-form research jobs.
- `backend/app/routers/config/llm.py` and
  `backend/app/routers/config/providers.py` mutating routes need admin gating
  for global provider/model/default changes.
- Screening results are currently global market scans rather than persisted
  user-owned artifacts. APIs must not accept `screening_result_id` until that
  artifact model exists.

## Required Product Flows

### Flow 1: Sector Research From Agent

1. User opens `/agent`.
2. User creates or selects a research session.
3. User submits "分析 A 股储能板块，给出推荐个股".
4. Backend creates a user-scoped research task.
5. Agent receives only tools allowed for the current principal.
6. Agent constructs or requests a universe:
   - explicit symbols;
   - favorites;
   - sector/industry source;
   - persisted screening artifact when available.
7. Agent runs screening, matrix, Alpha, and single-stock analysis tools as
   needed.
8. Frontend renders streamed Markdown and tool timeline events.
9. Final output is persisted as a message and report/artifact.
10. Browser refresh shows the complete final content and linked artifacts.

Acceptance:

- Refreshing after completion does not truncate the answer.
- Final answer includes recommended stocks only when supporting artifacts or
  linked analysis exist.
- Missing evidence appears in "数据限制", not as invented conclusions.

### Flow 2: Alpha Zoo

1. User opens `/alpha-zoo`.
2. User filters factors by zoo, theme, required columns, and search keyword.
3. User opens factor detail and sees formula, metadata, and required panel
   columns.
4. User runs a bench or compare job against an explicit or user-owned universe.
5. Result persists as a private artifact.
6. User can send the result or universe to an Agent session.

Acceptance:

- Factor definitions are public.
- Job results are private to the submitting user.
- A user cannot read or stream another user's Alpha job.
- Alpha jobs are not forced into the existing symbol-only queue schema.

### Flow 3: Correlation Matrix

1. User opens `/correlation`.
2. User selects explicit symbols, favorites, sector, or a persisted private
   universe.
3. User chooses date range, rolling window, and method.
4. Backend computes the matrix and persists the result.
5. Frontend shows heatmap, high-correlation pairs, and diversification
   candidates.
6. User can send the universe or matrix artifact to Agent.

Acceptance:

- Private input universe produces a private matrix result.
- A user cannot read or stream another user's matrix job.
- Matrix result is reloadable after browser refresh.

## Backend Requirements

### Ownership Foundation

- Add helper functions that normalize owner fields:
  - existing queue tasks may use `user`;
  - new research resources must use `user_id`;
  - report/task fallback reads must compare against current user before
    returning data.
- Fix document-style report persistence to write `user_id`.
- Apply user filters to report list/detail/content/download/delete.
- Add admin checks to mutating global LLM/provider endpoints.

### Research Data Model

Add persistent models through the existing storage strategy:

```text
research_sessions
  session_id
  user_id
  title
  status
  created_at
  updated_at
  last_message_at

research_messages
  message_id
  session_id
  user_id
  role
  content
  tool_name
  tool_call_id
  metadata
  created_at

research_tasks
  task_id
  session_id
  user_id
  task_type
  status
  current_step
  progress
  error_message
  payload
  result
  created_at
  started_at
  completed_at

research_events
  event_id
  session_id
  task_id
  user_id
  event_type
  payload
  created_at

research_artifacts
  artifact_id
  user_id
  session_id
  task_id
  type
  title
  payload
  storage_path
  visibility
  created_at
  updated_at
```

### Research Job Model

Use a dedicated `research_jobs` queue/table unless the existing queue is
generalized with typed fields:

```text
task_type: agent | alpha_bench | alpha_compare | correlation | report_synthesis
resource_id: session_id or artifact_id
symbol: nullable
payload: typed json
user_id: string
```

The job model must enforce:

- current user's quota and concurrency;
- cancellation;
- job TTL or retention policy;
- persisted terminal result;
- persisted events for replay.

### Research Tool Registry

Introduce a TradingAgents-CN-native tool registry:

```text
ResearchPrincipal
  user_id
  role
  permissions
  session_id

ToolExecutionContext
  principal
  session_id
  request_id
  artifact_writer
  event_emitter
  budget
  timeout
  cancel_token
```

Initial tools:

- `market_data_lookup`
- `screening_run`
- `single_stock_analysis`
- `batch_stock_analysis`
- `report_lookup`
- `report_write`

Later tools:

- `alpha_list`
- `alpha_detail`
- `alpha_bench`
- `alpha_compare`
- `correlation_matrix`
- `sector_universe`

The Agent prompt must be generated from the filtered registry for the current
principal. It must not include static Vibe tool names.

### Agent Loop

Port these behaviors from Vibe:

- streaming model output;
- tool call parsing and dispatch;
- read-only parallel tool execution where safe;
- tool-result truncation;
- context compaction;
- finish-reason length continuation;
- event emission.

Do not port:

- Vibe's system prompt;
- shell tools;
- file edit tools;
- local workspace memory;
- process-local session/event store as final persistence;
- `~/.vibe-trading` cache;
- live trading tools.

### Alpha Data Requirements

Port factor formulas and analytics, but replace Vibe data loaders with a
TradingAgents-CN panel loader:

```text
open: DataFrame[date x symbol]
high: DataFrame[date x symbol]
low: DataFrame[date x symbol]
close: DataFrame[date x symbol]
volume: DataFrame[date x symbol]
amount: DataFrame[date x symbol]
vwap: DataFrame[date x symbol]
_meta: dict
```

Panel metadata must include:

- source service;
- adjusted-price mode;
- trading calendar;
- source units for `volume` and `amount`;
- normalized units used for `vwap`;
- universe source;
- missing symbols;
- sparse and suspended dates where available.

For Tushare-style A-share data, `volume` and `amount` units must be explicitly
normalized or recorded before computing `vwap`.

## Frontend Requirements

### `/agent`

Required UI:

- session list;
- current conversation;
- model/status indicator;
- tool timeline;
- artifact drawer;
- cancel and retry actions;
- streamed Markdown renderer;
- final report card;
- links to reports, tasks, Alpha artifacts, matrix artifacts, and stock pages.

The page must render the actual workspace as the first screen. It must not be a
landing page.

### `/alpha-zoo`

Required UI:

- factor table with zoo/theme/required-column/search filters;
- factor detail panel;
- bench and compare runner;
- IC/IR and grouped NAV result summary;
- alive/reversed/dead classification;
- "send to Agent" action.

### `/correlation`

Required UI:

- universe selector;
- date range and window controls;
- method selector;
- heatmap;
- high-correlation pairs;
- diversification candidates;
- "send universe to Agent" action.

## LLM And MiniMax Requirements

- Runnable model choices come from `/api/config/llm`.
- Model catalog metadata remains separate from runnable config.
- Global provider/model/default mutations require admin permission.
- User-owned model keys use a separate private credential path from system
  provider credentials.
- User-owned model key storage must include create/list/update/delete APIs,
  owner-scoped reads, redacted responses, and audit events that never include
  plaintext secrets.
- API responses redact keys.
- MiniMax token-plan remains a first-class provider path and must not be forced
  into OpenAI-compatible format.
- If the current TradingAgents-CN Anthropic-compatible MiniMax path fails for
  tool calls, headers, max token handling, or finish reasons, port Vibe's
  dedicated adapter into the TradingAgents-CN LLM client layer.

## Acceptance Criteria

### Security

- User A cannot list, detail-read, content-read, download, delete, stream, or
  recover user B's reports or tasks.
- User A cannot read, stream, cancel, or retry user B's research task.
- User A cannot read user B's Alpha bench, compare, or matrix artifacts.
- Non-admin users cannot mutate global LLM/provider/default configuration.
- Non-admin users cannot mutate compatibility LLM/default endpoints either:
  `POST /api/config/llm` and `POST /api/config/default/llm`.
- User A cannot list, read, update, or delete user B's private model keys.
- User keys and system keys are redacted in every config response and audit
  event.

### Persistence

- Agent messages, tool events, and final output persist across browser refresh.
- Alpha bench and correlation results persist after worker completion.
- SSE supports reconnect with replay from the last event id.

### Product

- `/agent` can complete the storage-sector research workflow using at least one
  TradingAgents-CN analysis tool and one persisted artifact.
- `/alpha-zoo` can list factors and run a private bench job.
- `/correlation` can compute and display a private matrix.
- Final report includes recommended stocks only when generated evidence
  supports them.

### Verification

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

## ADR

Decision: Integrate Vibe capabilities into TradingAgents-CN rather than running
Vibe as a sidecar or merging the whole Vibe application.

Drivers:

- TradingAgents-CN already owns auth, data, reports, model config, and product
  shell.
- Vibe provides missing global Agent, Alpha Zoo, and matrix capabilities.
- Multi-user isolation and permissions are mandatory.

Rejected alternatives:

- Run Vibe as a sidecar: rejected because it duplicates auth, sessions,
  persistence, frontend shell, and user isolation.
- Replace TradingAgentsGraph: rejected because TradingAgents-CN already has the
  canonical single-stock workflow.
- Copy Vibe frontend: rejected because TradingAgents-CN uses Next.js and must
  keep a single product shell.
- Use the current symbol-only queue unchanged: rejected because Alpha,
  correlation, and Agent tasks are not always single-symbol tasks.

Consequences:

- More upfront backend safety work is required.
- Phase 0 must fix current report/task/config ownership gaps before feature
  migration.
- The Alpha port requires a TradingAgents-CN-native A-share panel loader before
  results are trustworthy.

Follow-ups:

- Implement Phase 0 safety fixes and tests first.
- Verify MiniMax token-plan behavior against the active client.
- Split implementation into isolated commits following the Lore commit
  protocol.
