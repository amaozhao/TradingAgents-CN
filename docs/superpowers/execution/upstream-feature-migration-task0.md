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

- `trader/agents/managers/portfolio_manager.py`
- `trader/agents/schemas.py`
- `trader/agents/utils/structured.py`
- `trader/graph/analyst_execution.py`
- `trader/graph/checkpointer.py`
- `trader/llm_clients/api_key_env.py`
- `trader/llm_clients/azure_client.py`
- `trader/llm_clients/capabilities.py`

These files match upstream byte-for-byte at baseline and are classified as
`keep-and-adapt`, not as completed migration.

## Import Smoke

Command:

```bash
conda run -n trader python -c "import importlib; ..."
```

Results:

- OK: `trader.agents.schemas`
- OK: `trader.agents.utils.structured`
- OK: `trader.graph.analyst_execution`
- FAIL: `trader.graph.checkpointer`
  - `ModuleNotFoundError: No module named 'langgraph.checkpoint.sqlite'`
  - Expected until `langgraph-checkpoint-sqlite` is installed/declared.
- OK: `trader.llm.clients.api_key_env`
- OK: `trader.llm.clients.azure_client`
- OK: `trader.llm.clients.capabilities`
- FAIL: `trader.agents.managers.portfolio_manager`
  - `ImportError: cannot import name 'get_instrument_context_from_state' from 'trader.agents.utils.agent_utils'`
  - Expected until CN `agent_utils` exposes upstream-compatible instrument context helpers.

## Upstream-Only Backend/Core Files

The tracked upstream files missing from current tracked CN files include:

- `trader/agents/analysts/sentiment_analyst.py`
- `trader/agents/managers/portfolio_manager.py`
- `trader/agents/risk_mgmt/aggressive_debator.py`
- `trader/agents/schemas.py`
- `trader/agents/utils/core_stock_tools.py`
- `trader/agents/utils/fundamental_data_tools.py`
- `trader/agents/utils/market_data_validation_tools.py`
- `trader/agents/utils/news_data_tools.py`
- `trader/agents/utils/rating.py`
- `trader/agents/utils/structured.py`
- `trader/agents/utils/technical_indicators_tools.py`
- `trader/dataflows/alpha_vantage.py`
- `trader/dataflows/alpha_vantage_common.py`
- `trader/dataflows/alpha_vantage_fundamentals.py`
- `trader/dataflows/alpha_vantage_indicator.py`
- `trader/dataflows/alpha_vantage_news.py`
- `trader/dataflows/alpha_vantage_stock.py`
- `trader/dataflows/config.py`
- `trader/dataflows/market_data_validator.py`
- `trader/dataflows/reddit.py`
- `trader/dataflows/stockstats_utils.py`
- `trader/dataflows/stocktwits.py`
- `trader/dataflows/symbol_utils.py`
- `trader/dataflows/utils.py`
- `trader/dataflows/y_finance.py`
- `trader/dataflows/yfinance_news.py`
- `trader/graph/analyst_execution.py`
- `trader/graph/checkpointer.py`
- `trader/llm_clients/api_key_env.py`
- `trader/llm_clients/azure_client.py`
- `trader/llm_clients/capabilities.py`

Upstream test files are tracked in the migration plan Task 14 and will be
ported/adapted after runtime compatibility work.
