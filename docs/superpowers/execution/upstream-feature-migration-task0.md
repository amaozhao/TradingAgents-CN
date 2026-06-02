# Upstream Feature Migration Task 0 Baseline

Date: 2026-06-02

## Repositories

- Current project: `/home/amaozhao/workspace/TradingAgents-CN`
- Current branch: `dev`
- Current HEAD: `cdd0316`
- Upstream source: `/home/amaozhao/workspace/TradingAgents`
- Upstream HEAD: `04f434e`
- Upstream status: clean

## Current Dirty Worktree

Existing modified files before this migration execution:

- `frontend/package.json`
- `frontend/src/layouts/BasicLayout.vue`
- `frontend/src/stores/auth.ts`
- `frontend/src/views/Dashboard/index.vue`
- `frontend/src/views/Favorites/index.vue`
- `frontend/src/views/Reports/TokenStatistics.vue`
- `frontend/src/views/Reports/index.vue`
- `frontend/src/views/Screening/index.vue`
- `frontend/src/views/Settings/ConfigManagement.vue`
- `frontend/src/views/Settings/components/MarketCategoryManagement.vue`
- `frontend/src/views/System/LogManagement.vue`
- `frontend/src/views/System/MultiSourceSync.vue`
- `frontend/src/views/System/SchedulerManagement.vue`
- `frontend/tsconfig.json`
- `frontend/yarn.lock`
- `backend/pyproject.toml`

Existing untracked migration-related files before this execution:

- `tradingagents/agents/managers/portfolio_manager.py`
- `tradingagents/agents/schemas.py`
- `tradingagents/agents/utils/structured.py`
- `tradingagents/graph/analyst_execution.py`
- `tradingagents/graph/checkpointer.py`
- `tradingagents/llm_clients/api_key_env.py`
- `tradingagents/llm_clients/azure_client.py`
- `tradingagents/llm_clients/capabilities.py`

These files match upstream byte-for-byte at baseline and are classified as
`keep-and-adapt`, not as completed migration.

## Import Smoke

Command:

```bash
conda run -n trader python -c "import importlib; ..."
```

Results:

- OK: `tradingagents.agents.schemas`
- OK: `tradingagents.agents.utils.structured`
- OK: `tradingagents.graph.analyst_execution`
- FAIL: `tradingagents.graph.checkpointer`
  - `ModuleNotFoundError: No module named 'langgraph.checkpoint.sqlite'`
  - Expected until `langgraph-checkpoint-sqlite` is installed/declared.
- OK: `tradingagents.llm_clients.api_key_env`
- OK: `tradingagents.llm_clients.azure_client`
- OK: `tradingagents.llm_clients.capabilities`
- FAIL: `tradingagents.agents.managers.portfolio_manager`
  - `ImportError: cannot import name 'get_instrument_context_from_state' from 'tradingagents.agents.utils.agent_utils'`
  - Expected until CN `agent_utils` exposes upstream-compatible instrument context helpers.

## Upstream-Only Backend/Core Files

The tracked upstream files missing from current tracked CN files include:

- `tradingagents/agents/analysts/sentiment_analyst.py`
- `tradingagents/agents/managers/portfolio_manager.py`
- `tradingagents/agents/risk_mgmt/aggressive_debator.py`
- `tradingagents/agents/schemas.py`
- `tradingagents/agents/utils/core_stock_tools.py`
- `tradingagents/agents/utils/fundamental_data_tools.py`
- `tradingagents/agents/utils/market_data_validation_tools.py`
- `tradingagents/agents/utils/news_data_tools.py`
- `tradingagents/agents/utils/rating.py`
- `tradingagents/agents/utils/structured.py`
- `tradingagents/agents/utils/technical_indicators_tools.py`
- `tradingagents/dataflows/alpha_vantage.py`
- `tradingagents/dataflows/alpha_vantage_common.py`
- `tradingagents/dataflows/alpha_vantage_fundamentals.py`
- `tradingagents/dataflows/alpha_vantage_indicator.py`
- `tradingagents/dataflows/alpha_vantage_news.py`
- `tradingagents/dataflows/alpha_vantage_stock.py`
- `tradingagents/dataflows/config.py`
- `tradingagents/dataflows/market_data_validator.py`
- `tradingagents/dataflows/reddit.py`
- `tradingagents/dataflows/stockstats_utils.py`
- `tradingagents/dataflows/stocktwits.py`
- `tradingagents/dataflows/symbol_utils.py`
- `tradingagents/dataflows/utils.py`
- `tradingagents/dataflows/y_finance.py`
- `tradingagents/dataflows/yfinance_news.py`
- `tradingagents/graph/analyst_execution.py`
- `tradingagents/graph/checkpointer.py`
- `tradingagents/llm_clients/api_key_env.py`
- `tradingagents/llm_clients/azure_client.py`
- `tradingagents/llm_clients/capabilities.py`

Upstream test files are tracked in the migration plan Task 14 and will be
ported/adapted after runtime compatibility work.
