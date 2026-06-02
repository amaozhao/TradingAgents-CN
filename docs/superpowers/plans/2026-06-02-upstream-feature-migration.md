# Upstream Backend Capability Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the backend/core capabilities that exist in `/home/amaozhao/workspace/TradingAgents` but are missing or incomplete in this CN project, while preserving the CN backend API, A-share data behavior, Chinese reports, task progress, database configuration, and existing role memories.

**Architecture:** Treat `TradingAgents-CN` as the host system and upstream `TradingAgents` as the capability source. Add upstream modules only when they are standalone, then connect them through CN-compatible adapters so graph state, node names, provider configuration, and backend response shapes remain stable. Do not replace CN dataflows, LLM configuration, prompts, progress reporting, or report extraction with upstream defaults.

**Tech Stack:** Python, LangGraph, LangChain, Pydantic, FastAPI backend, MongoDB-backed configuration, ChromaDB role memory, CN multi-market data providers, pytest, conda env `trader`.

## Execution Status

Status as of 2026-06-02:
- Tasks 0-14 have been implemented against this spec.
- The CN backend remains the host system; upstream modules were adapted rather than replacing CN data routing, prompts, progress streaming, or report contracts.
- Existing CN `FinancialSituationMemory` / Chroma role memories are preserved when `memory_enabled` is true.
- Upstream `TradingMemoryLog` is added alongside the existing role memories for final-decision logging and delayed outcome reflection.
- Local MongoDB verification uses Docker Compose service `tradingagents-mongodb`; current health check: container `healthy`, `db.adminCommand({ping:1}).ok == 1`.
- Legacy import/collection blockers have been resolved with compatibility shims for `app.database`, `app.routers.auth`, `tradingagents.llm_adapters.dashscope_adapter`, legacy dataflow utility paths, `TushareDataAdapter`, `OptimizedChinaDataFlow`, upstream `aggressive_debator`, and old `create_trading_graph()`.
- Legacy live/manual tests that require a running `localhost:8000` backend, missing local export fixtures, or direct live scripts are skipped by default unless `TRADINGAGENTS_RUN_LIVE_TESTS=1` is set.
- Verification completed in conda env `trader`:
  - migrated verification matrix: `310 passed, 1 deselected, 65 warnings, 64 subtests passed`.
  - compatibility target set: `42 passed, 24 warnings`.
  - package/directories: `59 passed, 41 warnings`.
  - legacy/integration subdirectories: `22 passed, 17 warnings`.
  - top-level test chunks: `183 passed, 5 skipped`; `191 passed, 5 skipped, 1 deselected`; `125 passed, 4 skipped`; `182 passed, 9 skipped`; `184 passed, 8 skipped`; `60 passed`.
  - full collection: `1042/1043 tests collected (1 deselected)`.
  - final full suite: `1013 passed, 31 skipped, 1 deselected, 479 warnings, 64 subtests passed`.
  - compile check: `python -m compileall -q app tradingagents scripts/smoke_structured_output.py`.
  - import audit: all migrated upstream/backend compatibility modules import successfully.

---

## Scope

This plan covers backend/core runtime migration only.

In scope:
- LangGraph workflow/checkpoint/runtime capabilities from upstream.
- Structured output schemas and fallback wrappers from upstream.
- Portfolio Manager / final decision semantics from upstream, adapted to CN report contracts.
- LLM provider capability handling from upstream, merged with CN providers and database API-key behavior.
- Upstream dataflow safety utilities, no-data behavior, symbol normalization, and market-data validation, connected to CN A/HK/US data sources.
- TradingMemoryLog decision/reflection capability, adapted for A-share and CN benchmark/data sources.
- Upstream tests as verification contracts, adapted to avoid live network dependence.

Out of scope for the first backend migration:
- Frontend UI redesign.
- CLI polish modules unless required by backend tests.
- Replacing CN data providers with yfinance or Alpha Vantage defaults.
- Replacing CN Chinese prompts with upstream English prompts.
- Removing existing CN backend APIs or report fields.

## Current Source Truths

Current project root:
- `/home/amaozhao/workspace/TradingAgents-CN`

Upstream source root:
- `/home/amaozhao/workspace/TradingAgents`

Current conda environment:
- `trader`

Do not use:
- `uv`

Important dirty-worktree note:
- Existing dependency/frontend changes are already present in the worktree.
- Existing untracked upstream-copy files must be reviewed as partial inputs, not treated as completed migration.
- Do not revert unrelated user or previous-session changes.

## Non-Negotiable Compatibility Contracts

The migration is only acceptable if these remain true:

1. Backend callers can still call `TradingAgentsGraph.propagate(company_name, trade_date, progress_callback=None, task_id=None)`.
2. `progress_callback`, `task_id`, node timing, and `performance_metrics` remain available to `app/services/simple_analysis_service.py`, `app/worker.py`, and web progress flows.
3. Backend results still expose `market_report`, `sentiment_report`, `news_report`, `fundamentals_report`, `investment_debate_state`, `risk_debate_state`, `investment_plan`, `trader_investment_plan`, and `final_trade_decision`.
4. `SignalProcessor.process_signal()` still returns the CN dictionary shape expected by backend/API users:
   - `action`
   - `target_price`
   - `confidence`
   - `risk_score`
   - `reasoning`
5. A-share/HK/US data routing remains controlled by CN data source logic and database configuration.
6. Database-supplied API keys and base URLs remain supported and take precedence where CN currently supports them.
7. Chinese prompts, Chinese output, target-price requirements, and market/currency constraints remain preserved.
8. ChromaDB role memories remain preserved; upstream `TradingMemoryLog` is additive.

## Known Structural Conflicts To Resolve

| Conflict | Upstream Behavior | CN Behavior | Required Resolution |
|---|---|---|---|
| Graph compilation | `GraphSetup.setup_graph()` returns workflow, caller compiles it and can recompile with checkpointer | `GraphSetup.setup_graph()` returns compiled graph | Refactor CN to keep both workflow and compiled graph without losing progress streaming |
| Risk naming | `Aggressive Analyst`, `Conservative Analyst`, `Portfolio Manager`; state uses `aggressive_history`, `conservative_history` | `Risky Analyst`, `Safe Analyst`, `Risk Judge`; state uses `risky_history`, `safe_history` | Add compatibility aliases or dual-field state updates before renaming anything |
| Final signal | Upstream returns 5-tier rating string from markdown | CN returns Chinese structured dict with target price | Keep CN dict and add upstream rating parser as internal stable signal |
| Data source | Upstream router uses yfinance/Alpha Vantage | CN uses A/HK/US provider manager and DB source priority | Port router/safety concepts into CN provider entry points |
| Memory | Upstream final decision log with delayed outcome reflection | CN Chroma role memory | Add memory log alongside Chroma and adapt returns to CN market data |
| LLM keys | Upstream mostly env-based provider key lookup | CN supports DB key/base-url and mixed quick/deep providers | Merge lookup rules, keeping CN DB behavior intact |

---

## File Responsibility Map

### Additive Upstream Modules

These modules can be created from upstream, then patched for CN compatibility:

- `tradingagents/agents/schemas.py`: Pydantic schemas and render helpers for structured decision artifacts.
- `tradingagents/agents/utils/structured.py`: shared structured-output binding and free-text fallback.
- `tradingagents/agents/utils/rating.py`: deterministic parser for Buy/Overweight/Hold/Underweight/Sell.
- `tradingagents/graph/analyst_execution.py`: selected analyst validation and execution-plan metadata.
- `tradingagents/graph/checkpointer.py`: sqlite checkpoint helpers.
- `tradingagents/llm_clients/api_key_env.py`: canonical provider-to-env mapping.
- `tradingagents/llm_clients/azure_client.py`: Azure OpenAI client.
- `tradingagents/llm_clients/capabilities.py`: model capability table for structured-output behavior.
- `tradingagents/dataflows/symbol_utils.py`: no-data error type and symbol normalization, extended for CN markets.
- `tradingagents/dataflows/utils.py`: safe ticker/path utility.
- `tradingagents/dataflows/market_data_validator.py`: deterministic market-data snapshot, backed by CN data where applicable.

### Existing CN Modules That Must Be Modified Carefully

- `tradingagents/graph/trading_graph.py`: graph orchestration, provider creation, progress streaming, checkpoint integration, memory log integration, final signal processing.
- `tradingagents/graph/setup.py`: workflow construction, analyst execution plan, optional Portfolio Manager integration, node-name compatibility.
- `tradingagents/graph/propagation.py`: initial state fields, graph args, callbacks, checkpoint thread config.
- `tradingagents/graph/conditional_logic.py`: risk-node end destinations and compatibility with old/new node names.
- `tradingagents/graph/signal_processing.py`: merge deterministic rating parsing with CN dict extraction.
- `tradingagents/agents/utils/agent_states.py`: add upstream fields and risk aliases without removing CN counters.
- `tradingagents/agents/utils/agent_utils.py`: expose upstream tool function names as CN-compatible wrappers.
- `tradingagents/agents/utils/memory.py`: add `TradingMemoryLog` without breaking `FinancialSituationMemory`.
- `tradingagents/agents/managers/research_manager.py`: structured output plus CN prompt/memory/target-price constraints.
- `tradingagents/agents/trader/trader.py`: structured output plus CN prompt/memory/target-price constraints.
- `tradingagents/agents/managers/risk_manager.py`: either wrap as CN-compatible Portfolio Manager or share schema with new PM node.
- `tradingagents/agents/risk_mgmt/*.py`: dual-field risk state compatibility if upstream naming is introduced.
- `tradingagents/agents/analysts/social_media_analyst.py`: structured sentiment behavior without losing CN social data.
- `tradingagents/agents/__init__.py`: lazy exports for new/aliased factories.
- `tradingagents/llm_clients/factory.py`: provider routing merge.
- `tradingagents/llm_clients/openai_client.py`: structured capability handling and provider quirks.
- `tradingagents/llm_clients/google_client.py`: preserve CN Google adapter while adding thinking config support.
- `tradingagents/llm_clients/anthropic_client.py`: add effort handling.
- `tradingagents/llm_clients/model_catalog.py`: merge provider/model validation coverage.
- `tradingagents/llm_clients/provider_keys.py`: merge canonical provider key names.
- `tradingagents/default_config.py`: add missing upstream config keys while preserving DB-managed config boundaries.
- `pyproject.toml`, `requirements.txt`, `requirements-lock.txt`: dependency declarations using `>=` lower bounds where applicable.

### Backend Integration Points To Keep Stable

- `app/services/simple_analysis_service.py`
- `app/services/analysis_service.py`
- `app/routers/analysis.py`
- `app/worker.py`
- `web/utils/analysis_runner.py`
- `web/utils/report_exporter.py`
- `web/components/analysis_results.py`

These files should only be touched when a backend contract must explicitly understand a new optional field or node alias.

---

## Task Breakdown

### Task 0: Preflight And Baseline Inventory

**Purpose:** Establish exact baseline before migration and prevent accidental acceptance of partial copied files.

**Files:**
- Read: `/home/amaozhao/workspace/TradingAgents`
- Read: `/home/amaozhao/workspace/TradingAgents-CN`
- Review untracked: `tradingagents/agents/managers/portfolio_manager.py`
- Review untracked: `tradingagents/agents/schemas.py`
- Review untracked: `tradingagents/agents/utils/structured.py`
- Review untracked: `tradingagents/graph/analyst_execution.py`
- Review untracked: `tradingagents/graph/checkpointer.py`
- Review untracked: `tradingagents/llm_clients/api_key_env.py`
- Review untracked: `tradingagents/llm_clients/azure_client.py`
- Review untracked: `tradingagents/llm_clients/capabilities.py`

**Steps:**
- [ ] Run `git status --short` and save the list of unrelated dirty files in the implementation notes.
- [ ] Run `git -C /home/amaozhao/workspace/TradingAgents status --short` and verify upstream source is readable.
- [ ] Compare tracked upstream-only backend files with current tracked files.
- [ ] Mark existing untracked upstream-copy files as either `keep-and-adapt` or `replace-from-upstream`.
- [ ] Run import smoke in conda env `trader` for all untracked modules and record failures.

**Acceptance:**
- There is a written inventory of upstream-only backend/core files.
- Existing untracked files are explicitly classified.
- Known import failures are recorded before implementation begins.

---

### Task 1: Dependency And Config Foundation

**Purpose:** Add only the backend dependencies and config keys required for migrated upstream capabilities.

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`
- Modify: `requirements-lock.txt`
- Modify: `tradingagents/default_config.py`
- Test: `tests/test_env_overrides.py`
- Test: `tests/test_checkpoint_resume.py`

**Required dependency changes:**
- Add `langgraph-checkpoint-sqlite>=2.0.0`.
- Add `backtrader>=1.9.78.123` only if a migrated backend module imports it or an upstream verification test requires it.
- Keep existing dependency style in this repository.
- Do not use `uv`.

**Required config keys to add or preserve:**
- `checkpoint_enabled`
- `memory_log_path`
- `memory_log_max_entries`
- `analyst_concurrency_limit`
- `benchmark_ticker`
- `benchmark_map`
- `output_language`
- `temperature`
- `google_thinking_level`
- `openai_reasoning_effort`
- `anthropic_effort`
- `data_vendors`
- `tool_vendors`
- `news_article_limit`
- `global_news_article_limit`
- `global_news_lookback_days`
- `global_news_queries`

**Compatibility requirements:**
- CN DB/.env configuration boundaries remain valid.
- Existing `online_tools`, `online_news`, and `realtime_data` keys remain intact.
- `backend_url` remains compatible with CN provider creation and database override behavior.

**Acceptance:**
- `conda run -n trader python -c "from tradingagents.default_config import DEFAULT_CONFIG; print(DEFAULT_CONFIG['checkpoint_enabled'])"` succeeds.
- Config import does not initialize MongoDB or network clients.
- Dependency declarations include checkpoint support.

---

### Task 2: State Model And Risk Alias Compatibility

**Purpose:** Merge upstream state fields without breaking CN report extraction.

**Files:**
- Modify: `tradingagents/agents/utils/agent_states.py`
- Modify: `tradingagents/graph/propagation.py`
- Modify: `tradingagents/agents/risk_mgmt/aggresive_debator.py`
- Modify: `tradingagents/agents/risk_mgmt/conservative_debator.py`
- Modify: `tradingagents/agents/risk_mgmt/neutral_debator.py`
- Modify: `tradingagents/agents/managers/risk_manager.py`
- Test: `tests/test_crypto_asset_mode.py`
- Test: `tests/test_instrument_identity.py`

**Required state additions:**
- `asset_type`
- `instrument_context`
- `past_context`

**Required risk compatibility fields:**
- Existing CN fields remain:
  - `risky_history`
  - `safe_history`
  - `current_risky_response`
  - `current_safe_response`
- Upstream-compatible aliases are added or populated:
  - `aggressive_history`
  - `conservative_history`
  - `current_aggressive_response`
  - `current_conservative_response`

**Implementation rule:**
- During migration, every risk node update must preserve both CN and upstream field names until all backend/report consumers have been reviewed.

**Acceptance:**
- Existing CN report extraction can still read `risky_history` and `safe_history`.
- Upstream-style Portfolio Manager can read `aggressive_history` and `conservative_history`.
- Initial state includes all required fields with empty-string defaults where appropriate.

---

### Task 3: Instrument Identity And Safe Path Utilities

**Purpose:** Prevent ticker/company hallucination and unsafe result paths while supporting A-share/HK/US symbols.

**Files:**
- Create or adapt: `tradingagents/dataflows/symbol_utils.py`
- Create or adapt: `tradingagents/dataflows/utils.py`
- Modify: `tradingagents/agents/utils/agent_utils.py`
- Modify: `tradingagents/agents/utils/instrument_utils.py`
- Modify: `tradingagents/graph/trading_graph.py`
- Test: `tests/test_symbol_utils.py`
- Test: `tests/test_safe_ticker_component.py`
- Test: `tests/test_instrument_identity.py`

**Required behavior:**
- `safe_ticker_component()` rejects path traversal and produces a filesystem-safe ticker directory name.
- `resolve_instrument_identity()` must not rely only on yfinance for A-share.
- A-share symbols such as `600519`, `000001`, `300750`, `600519.SH`, and `000001.SZ` resolve to CN-aware context.
- HK and US symbols still produce useful context.
- Invalid/no-data symbols produce explicit no-data context rather than fabricated company identity.

**Acceptance:**
- Log paths cannot escape `results_dir`.
- Agent prompts receive deterministic `instrument_context`.
- No live network is required for unit tests.

---

### Task 4: LLM Provider Capability Merge

**Purpose:** Merge upstream structured-output provider handling with CN provider/key behavior.

**Files:**
- Create/adapt: `tradingagents/llm_clients/api_key_env.py`
- Create/adapt: `tradingagents/llm_clients/capabilities.py`
- Create/adapt: `tradingagents/llm_clients/azure_client.py`
- Modify: `tradingagents/llm_clients/factory.py`
- Modify: `tradingagents/llm_clients/openai_client.py`
- Modify: `tradingagents/llm_clients/google_client.py`
- Modify: `tradingagents/llm_clients/anthropic_client.py`
- Modify: `tradingagents/llm_clients/model_catalog.py`
- Modify: `tradingagents/llm_clients/provider_keys.py`
- Modify: `tradingagents/graph/trading_graph.py`
- Test: `tests/test_api_key_env.py`
- Test: `tests/test_capabilities.py`
- Test: `tests/test_deepseek_reasoning.py`
- Test: `tests/test_minimax.py`
- Test: `tests/test_google_api_key.py`
- Test: `tests/test_ollama_base_url.py`
- Test: `tests/test_anthropic_effort.py`
- Test: `tests/test_model_validation.py`

**Providers to preserve from CN:**
- `openai`
- `siliconflow`
- `deepseek`
- `qwen`
- `glm`
- `qianfan`
- `openrouter`
- `aihubmix`
- `ollama`
- `custom_openai`
- `google`
- `anthropic`

**Providers/capabilities to add from upstream:**
- `azure`
- `xai`
- `minimax`
- `minimax-cn`
- `qwen-cn`
- `glm-cn`
- OpenAI Responses API for native OpenAI where compatible.
- DeepSeek `reasoning_content` roundtrip.
- MiniMax `reasoning_split`.
- Capability-aware `with_structured_output()`.
- Anthropic effort handling.
- Google thinking-level forwarding, without discarding CN's Google adapter behavior.

**Compatibility requirements:**
- Explicit `api_key` passed from CN config must still work.
- Explicit `base_url` passed from CN config must still work.
- Mixed quick/deep provider mode remains supported.
- Missing env keys should not break tests that use explicit fake keys.

**Acceptance:**
- Provider factory can instantiate supported providers with fake API keys where network is not invoked.
- Existing CN model capability routes continue to recognize CN providers.
- Structured-output tests pass without requiring real provider calls.

---

### Task 5: Structured Schemas And Decision-Agent Integration

**Purpose:** Use upstream structured output without losing CN Chinese prompt semantics.

**Files:**
- Create/adapt: `tradingagents/agents/schemas.py`
- Create/adapt: `tradingagents/agents/utils/structured.py`
- Modify: `tradingagents/agents/managers/research_manager.py`
- Modify: `tradingagents/agents/trader/trader.py`
- Modify: `tradingagents/agents/managers/risk_manager.py`
- Modify: `tradingagents/agents/__init__.py`
- Test: `tests/test_structured_agents.py`

**Schemas to include:**
- `PortfolioRating`
- `TraderAction`
- `ResearchPlan`
- `TraderProposal`
- `PortfolioDecision`
- `SentimentReport`

**CN-specific schema extensions:**
- Preserve or add optional fields for:
  - target price
  - stop loss
  - position sizing
  - time horizon
  - quote currency
  - Chinese reasoning text

**Implementation rules:**
- Use `bind_structured()` and `invoke_structured_or_freetext()` as wrappers.
- Keep CN prompt content in Chinese.
- Keep Chroma memory retrieval in Research Manager, Trader, and Risk Manager.
- Render structured objects back into markdown/text so downstream state keys remain strings.

**Acceptance:**
- Structured-capable fake LLM returns rendered markdown/text.
- Non-structured fake LLM falls back to free text.
- `investment_plan`, `trader_investment_plan`, and `final_trade_decision` remain strings.

---

### Task 6: Portfolio Manager Migration Without Backend Breakage

**Purpose:** Add upstream Portfolio Manager capability while preserving CN `Risk Judge` semantics and report fields.

**Files:**
- Create/adapt: `tradingagents/agents/managers/portfolio_manager.py`
- Modify: `tradingagents/agents/managers/risk_manager.py`
- Modify: `tradingagents/graph/setup.py`
- Modify: `tradingagents/graph/conditional_logic.py`
- Modify: `tradingagents/graph/trading_graph.py`
- Modify only if required: `app/services/simple_analysis_service.py`
- Modify only if required: `web/utils/analysis_runner.py`
- Test: `tests/test_signal_processing.py`
- Test: `tests/test_structured_agents.py`

**Required behavior:**
- Existing `Risk Judge` node path remains valid.
- Upstream `Portfolio Manager` node path is either:
  - exposed as an alias to CN-compatible risk manager, or
  - added as the final risk synthesis node while `Risk Judge` remains a compatibility name.
- `risk_debate_state["judge_decision"]` remains populated.
- `final_trade_decision` remains populated.
- Both CN risk field names and upstream risk field names remain readable.

**Acceptance:**
- Backend report extraction still finds risk decision.
- Upstream-style final decision parsing can read `**Rating**`.
- CN final decision still contains Chinese actionable advice and target-price information.

---

### Task 7: Graph Runtime, Checkpointing, And Progress Streaming

**Purpose:** Merge upstream checkpoint/runtime behavior into CN graph without losing backend progress.

**Files:**
- Create/adapt: `tradingagents/graph/checkpointer.py`
- Modify: `tradingagents/graph/setup.py`
- Modify: `tradingagents/graph/trading_graph.py`
- Modify: `tradingagents/graph/propagation.py`
- Test: `tests/test_checkpoint_resume.py`
- Test: `tests/test_cli_env_skip.py`

**Required behavior:**
- `TradingAgentsGraph` keeps `self.workflow`.
- `self.graph = self.workflow.compile()` remains the normal path.
- When `checkpoint_enabled` is true, graph recompiles with sqlite saver.
- `thread_id(company_name, trade_date)` isolates checkpoint state by symbol/date.
- Successful completion clears checkpoint.
- `progress_callback` update streaming remains supported.
- `callbacks` can be passed to LLM/tool invocation where supported.

**Acceptance:**
- Checkpoint tests can simulate resume without live LLM calls.
- CN progress callbacks still receive known node messages.
- `propagate()` return shape remains `(final_state, decision)`.

---

### Task 8: Analyst Execution Plan And Node Mapping

**Purpose:** Use upstream analyst execution validation while retaining CN node labels and progress mapping.

**Files:**
- Create/adapt: `tradingagents/graph/analyst_execution.py`
- Modify: `tradingagents/graph/setup.py`
- Modify: `tradingagents/graph/trading_graph.py`
- Modify: `app/services/simple_analysis_service.py` only if node-message mapping needs explicit aliases.
- Test: `tests/test_analyst_execution.py`

**Required behavior:**
- Empty selected analyst list raises clear error.
- Unsupported analyst key raises clear error.
- Valid analyst keys remain:
  - `market`
  - `social`
  - `news`
  - `fundamentals`
- Existing CN node progress messages still work.
- Upstream node metadata can be used by tests and future concurrency work.

**Acceptance:**
- Existing CN analyst sequences still execute in the requested order.
- New validation tests pass.
- No backend progress regression from renamed nodes.

---

### Task 9: Dataflow Safety Layer And Market Data Validator

**Purpose:** Port upstream no-data and deterministic market snapshot behavior into CN multi-market data architecture.

**Files:**
- Create/adapt: `tradingagents/dataflows/market_data_validator.py`
- Create/adapt: `tradingagents/dataflows/symbol_utils.py`
- Create/adapt: `tradingagents/dataflows/utils.py`
- Create/adapt: `tradingagents/dataflows/config.py`
- Modify: `tradingagents/dataflows/interface.py`
- Modify: `tradingagents/agents/utils/agent_utils.py`
- Create/adapt: `tradingagents/agents/utils/core_stock_tools.py`
- Create/adapt: `tradingagents/agents/utils/fundamental_data_tools.py`
- Create/adapt: `tradingagents/agents/utils/news_data_tools.py`
- Create/adapt: `tradingagents/agents/utils/technical_indicators_tools.py`
- Test: `tests/test_dataflows_config.py`
- Test: `tests/test_market_data_validator.py`
- Test: `tests/test_no_data_handling.py`
- Test: `tests/test_stockstats_date_column.py`

**Required behavior:**
- Upstream tool names such as `get_stock_data`, `get_indicators`, `get_fundamentals`, `get_news`, and `get_global_news` exist as CN-compatible wrappers.
- CN unified Toolkit methods remain primary for A-share/HK data.
- Vendor fallback returns explicit `NO_DATA_AVAILABLE` sentinel where appropriate.
- Market snapshot excludes future rows after the requested analysis date.
- Tests use local fixtures or monkeypatches, not live vendor calls.

**Acceptance:**
- Market analyst can receive deterministic verified data snapshot.
- No-data paths instruct agents not to fabricate values.
- A-share behavior remains routed through CN provider logic.

---

### Task 10: Sentiment Analyst Migration For Multi-Market Data

**Purpose:** Add upstream structured sentiment reporting while respecting A-share data reality.

**Files:**
- Create/adapt: `tradingagents/agents/analysts/sentiment_analyst.py`
- Modify: `tradingagents/agents/analysts/social_media_analyst.py`
- Modify: `tradingagents/agents/__init__.py`
- Create/adapt: `tradingagents/dataflows/reddit.py`
- Create/adapt: `tradingagents/dataflows/stocktwits.py`
- Modify: `tradingagents/dataflows/interface.py`
- Test: `tests/test_reddit_fallback.py`
- Test: `tests/test_structured_agents.py`

**Required source routing:**
- A-share:
  - CN `get_stock_sentiment_unified`
  - Chinese finance/social sources
  - Chinese news sources
- HK:
  - CN/HK news and sentiment sources where available
  - global news fallback
- US:
  - yfinance/Alpha Vantage news if configured
  - StockTwits
  - Reddit fallback

**Implementation rules:**
- If a source is unavailable, the report explicitly says it is unavailable.
- Do not infer A-share retail sentiment from US-only Reddit/StockTwits by default.
- Keep `sentiment_report` as a string.

**Acceptance:**
- Structured sentiment output includes direction/confidence/source notes.
- A-share tests do not call Reddit/StockTwits unless explicitly configured.
- Existing `create_social_media_analyst` import remains valid.

---

### Task 11: TradingMemoryLog And A-Share Outcome Reflection

**Purpose:** Add upstream final-decision logging and delayed reflection without replacing CN Chroma role memory.

**Files:**
- Modify: `tradingagents/agents/utils/memory.py`
- Modify: `tradingagents/graph/trading_graph.py`
- Modify: `tradingagents/graph/reflection.py`
- Create/adapt: `tests/test_memory_log.py`

**Required behavior:**
- `FinancialSituationMemory` remains unchanged for role-level vector memory.
- `TradingMemoryLog` stores final decisions after successful propagation.
- Pending entries are resolved on later runs when price data is available.
- A-share raw return uses CN historical price data, not yfinance-only history.
- A-share benchmark uses CN index mapping, such as Shanghai/Shenzhen benchmarks where appropriate.
- If price or benchmark data is unavailable, pending entry remains unresolved.

**Acceptance:**
- Memory log tests pass using local fake price data.
- Reflection prompt can read same-ticker and cross-ticker lessons.
- No live market request is required for unit tests.

---

### Task 12: Signal Processing Compatibility

**Purpose:** Combine upstream deterministic rating parsing with CN final API decision extraction.

**Files:**
- Create/adapt: `tradingagents/agents/utils/rating.py`
- Modify: `tradingagents/graph/signal_processing.py`
- Modify: `tradingagents/graph/trading_graph.py`
- Test: `tests/test_signal_processing.py`

**Required behavior:**
- Parse upstream rating labels:
  - `Buy`
  - `Overweight`
  - `Hold`
  - `Underweight`
  - `Sell`
- Map ratings into CN actions:
  - `Buy` and `Overweight` -> `买入`
  - `Hold` -> `持有`
  - `Underweight` and `Sell` -> `卖出`
- Preserve CN target-price extraction and fallback behavior.
- Preserve confidence/risk score fields.
- Avoid a second LLM call when structured rating and target-price fields are already available.
- Use LLM fallback only when deterministic extraction cannot produce required CN fields.

**Acceptance:**
- Existing backend receives CN dict.
- Upstream tests for rating parsing pass.
- CN target-price extraction tests pass.

---

### Task 13: Backend And Report Contract Verification

**Purpose:** Ensure migrated graph output still feeds existing backend and web reporting.

**Files:**
- Read/modify only as needed: `app/services/simple_analysis_service.py`
- Read/modify only as needed: `app/services/analysis_service.py`
- Read/modify only as needed: `app/routers/analysis.py`
- Read/modify only as needed: `app/worker.py`
- Read/modify only as needed: `web/utils/analysis_runner.py`
- Read/modify only as needed: `web/utils/report_exporter.py`
- Test: existing backend tests under `backend/tests` if present
- Test: new focused tests for report extraction if no existing coverage exists

**Required behavior:**
- Existing task progress transitions still work.
- Existing report module extraction still works.
- `risk_debate_state` can be rendered whether it contains CN names, upstream names, or both.
- Final decision summary extraction still works.
- `performance_metrics` remains included in persisted analysis result.

**Acceptance:**
- A fake graph final state with migrated fields can be converted into the existing API/report result.
- No frontend component needs a breaking field rename.

---

### Task 14: Test Suite Port And Final Verification

**Purpose:** Make upstream behavior measurable in this project.

**Files:**
- Create/adapt upstream tests under `tests/`
- Create/adapt: `scripts/smoke_structured_output.py`

**Test groups to port/adapt:**
- `test_analyst_execution.py`
- `test_anthropic_effort.py`
- `test_api_key_env.py`
- `test_capabilities.py`
- `test_checkpoint_resume.py`
- `test_cli_env_skip.py`
- `test_crypto_asset_mode.py`
- `test_dataflows_config.py`
- `test_deepseek_reasoning.py`
- `test_env_overrides.py`
- `test_google_api_key.py`
- `test_instrument_identity.py`
- `test_market_data_validator.py`
- `test_memory_log.py`
- `test_minimax.py`
- `test_model_validation.py`
- `test_no_data_handling.py`
- `test_ollama_base_url.py`
- `test_reddit_fallback.py`
- `test_safe_ticker_component.py`
- `test_signal_processing.py`
- `test_stockstats_date_column.py`
- `test_structured_agents.py`
- `test_symbol_utils.py`
- `test_temperature_config.py`

**Verification commands:**
- `conda run -n trader python -m pytest tests/test_capabilities.py tests/test_api_key_env.py -q`
- `conda run -n trader python -m pytest tests/test_structured_agents.py tests/test_signal_processing.py -q`
- `conda run -n trader python -m pytest tests/test_checkpoint_resume.py -q`
- `conda run -n trader python -m pytest tests/test_market_data_validator.py tests/test_symbol_utils.py tests/test_no_data_handling.py -q`
- `conda run -n trader python -m pytest tests -q`

**Acceptance:**
- Migrated upstream behavior has local tests.
- Network-dependent paths are mocked or skipped with explicit reason.
- Final test report lists passing suites and any justified skipped tests.

---

## Execution Order

Use this order to avoid contradictory partial states:

1. Task 0: preflight and file classification.
2. Task 1: dependencies/config foundation.
3. Task 2: state compatibility.
4. Task 3: instrument identity and safe path utilities.
5. Task 4: LLM provider capability merge.
6. Task 5: structured schemas and decision-agent integration.
7. Task 6: Portfolio Manager compatibility.
8. Task 7: graph runtime/checkpoint/progress streaming.
9. Task 8: analyst execution plan and node mapping.
10. Task 9: dataflow safety layer and market data validator.
11. Task 10: sentiment analyst multi-market routing.
12. Task 11: memory log and A-share reflection.
13. Task 12: signal processing compatibility.
14. Task 13: backend/report contract verification.
15. Task 14: full adapted upstream test suite.

Rationale:
- State compatibility must come before Portfolio Manager and graph checkpoint work.
- Provider capability work must come before structured-output agents.
- Dataflow safety must come before A-share reflection and sentiment routing.
- Backend/report verification must happen after graph output shape stabilizes.

---

## Review: Coverage Matrix

| Requirement | Covered By | Notes |
|---|---|---|
| Complete upstream backend/core migration | Tasks 1-14 | CLI-only polish intentionally excluded from backend scope |
| Preserve CN backend progress | Tasks 7, 8, 13 | `progress_callback`, `task_id`, node messages retained |
| Preserve CN API result shape | Tasks 6, 12, 13 | Final decision remains CN dict after signal processing |
| Preserve A-share data behavior | Tasks 3, 9, 10, 11 | Upstream data safety is adapted to CN providers |
| Preserve Chinese prompts | Tasks 5, 6, 10, 12 | Structured output wraps CN prompts |
| Preserve database API-key config | Tasks 1, 4 | Env mapping added without removing DB key behavior |
| Add checkpoint/resume | Tasks 1, 7 | Requires workflow/compile refactor |
| Add structured output | Tasks 4, 5, 6, 10 | Capability-aware provider handling included |
| Add Portfolio Manager | Task 6 | Implemented through alias or compatibility node |
| Add TradingMemoryLog | Task 11 | Additive to Chroma role memory |
| Add upstream no-data safety | Tasks 3, 9 | Includes sentinel and deterministic validation |
| Add upstream tests | Task 14 | Tests adapted to local fakes |

No uncovered backend/core requirement remains from the analysis list.

## Review: Contradiction Check

Checked contradictions and resolutions:

1. Upstream `GraphSetup.setup_graph()` vs CN compiled graph:
   - Resolution: keep `self.workflow` and `self.graph`; compile normally, recompile with checkpointer only when enabled.

2. Upstream risk field names vs CN risk field names:
   - Resolution: dual-field compatibility until all consumers are verified.

3. Upstream rating string vs CN decision dict:
   - Resolution: upstream rating becomes internal deterministic signal; CN dict remains external contract.

4. Upstream yfinance outcome reflection vs A-share data requirement:
   - Resolution: reflection return calculation uses CN data source for A-share and only falls back when market-compatible.

5. Upstream env-only API keys vs CN DB API keys:
   - Resolution: explicit/config API keys remain supported; env mapping is fallback/canonical metadata.

6. Upstream StockTwits/Reddit sentiment vs A-share sentiment:
   - Resolution: source routing by market; A-share does not default to US-only social sources.

7. Upstream English schema/rendering vs CN Chinese output:
   - Resolution: schema constrains structure; CN prompt and Chinese rendered content remain.

No unresolved contradiction is left in this spec.

## Review: Omission Check

Checked upstream-only backend files and mapped them:

| Upstream Area | Spec Coverage |
|---|---|
| `tradingagents/graph/checkpointer.py` | Task 7 |
| `tradingagents/graph/analyst_execution.py` | Task 8 |
| `tradingagents/agents/schemas.py` | Task 5 |
| `tradingagents/agents/utils/structured.py` | Task 5 |
| `tradingagents/agents/utils/rating.py` | Task 12 |
| `tradingagents/agents/managers/portfolio_manager.py` | Task 6 |
| LLM `api_key_env`, `capabilities`, `azure_client` | Task 4 |
| LLM OpenAI/Google/Anthropic provider changes | Task 4 |
| Dataflow `symbol_utils`, `utils`, `market_data_validator`, config/router concepts | Tasks 3 and 9 |
| Alpha Vantage/YFinance/Reddit/StockTwits modules | Tasks 9 and 10 |
| `TradingMemoryLog` | Task 11 |
| Upstream tests | Task 14 |
| CLI helper modules | Out of first backend scope; can be a later CLI task if needed |

No backend/core omission remains from the comparison.

## Review: Risk Register

| Risk | Impact | Guardrail |
|---|---|---|
| Renaming risk nodes breaks progress/report extraction | High | Use aliases and backend contract tests before any rename |
| Checkpoint compile refactor breaks progress streaming | High | Add checkpoint tests and progress callback smoke before graph changes continue |
| Structured output fails on provider-specific models | High | Capability table plus free-text fallback tests |
| A-share data accidentally routed to yfinance-only path | High | Market-specific tests for A-share symbol resolution and no-data handling |
| Target price disappears from final result | High | Signal processor tests require `target_price` behavior |
| DB API keys stop working | High | Fake explicit-key tests in provider factory |
| Existing untracked copied files mask import failures | Medium | Task 0 classification and import smoke |
| Upstream tests require live network | Medium | Mock/fixture network-dependent tests |

## Final Spec Status

This spec is internally consistent:
- Every mandatory migration item from the code comparison maps to at least one task.
- Every known structural conflict has an explicit resolution.
- CN backend compatibility contracts are stated before implementation tasks.
- Verification is defined per subsystem and again at full-suite level.
