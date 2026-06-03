# PostgreSQL Hot Field Matrix

This matrix is the cutover checklist for JSONB-first tables that still need split columns for frequent filters, sort keys, uniqueness, or worker/status safety. It is referenced by the cutover runbook before enabling PostgreSQL reads.

## Rules

- Fields listed under `required split columns` must be PostgreSQL columns, not only `payload` keys.
- Fields listed under `required indexes or constraints` must exist in SQLAlchemy metadata and Alembic DDL.
- Query-plan acceptance must show representative high-frequency filters do not use JSONB payload predicates.
- Worker/status collections in this file cannot be treated as Mongo-only during read cutover.

## High-Frequency Read Paths

| API or service path | PostgreSQL table | Required split columns | Required indexes or constraints | Query-plan gate |
| --- | --- | --- | --- | --- |
| Stock list and stock basics | `stock_basic_info` | `code`, `source`, `name`, `industry`, `area`, `market`, `total_mv`, `circ_mv`, `pe`, `pb`, `pe_ttm`, `pb_mrq`, `updated_at` | `uq_stock_basic_info_code_source`; indexes on `industry`, `total_mv`, `pe`, `pb` | `stock_list_page`, `stock_screening` |
| Latest market quote and screening joins | `market_quotes` | `code`, `source`, `trade_date`, `open`, `high`, `low`, `close`, `pre_close`, `pct_chg`, `amount`, `volume`, `updated_at` | `uq_market_quotes_code_source`; indexes on `pct_chg`, `amount`, `updated_at` | `stock_screening` |
| Historical daily quotes | `stock_daily_quotes` | `symbol`, `code`, `full_symbol`, `market`, `trade_date`, `period`, `data_source`, `open`, `high`, `low`, `close`, `pre_close`, `volume`, `amount`, `change`, `pct_chg`, `deleted`, `updated_at` | `uq_stock_daily_quotes_symbol_date_source_period`; indexes on `symbol+trade_date`, `trade_date`, `market+data_source` | `daily_quotes_range` |
| Financial metrics | `stock_financial_data` | `code`, `data_source`, `report_period`, `roe`, `roa`, `netprofit_margin`, `gross_margin`, `updated_at` | `uq_stock_financial_data_code_source_period`; index on `report_period` | `financial_data` |
| Operation log list, stats, export | `operation_logs` | `user_id`, `username`, `action_type`, `success`, `timestamp`, `deleted`, `updated_at` | indexes on `user_id+timestamp`, `action_type+success` | `operation_logs_page` |
| Favorites | `user_favorites` | `user_id`, `stock_code`, `stock_name`, `market`, `deleted`, `updated_at` | `uq_user_favorites_user_stock`; index on `user_id` | `user_favorites` |
| Tags | `user_tags` | `user_id`, `tag_id`, `name`, `color`, `sort_order`, `deleted`, `updated_at` | `uq_user_tags_user_name`; index on `user_id+sort_order` | `user_tags` |
| Paper positions | `paper_positions` | `user_id`, `code`, `market`, `currency`, `quantity`, `deleted`, `updated_at` | `uq_paper_positions_user_code`; index on `user_id` | `paper_positions` |
| Paper orders | `paper_orders` | `user_id`, `code`, `side`, `status`, `deleted`, `created_at`, `updated_at` | index on `user_id+created_at` | `paper_orders` |

## Status, Worker, And Operational Writes

| Mongo collection | PostgreSQL table | Required split columns | Cutover rule |
| --- | --- | --- | --- |
| `sync_status` / `quotes_ingestion_status` | `sync_status` | `job`, `status`, `started_at`, `finished_at`, `duration`, `updated_at` | Startup, sync workers, and quote ingestion status must dual-write or be paused with log evidence before read cutover. |
| `scheduler_executions` | `scheduler_executions` | `job_id`, `status`, `progress`, `progress_message`, `timestamp`, `cancel_requested` | Running and terminal scheduler updates must dual-write. |
| `scheduler_history` | `scheduler_history` | `job_id`, `action`, `status`, `timestamp`, `deleted` | Scheduler history append/delete paths must dual-write or be explicitly paused. |
| `scheduler_metadata` | `scheduler_metadata` | `job_id`, `display_name`, `description`, `deleted` | Scheduler metadata updates must dual-write before read cutover. |
| `analysis_tasks` | `analysis_tasks` | `task_id`, `user_id`, `stock_symbol`, `status`, `progress`, `created_at`, `updated_at` | Analysis task status changes must dual-write; Mongo-only task status is a blocker. |
| `analysis_reports` | `analysis_reports` | `analysis_id`, `task_id`, `user_id`, `stock_symbol`, `analysis_date`, `summary` | Analysis result/report writes must dual-write before task APIs read PostgreSQL. |
| `analysis_batches` | `analysis_batches` | `batch_id`, `user_id`, `status`, `total_tasks`, `deleted` | Batch lifecycle writes must dual-write or be disabled during cutover. |
| `analysis_results` | `analysis_results` | `task_id`, `user_id`, `stock_symbol`, `status`, `deleted` | Cleanup must write tombstones before Mongo deletion. |
| `database_backups` | `database_backups` | `name`, `filename`, `created_by`, `backup_type`, `deleted`, `created_at`, `updated_at` | Backup metadata writes and migrated-collection import replay must dual-write; unknown ad-hoc collection import remains explicit Mongo-only. |

## User, Security, And Dynamic Business Data

| Mongo collection | PostgreSQL table | Required split columns | Cutover rule |
| --- | --- | --- | --- |
| `users` / `users_collection` | `user_accounts` | `username`, `email`, `is_active`, `is_admin`, `deleted`, `updated_at` | Auth and user list reads can use PostgreSQL first only after migration consistency covers both Mongo aliases. |
| `user_sessions` | `user_sessions` | `session_id`, `user_id`, `username`, `ip_address`, `user_agent`, `expires_at`, `last_activity_at`, `deleted` | Session cleanup must write tombstones; TTL and audit filters must use split columns. |
| `login_attempts` | `login_attempts` | `user_id`, `username`, `ip_address`, `success`, `reason`, `timestamp`, `deleted` | Security cleanup and audit checks must write PostgreSQL tombstones. |
| `stock_news` | `stock_news` | `symbol`, `market`, `title`, `url`, `data_source`, `category`, `sentiment`, `importance`, `publish_time`, `deleted`, `updated_at` | News query and cleanup must use PostgreSQL split fields and tombstones. |
| `notifications` | `notifications` | `user_id`, `type`, `status`, `severity`, `title`, `deleted` | Notification create/read-status/delete paths must dual-write. |
| `token_usage` | `token_usage` | `provider`, `model_name`, `session_id`, `timestamp`, `input_tokens`, `output_tokens`, `cost`, `currency`, `deleted` | Token usage accounting must not remain Mongo-only once PostgreSQL reads are enabled. |
| `internal_messages` | `internal_messages` | `message_id`, `symbol`, `message_type`, `category`, `access_level`, `importance`, `created_time`, `deleted` | Query/search/stats filters must use split columns; bulk upserts must dual-write. |
| `social_media_messages` | `social_media_messages` | `message_id`, `platform`, `symbol`, `message_type`, `sentiment`, `importance`, `publish_time`, `deleted` | Query/search/stats filters must use split columns; bulk upserts must dual-write. |

## Verification

Current local verification is covered by:

- `backend/tests/db/test_models.py`
- `backend/tests/db/test_query_plan_checker.py`
- `backend/scripts/postgres/query/plan/check/script.py`
- `docs/migration/worker_dual_write_coverage.md`
- `docs/migration/postgres_long_tail_coverage.md`

Target-environment verification must re-run `backend/scripts/postgres/query/plan/check/script.py` without `--compile-only` and save the JSON output before entering `postgres_read_mongo_fallback`.
