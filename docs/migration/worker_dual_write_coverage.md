# Worker Dual-Write Coverage

Generated from `docs/migration/postgres_inventory.json` after adding collection-name extraction.

## Summary

- Worker Mongo write files: 9
- Worker Mongo write operations: 18
- Hot, market-variant, or status writes covered by PostgreSQL dual-write: 18
- Mongo-only status writes with explicit warning: 0

## Coverage

| File | Line | Mongo collection | Operation | PostgreSQL action | Status |
| --- | ---: | --- | --- | --- | --- |
| `app/worker/akshare_sync_service.py` | 179 | `stock_basic_info` | `update_one` | `dual_write_hot_document("stock_basic_info", ...)` | covered |
| `app/worker/akshare_sync_service.py` | 353 | `market_quotes` | `update_one` | `dual_write_hot_document("market_quotes", ...)` | covered |
| `app/worker/akshare_sync_service.py` | 437 | `market_quotes` | `update_one` | `dual_write_hot_document("market_quotes", ...)` | covered |
| `app/worker/akshare_sync_service.py` | 534 | `market_quotes` | `update_one` | `dual_write_hot_document("market_quotes", ...)` | covered |
| `app/worker/baostock_init_service.py` | 258 | `stock_basic_info` | `update_one` | `dual_write_hot_document("stock_basic_info", ...)` | covered |
| `app/worker/baostock_sync_service.py` | 245 | `stock_basic_info` | `update_one` | `dual_write_hot_document("stock_basic_info", ...)` | covered |
| `app/worker/baostock_sync_service.py` | 342 | `market_quotes` | `update_one` | `dual_write_hot_document("market_quotes", ...)` | covered |
| `app/worker/baostock_sync_service.py` | 491 | `market_quotes` | `update_one` | `dual_write_hot_document("market_quotes", ...)` | covered |
| `app/worker/example_sdk_sync_service.py` | 256 | `stock_financial_data` | `update_one` | `dual_write_hot_document("stock_financial_data", ...)` | covered |
| `app/worker/example_sdk_sync_service.py` | 288 | `sync_status` | `update_one` | `dual_write_hot_document("sync_status", ...)` | covered |
| `app/worker/hk_data_service.py` | 138 | `stock_basic_info_hk` | `update_one` | `dual_write_hot_document("stock_basic_info", ...)` | covered |
| `app/worker/hk_sync_service.py` | 222 | `stock_basic_info_hk` | `bulk_write` | `dual_write_hot_documents("stock_basic_info", ...)` | covered |
| `app/worker/hk_sync_service.py` | 328 | `stock_basic_info_hk` | `bulk_write` | `dual_write_hot_documents("stock_basic_info", ...)` | covered |
| `app/worker/hk_sync_service.py` | 455 | `market_quotes_hk` | `bulk_write` | `dual_write_hot_documents("market_quotes", ...)` | covered |
| `app/worker/tushare_sync_service.py` | 1290 | `scheduler_executions` | `update_one` | `dual_write_hot_document("scheduler_executions", ...)` | covered |
| `app/worker/us_data_service.py` | 137 | `stock_basic_info_us` | `update_one` | `dual_write_hot_document("stock_basic_info", ...)` | covered |
| `app/worker/us_sync_service.py` | 249 | `stock_basic_info_us` | `bulk_write` | `dual_write_hot_documents("stock_basic_info", ...)` | covered |
| `app/worker/us_sync_service.py` | 375 | `market_quotes_us` | `bulk_write` | `dual_write_hot_documents("market_quotes", ...)` | covered |

## Cutover Rule

`sync_status` and `scheduler_executions` are status collections and are now included in the first-wave JSONB PostgreSQL schema. Do not disable MongoDB until the consistency checker reports these collections, plus market-data and analysis collections, as consistent.

Remaining fail-closed hardening is controlled by `POSTGRES_DUAL_WRITE_FAIL_OPEN`; production cutover should set it according to the operation risk of each writer.
